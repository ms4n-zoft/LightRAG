"""LightRAG client wrapper with enhanced functionality"""

import os
import logging
from typing import Optional, List
import numpy as np
from openai import OpenAI, AzureOpenAI

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status

logger = logging.getLogger(__name__)


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
            logger.info(
                f"🧠 Calling LLM for {task_type} ({len(prompt)} chars)...")

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

        # Initialize LightRAG with Neo4j graph storage
        # Use optimized settings that match the main server
        self.rag = LightRAG(
            working_dir=self.working_dir,
            llm_model_func=self.llm_func,
            embedding_func=embedding_func_instance,
            graph_storage="Neo4JStorage",  # Use Neo4j for knowledge graph
            log_level="INFO",
            # Performance optimizations for large-scale ingestion
            # Disable gleaning (2 LLM calls instead of 4)
            entity_extract_max_gleaning=0,
            # Settings will be inherited from environment variables (.env)
            # This ensures consistency with main server performance settings
        )

        # Initialize storages
        await self.rag.initialize_storages()
        await initialize_pipeline_status()

        logger.info(
            f"✅ LightRAG initialized with working directory: {self.working_dir}")
        return self.rag

    async def insert_text(self, text: str) -> bool:
        """Insert text into LightRAG (async)"""
        return await self.insert_text_with_source(text, "product_ingestion")

    async def insert_text_with_source(self, text: str, source_name: str) -> bool:
        """Insert text into LightRAG with source identification (async)"""
        if not self.rag:
            raise ValueError("RAG not initialized. Call initialize() first.")

        try:
            logger.info(f"🔄 Starting LightRAG knowledge graph construction...")
            logger.info(f"   📄 Text length: {len(text):,} characters")
            logger.info(f"   📂 Source: {source_name}")
            logger.info(
                f"   🧠 This will involve multiple LLM calls for entity/relationship extraction")
            logger.info(f"   🔗 Plus embedding generation for vector search")
            logger.info(
                f"   ⏱️  Please wait - this typically takes 1-3 minutes per batch...")

            # Add timeout protection to prevent hanging
            import asyncio
            try:
                # 5 minute timeout - insert with source identification
                await asyncio.wait_for(
                    self.rag.ainsert(text, file_paths=[source_name]),
                    timeout=300
                )
            except asyncio.TimeoutError:
                logger.error(f"⏰ LLM processing timed out after 5 minutes")
                raise Exception(
                    "LLM processing timeout - consider reducing text size or increasing timeout")

            logger.info(
                f"🎉 Knowledge graph construction completed successfully!")
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
