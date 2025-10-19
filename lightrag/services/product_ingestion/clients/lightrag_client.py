"""LightRAG client wrapper with enhanced functionality"""

import os
import logging
from typing import Optional, List
import numpy as np
from openai import OpenAI, AzureOpenAI

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status

logger = logging.getLogger("lightrag_client")


class LightRAGClient:
    """Enhanced LightRAG client with optimized configuration"""

    def __init__(self, working_dir: str):
        """Initialize LightRAG client"""
        self.working_dir = working_dir
        self.rag: Optional[LightRAG] = None

        # Initialize LLM and embedding functions
        self.llm_func = self._create_llm_function()
        self.embedding_func = self._create_embedding_function()

    def _create_llm_function(self):
        """Create Azure OpenAI LLM function"""
        async def azure_openai_llm_func(prompt, system_prompt=None, history_messages=[], **kwargs) -> str:
            client = AzureOpenAI(
                api_key=os.getenv("LLM_BINDING_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.getenv("LLM_BINDING_HOST"),
            )
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if history_messages:
                messages.extend(history_messages)
            messages.append({"role": "user", "content": prompt})

            # Log what type of LLM processing is happening
            task_type = "entity extraction" if "extract" in prompt.lower() else "text analysis"
            prompt_chars = len(prompt)
            estimated_tokens = prompt_chars // 4  # Rough estimate: 4 chars per token
            logger.info(
                f"🧠 Calling LLM for {task_type}")
            logger.info(
                f"   📊 Prompt size: {prompt_chars:,} chars (~{estimated_tokens:,} tokens)")
            logger.info(f"   🔄 Processing request...")

            # Log a sample of the prompt to debug
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"🔍 Prompt preview: {prompt[:200]}...")

            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                messages=messages,
                # Changed from 0 to 1
                temperature=kwargs.get("temperature", 1),
                # Remove token limit to allow maximum response length
            )

            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason

            # Check for token limit issues
            if finish_reason == "length":
                logger.warning(
                    f"⚠️  LLM hit model's maximum token limit for {task_type} - response may be incomplete")
                if hasattr(response, 'usage'):
                    logger.debug(
                        f"🔍 Token usage: {response.usage.completion_tokens} completion tokens (no limit set)")

            if not content or content.strip() == "":
                logger.warning(
                    f"⚠️  LLM returned empty response for {task_type} (finish_reason: {finish_reason})")
                logger.debug(f"🔍 Full response: {response}")
                return ""

            logger.info(
                f"✅ LLM response received ({len(content)} chars, finish_reason: {finish_reason})")

            # Log completion delimiter check
            if "<|COMPLETE|>" not in content:
                logger.warning(
                    f"⚠️  LLM response missing completion delimiter for {task_type}")
                logger.debug(f"🔍 Response preview: {content[:200]}...")

            return content

        return azure_openai_llm_func

    def _create_embedding_function(self):
        """Create Azure embedding function"""
        async def azure_embedding_func(texts: List[str]) -> np.ndarray:
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_EMBEDDING_API_KEY"),
                api_version=os.getenv("AZURE_EMBEDDING_API_VERSION"),
                azure_endpoint=os.getenv("AZURE_EMBEDDING_ENDPOINT"),
            )

            # Log embedding generation
            total_chars = sum(len(text) for text in texts)
            logger.info(
                f"🔗 Generating embeddings for {len(texts)} text chunks ({total_chars} total chars)...")

            response = client.embeddings.create(
                model=os.getenv("AZURE_EMBEDDING_DEPLOYMENT"),
                input=texts
            )

            logger.info(
                f"✅ Embeddings generated ({len(response.data)} vectors)")
            embeddings = [item.embedding for item in response.data]
            return np.array(embeddings)

        return azure_embedding_func

    async def initialize(self) -> LightRAG:
        """Initialize LightRAG instance with optimized configuration"""
        if self.rag:
            return self.rag

        # Ensure working directory exists
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)

        # Create embedding function instance
        embedding_func_instance = EmbeddingFunc(
            embedding_dim=int(os.getenv("EMBEDDING_DIM", 1536)),
            max_token_size=8192,
            func=self.embedding_func,
        )

        # Initialize LightRAG with same storage configuration as main server
        # Use EXACTLY the same defaults as main server (api/config.py)
        from lightrag.utils import get_env_value
        from lightrag.api.config import DefaultRAGStorageConfig

        kv_storage = get_env_value(
            "LIGHTRAG_KV_STORAGE", DefaultRAGStorageConfig.KV_STORAGE)
        doc_status_storage = get_env_value(
            "LIGHTRAG_DOC_STATUS_STORAGE", DefaultRAGStorageConfig.DOC_STATUS_STORAGE)
        graph_storage = get_env_value(
            "LIGHTRAG_GRAPH_STORAGE", DefaultRAGStorageConfig.GRAPH_STORAGE)
        vector_storage = get_env_value(
            "LIGHTRAG_VECTOR_STORAGE", DefaultRAGStorageConfig.VECTOR_STORAGE)

        logger.info(f"📦 Product ingestion using storage backends:")
        logger.info(f"   - KV Storage: {kv_storage}")
        logger.info(f"   - Doc Status Storage: {doc_status_storage}")
        logger.info(f"   - Graph Storage: {graph_storage}")
        logger.info(f"   - Vector Storage: {vector_storage}")

        self.rag = LightRAG(
            working_dir=self.working_dir,
            llm_model_func=self.llm_func,
            embedding_func=embedding_func_instance,
            # Use same storage backends as main server from environment variables
            kv_storage=kv_storage,
            vector_storage=vector_storage,
            graph_storage=graph_storage,
            doc_status_storage=doc_status_storage,
            log_level="INFO",
            # Performance optimizations for large-scale ingestion
            # Disable gleaning (2 LLM calls instead of 4)
            entity_extract_max_gleaning=0,
            # Enhanced metadata support for product ingestion
            vector_db_storage_cls_kwargs={
                "cosine_better_than_threshold": 0.2,  # Required for Qdrant
            },
            # Settings will be inherited from environment variables (.env)
            # This ensures consistency with main server performance settings
        )

        # Initialize storages
        await self.rag.initialize_storages()

        # Enhance vector storages with product metadata fields
        await self._enhance_metadata_support()

        await initialize_pipeline_status()

        logger.info(f"✅ LightRAG initialized with enhanced metadata support")
        return self.rag

    async def _enhance_metadata_support(self):
        """Enhance vector storages with minimal product metadata for search convenience

        Only store product_id and weburl - they're small and useful in search results.
        All other metadata is available in the graph storage.
        """
        # Minimal product fields for convenience (small size, useful for search results)
        product_meta_fields = {
            "product_id",  # unique identifier
            "weburl",      # product reference url
        }

        # Enhance entities vector storage
        if hasattr(self.rag.entities_vdb, 'meta_fields'):
            self.rag.entities_vdb.meta_fields.update(product_meta_fields)

        # Enhance relationships vector storage
        if hasattr(self.rag.relationships_vdb, 'meta_fields'):
            self.rag.relationships_vdb.meta_fields.update(product_meta_fields)

        # Enhance chunks vector storage
        if hasattr(self.rag.chunks_vdb, 'meta_fields'):
            self.rag.chunks_vdb.meta_fields.update(product_meta_fields)

        logger.info(
            f"✅ Enhanced vector storages with {len(product_meta_fields)} minimal product fields (product_id, weburl)")

    async def insert_text(self, text: str) -> bool:
        """Insert text into LightRAG (async)"""
        return await self.insert_text_with_source(text, "product_ingestion")

    async def insert_text_with_source(self, text: str, source_name: str, product_id: str = None, category: str = None, product_metadata: dict = None) -> bool:
        """Insert text into LightRAG with source identification and product metadata (async)"""
        if not self.rag:
            raise ValueError("RAG not initialized. Call initialize() first.")

        import time
        start_time = time.time()

        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"🚀 STARTING PRODUCT INGESTION")
            logger.info(f"{'='*80}")
            logger.info(f"   📄 Text length: {len(text):,} characters")
            logger.info(f"   📂 Source: {source_name}")
            if product_metadata and product_metadata.get("company"):
                logger.info(f"   🏢 Product: {product_metadata.get('company')}")
            if category:
                logger.info(f"   📂 Category: {category}")
            logger.info(f"{'='*80}")

            # Build enhanced file path with metadata
            if product_id and category:
                enhanced_file_path = f"product_id:{product_id}:category:{category}:source:{source_name}"
            elif product_id:
                enhanced_file_path = f"product_id:{product_id}:source:{source_name}"
            else:
                enhanced_file_path = source_name

            # Add timeout protection to prevent hanging
            import asyncio
            try:
                # 10 minute timeout for small batches (was 5 minutes)
                timeout_seconds = 600  # 10 minutes
                logger.info(
                    f"   ⏰ Timeout set to {timeout_seconds//60} minutes")

                # Prepare metadata for LightRAG
                metadata = {}
                if product_metadata:
                    metadata.update(product_metadata)
                if product_id:
                    metadata["product_id"] = product_id
                if category:
                    metadata["category"] = category

                logger.info(f"\n🧠 STARTING LLM PROCESSING")
                logger.info(
                    f"   ⚡ Entity extraction → Relationship extraction → Embeddings")
                logger.info(f"   📊 Metadata fields: {len(metadata)} injected")

                # Use document pipeline for WebUI integration
                track_id = f"products_{int(start_time)}"

                # First enqueue the document in the pipeline
                await self.rag.apipeline_enqueue_documents(
                    input=text,
                    ids=[product_id] if product_id else None,
                    file_paths=[enhanced_file_path],
                    track_id=track_id,
                    metadata=metadata if metadata else None
                )

                # Then process it with timeout
                await asyncio.wait_for(
                    self.rag.apipeline_process_enqueue_documents(),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"⏰ LLM processing timed out after {timeout_seconds//60} minutes")
                logger.error(f"   📊 Text size: {len(text):,} characters")
                logger.error(
                    f"   💡 Consider reducing batch size further if this persists")
                raise Exception(
                    f"LLM processing timeout after {timeout_seconds//60} minutes - text too large for efficient processing")

            end_time = time.time()
            duration = end_time - start_time

            logger.info(f"\n{'='*80}")
            logger.info(f"🎉 PRODUCT INGESTION COMPLETED!")
            logger.info(f"{'='*80}")
            logger.info(
                f"   ⏱️  Total time: {duration:.1f} seconds ({duration/60:.1f} minutes)")
            if product_metadata and product_metadata.get("company"):
                logger.info(f"   🏢 Product: {product_metadata.get('company')}")
            logger.info(
                f"   📊 Metadata fields: {len(metadata) if metadata else 0}")
            logger.info(f"{'='*80}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert text: {e}")
            return False

    async def query_rfp(self, requirements: str, **kwargs) -> str:
        """Query for RFP generation using hybrid mode"""
        if not self.rag:
            raise ValueError("RAG not initialized. Call initialize() first.")

        # Use hybrid mode for complex reasoning
        result = self.rag.query(
            requirements,
            param=QueryParam(mode="hybrid", **kwargs)
        )
        return result

    async def query_semantic(self, query: str, **kwargs) -> str:
        """Query for semantic search using local mode"""
        if not self.rag:
            raise ValueError("RAG not initialized. Call initialize() first.")

        # Use local mode for semantic similarity
        result = self.rag.query(
            query,
            param=QueryParam(mode="local", **kwargs)
        )
        return result

    async def query_custom(self, query: str, mode: str = "mix", **kwargs) -> str:
        """Custom query with specified mode"""
        if not self.rag:
            raise ValueError("RAG not initialized. Call initialize() first.")

        result = self.rag.query(
            query,
            param=QueryParam(mode=mode, **kwargs)
        )
        return result

    def get_stats(self) -> dict:
        """Get basic statistics about the RAG instance"""
        if not self.rag:
            return {"status": "not_initialized"}

        # TODO: Add more detailed statistics
        return {
            "status": "initialized",
            "working_dir": self.working_dir,
            "graph_storage": "Neo4jGraphStorage"
        }
