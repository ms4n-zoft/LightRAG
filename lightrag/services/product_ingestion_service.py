#!/usr/bin/env python3
"""
Product Ingestion Service for LightRAG

This service handles:
1. Product data normalization from MongoDB
2. Metadata extraction and categorization  
3. Batch ingestion with progress tracking
4. Knowledge graph construction for RFP use cases
5. Vector embeddings for semantic search

Use Cases:
- RFP Generation: Complex multi-factor product recommendations
- Semantic Search: Direct product similarity matching
"""

import os
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

from dotenv import load_dotenv
from pymongo import MongoClient
import certifi
import numpy as np
from openai import OpenAI, AzureOpenAI

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProductMetadata:
    """Structured metadata for product filtering and context"""
    product_id: str
    category: str
    brand: str
    price: float
    price_range: str  # "budget", "mid-range", "premium", "luxury"
    availability: str
    rating: float
    rating_tier: str  # "excellent", "good", "average", "poor"
    feature_count: int
    specification_count: int


@dataclass
class IngestionConfig:
    """Configuration for the ingestion process"""
    batch_size: int = 1
    max_workers: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 200
    working_dir: str = "./product_rag_storage"


class ProductNormalizer:
    """Handles product JSON normalization for LightRAG ingestion"""

    @staticmethod
    def categorize_price(price: float) -> str:
        """Categorize price into ranges for metadata filtering"""
        if price < 50:
            return "budget"
        elif price < 200:
            return "mid-range"
        elif price < 1000:
            return "premium"
        else:
            return "luxury"

    @staticmethod
    def categorize_rating(rating: float) -> str:
        """Categorize rating into tiers for metadata filtering"""
        if rating >= 4.5:
            return "excellent"
        elif rating >= 3.5:
            return "good"
        elif rating >= 2.5:
            return "average"
        else:
            return "poor"

    @classmethod
    def normalize_product(cls, product_json: Dict[str, Any]) -> Tuple[str, ProductMetadata]:
        """
        Convert product JSON to LightRAG-friendly text with metadata

        This creates rich, structured text that enables:
        1. Entity extraction (products, brands, categories, features)
        2. Relationship detection (product-feature, brand-category, etc.)
        3. Knowledge graph construction for complex RFP queries
        4. Effective embeddings for semantic search
        """

        # Extract core fields with defaults
        name = product_json.get('name', 'Unknown Product')
        category = product_json.get('category', 'Uncategorized')
        brand = product_json.get('brand', 'Unknown Brand')
        price = float(product_json.get('price', 0))
        description = product_json.get('description', '')
        features = product_json.get('features', [])
        specifications = product_json.get('specifications', [])
        availability = product_json.get('availability', 'Unknown')
        rating = float(product_json.get('rating', 0))

        # Create rich, structured text for LLM processing
        normalized_text = f"""Product Information:

Name: {name}
Category: {category}
Brand: {brand}
Price: ${price:,.2f}
Availability: {availability}
Customer Rating: {rating}/5.0 stars

Product Description:
{description}

Key Features:"""

        # Add features with context
        if features:
            for i, feature in enumerate(features, 1):
                normalized_text += f"\n{i}. {feature}"
        else:
            normalized_text += "\nNo specific features listed."

        normalized_text += "\n\nTechnical Specifications:"

        # Add specifications with structured format
        if specifications:
            for spec in specifications:
                if isinstance(spec, dict):
                    spec_name = spec.get('name', 'Unknown Specification')
                    spec_value = spec.get('value', 'Not specified')
                    normalized_text += f"\n- {spec_name}: {spec_value}"
                else:
                    normalized_text += f"\n- {spec}"
        else:
            normalized_text += "\nNo technical specifications provided."

        # Add contextual information for relationship extraction
        normalized_text += f"""

Product Context:
This {category.lower()} product is manufactured by {brand} and is currently {availability.lower()}. 
With a customer rating of {rating}/5.0, it represents a {cls.categorize_price(price)} option in the {category.lower()} market segment.
The product offers {len(features)} key features and {len(specifications)} technical specifications."""

        # Create metadata for filtering and context
        metadata = ProductMetadata(
            product_id=str(product_json.get('_id', 'unknown')),
            category=category,
            brand=brand,
            price=price,
            price_range=cls.categorize_price(price),
            availability=availability,
            rating=rating,
            rating_tier=cls.categorize_rating(rating),
            feature_count=len(features),
            specification_count=len(specifications)
        )

        return normalized_text, metadata


class ProductIngestionService:
    """Main service for ingesting products into LightRAG"""

    def __init__(self, config: IngestionConfig = None):
        self.config = config or IngestionConfig()
        self.normalizer = ProductNormalizer()
        self.rag: Optional[LightRAG] = None

        # Initialize clients
        self._init_mongodb_client()
        self._init_llm_and_embedding_functions()

    def _init_mongodb_client(self):
        """Initialize MongoDB client for product data source"""
        product_mongo_uri = os.getenv("PRODUCT_MONGO_URI")
        if not product_mongo_uri:
            raise ValueError(
                "PRODUCT_MONGO_URI environment variable is required")

        self.product_mongo_client = MongoClient(
            product_mongo_uri,
            tlsCAFile=certifi.where()  # Handle SSL certificate verification
        )

        # Test connection
        try:
            self.product_mongo_client.admin.command('ping')
            logger.info("✅ Connected to product MongoDB")
        except Exception as e:
            logger.error(f"❌ Failed to connect to product MongoDB: {e}")
            raise

    def _init_llm_and_embedding_functions(self):
        """Initialize LLM and embedding functions"""

        # Azure OpenAI LLM function
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

            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                messages=messages,
                temperature=kwargs.get("temperature", 0),
                max_completion_tokens=kwargs.get("max_tokens", 1000),
            )
            return response.choices[0].message.content

        # Azure embedding function
        async def azure_embedding_func(texts: List[str]) -> np.ndarray:
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_EMBEDDING_API_KEY"),
                api_version=os.getenv("AZURE_EMBEDDING_API_VERSION"),
                azure_endpoint=os.getenv("AZURE_EMBEDDING_ENDPOINT"),
            )
            response = client.embeddings.create(
                model=os.getenv("AZURE_EMBEDDING_DEPLOYMENT"),
                input=texts
            )
            embeddings = [item.embedding for item in response.data]
            return np.array(embeddings)

        self.llm_func = azure_openai_llm_func
        self.embedding_func = azure_embedding_func

    async def initialize_rag(self) -> LightRAG:
        """Initialize LightRAG instance with proper configuration"""
        if not os.path.exists(self.config.working_dir):
            os.makedirs(self.config.working_dir)

        # Create embedding function instance
        embedding_func_instance = EmbeddingFunc(
            embedding_dim=int(os.getenv("EMBEDDING_DIM", 1536)),
            max_token_size=8192,
            func=self.embedding_func,
        )

        # Initialize LightRAG with Neo4j graph storage
        self.rag = LightRAG(
            working_dir=self.config.working_dir,
            llm_model_func=self.llm_func,
            embedding_func=embedding_func_instance,
            graph_storage="Neo4jGraphStorage",  # Use Neo4j for knowledge graph
            log_level="INFO",
        )

        # Initialize storages
        await self.rag.initialize_storages()
        await initialize_pipeline_status()

        logger.info(
            f"✅ LightRAG initialized with working directory: {self.config.working_dir}")
        return self.rag

    def fetch_products(self, database: str, collection: str,
                       filter_query: Dict = None, limit: int = None) -> List[Dict]:
        """Fetch products from MongoDB"""
        db = self.product_mongo_client[database]
        coll = db[collection]

        query = filter_query or {}
        cursor = coll.find(query)

        if limit:
            cursor = cursor.limit(limit)

        products = list(cursor)
        logger.info(
            f"📦 Fetched {len(products)} products from {database}.{collection}")
        return products

    async def process_batch(self, products: List[Dict], batch_id: int) -> Dict[str, Any]:
        """Process a batch of products"""
        logger.info(
            f"🔄 Processing batch {batch_id} ({len(products)} products)")

        batch_results = {
            "batch_id": batch_id,
            "processed": 0,
            "errors": [],
            "metadata_summary": {}
        }

        # Normalize products in batch
        normalized_texts = []
        metadata_list = []

        for product in products:
            try:
                text, metadata = self.normalizer.normalize_product(product)
                normalized_texts.append(text)
                metadata_list.append(metadata)
                batch_results["processed"] += 1

            except Exception as e:
                error_info = {
                    "product_id": product.get('_id', 'unknown'),
                    "error": str(e)
                }
                batch_results["errors"].append(error_info)
                logger.warning(
                    f"⚠️  Error processing product {error_info['product_id']}: {e}")

        # Insert batch into LightRAG
        if normalized_texts:
            try:
                # Insert all normalized texts as a single batch
                combined_text = "\n\n" + "="*80 + "\n\n".join(normalized_texts)
                self.rag.insert(combined_text)

                logger.info(f"✅ Batch {batch_id} inserted into LightRAG")

            except Exception as e:
                logger.error(f"❌ Failed to insert batch {batch_id}: {e}")
                batch_results["errors"].append({"batch_error": str(e)})

        # Collect metadata summary
        categories = {}
        brands = {}
        price_ranges = {}

        for metadata in metadata_list:
            categories[metadata.category] = categories.get(
                metadata.category, 0) + 1
            brands[metadata.brand] = brands.get(metadata.brand, 0) + 1
            price_ranges[metadata.price_range] = price_ranges.get(
                metadata.price_range, 0) + 1

        batch_results["metadata_summary"] = {
            "categories": categories,
            "brands": brands,
            "price_ranges": price_ranges
        }

        return batch_results

    async def ingest_products(self, database: str, collection: str,
                              filter_query: Dict = None, limit: int = None) -> Dict[str, Any]:
        """Main ingestion method"""
        start_time = datetime.now()
        logger.info(
            f"🚀 Starting product ingestion from {database}.{collection}")

        # Initialize RAG if not already done
        if not self.rag:
            await self.initialize_rag()

        # Fetch products
        products = self.fetch_products(
            database, collection, filter_query, limit)

        if not products:
            logger.warning("No products found to ingest")
            return {"status": "completed", "total_products": 0}

        # Process in batches
        total_batches = (len(products) + self.config.batch_size -
                         1) // self.config.batch_size
        batch_results = []

        for i in range(0, len(products), self.config.batch_size):
            batch_id = i // self.config.batch_size + 1
            batch = products[i:i + self.config.batch_size]

            result = await self.process_batch(batch, batch_id)
            batch_results.append(result)

            logger.info(f"📊 Batch {batch_id}/{total_batches} completed")

        # Compile final results
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        total_processed = sum(r["processed"] for r in batch_results)
        total_errors = sum(len(r["errors"]) for r in batch_results)

        # Aggregate metadata
        all_categories = {}
        all_brands = {}
        all_price_ranges = {}

        for result in batch_results:
            summary = result["metadata_summary"]
            for cat, count in summary.get("categories", {}).items():
                all_categories[cat] = all_categories.get(cat, 0) + count
            for brand, count in summary.get("brands", {}).items():
                all_brands[brand] = all_brands.get(brand, 0) + count
            for price_range, count in summary.get("price_ranges", {}).items():
                all_price_ranges[price_range] = all_price_ranges.get(
                    price_range, 0) + count

        final_results = {
            "status": "completed",
            "duration_seconds": duration,
            "total_products": len(products),
            "total_processed": total_processed,
            "total_errors": total_errors,
            "batch_count": total_batches,
            "metadata_summary": {
                "categories": all_categories,
                "brands": all_brands,
                "price_ranges": all_price_ranges
            },
            "batch_results": batch_results
        }

        logger.info(f"🎉 Ingestion completed in {duration:.2f}s")
        logger.info(f"📈 Processed: {total_processed}, Errors: {total_errors}")

        return final_results

    async def query_for_rfp(self, requirements: str, filters: Dict = None) -> str:
        """Query for RFP generation (complex multi-factor analysis)"""
        if not self.rag:
            raise ValueError(
                "RAG not initialized. Call ingest_products first.")

        # Use hybrid mode for complex reasoning across knowledge graph and embeddings
        result = self.rag.query(
            requirements,
            param=QueryParam(mode="hybrid")
        )
        return result

    async def semantic_search(self, query: str) -> str:
        """Semantic search for direct product matching"""
        if not self.rag:
            raise ValueError(
                "RAG not initialized. Call ingest_products first.")

        # Use local mode for semantic similarity
        result = self.rag.query(
            query,
            param=QueryParam(mode="local")
        )
        return result


# Example usage and testing
async def main():
    """Example usage of the ProductIngestionService"""

    # Configuration
    config = IngestionConfig(
        batch_size=1,  # process one product at a time
        working_dir="./product_rag_test"
    )

    # Initialize service
    service = ProductIngestionService(config)

    try:
        # Test ingestion (limit to 100 products for initial testing)
        results = await service.ingest_products(
            database="your_database_name",  # Replace with your actual database name
            collection="products",          # Replace with your actual collection name
            limit=100  # Start with 100 products for testing
        )

        print(f"\n🎉 Ingestion Results:")
        print(f"Total processed: {results['total_processed']}")
        print(f"Total errors: {results['total_errors']}")
        print(f"Duration: {results['duration_seconds']:.2f}s")

        print(f"\n📊 Categories ingested:")
        for category, count in results['metadata_summary']['categories'].items():
            print(f"  - {category}: {count}")

        # Test RFP query
        rfp_query = """
        I need products for a corporate office setup that are:
        - Budget-friendly (under $200)
        - High-rated (4+ stars)
        - Currently available
        - Suitable for professional use
        """

        print(f"\n🔍 Testing RFP Query:")
        rfp_result = await service.query_for_rfp(rfp_query)
        print(rfp_result)

        # Test semantic search
        search_query = "wireless keyboard with backlight"
        print(f"\n🔎 Testing Semantic Search:")
        search_result = await service.semantic_search(search_query)
        print(search_result)

    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
