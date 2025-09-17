"""Main product ingestion service orchestrator"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..models.config import IngestionConfig
from ..clients.mongodb_client import MongoDBClient
from ..clients.lightrag_client import LightRAGClient
from ..processors.batch_processor import BatchProcessor
from ..monitoring.pipeline_integration import get_pipeline_integrator

logger = logging.getLogger(__name__)


class ProductIngestionService:
    """
    Main service orchestrator for product ingestion into LightRAG

    Coordinates all components:
    - MongoDB data access
    - Enhanced metadata extraction
    - Rich text normalization
    - Batch processing with progress tracking
    - LightRAG integration with Neo4j knowledge graph
    """

    def __init__(self, config: IngestionConfig = None):
        """Initialize the ingestion service with all components"""
        self.config = config or IngestionConfig()

        # Initialize clients
        self.mongodb_client = MongoDBClient()
        self.lightrag_client = LightRAGClient(self.config.working_dir)

        # Initialize processor with database connection for name resolution
        self.batch_processor = BatchProcessor(
            self.lightrag_client, self.mongodb_client.client.get_database('Zoftware'))

        logger.info(f"🚀 ProductIngestionService initialized")
        logger.info(f"   Working directory: {self.config.working_dir}")
        logger.info(f"   Batch size: {self.config.batch_size}")
        logger.info(f"   Max workers: {self.config.max_workers}")

    async def initialize_lightrag(self):
        """Initialize LightRAG instance"""
        await self.lightrag_client.initialize()
        logger.info("✅ LightRAG initialized successfully")

    def get_collection_stats(self, database: str, collection: str) -> Dict[str, Any]:
        """Get statistics about the source collection"""
        return self.mongodb_client.get_collection_stats(database, collection)

    def get_sample_product(self, database: str, collection: str) -> Optional[Dict[str, Any]]:
        """Get a sample product for validation"""
        return self.mongodb_client.get_sample_product(database, collection)

    async def ingest_products(self,
                              database: str,
                              collection: str,
                              filter_query: Optional[Dict[str, Any]] = None,
                              limit: Optional[int] = None,
                              skip: int = 0) -> Dict[str, Any]:
        """
        Main ingestion method with comprehensive processing pipeline

        Args:
            database: MongoDB database name
            collection: MongoDB collection name
            filter_query: Optional MongoDB query filter
            limit: Optional limit on number of products to process
            skip: Number of products to skip

        Returns:
            Comprehensive ingestion results with metadata analysis
        """
        start_time = datetime.now()
        logger.info(
            f"🚀 Starting product ingestion from {database}.{collection}")

        if limit:
            logger.info(f"   Processing limit: {limit} products")
        if filter_query:
            logger.info(f"   Applied filter: {filter_query}")

        # Initialize LightRAG if not already done
        await self.initialize_lightrag()

        # Fetch products from MongoDB
        try:
            products = self.mongodb_client.fetch_products(
                database=database,
                collection=collection,
                filter_query=filter_query,
                limit=limit,
                skip=skip
                # Remove sort to avoid MongoDB memory limit with large collections
            )
        except Exception as e:
            logger.error(f"❌ Failed to fetch products: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "total_products": 0
            }

        if not products:
            logger.warning("No products found to ingest")
            return {
                "status": "completed",
                "total_products": 0,
                "message": "No products found matching criteria"
            }

        # Process products in batches
        total_batches = (len(products) + self.config.batch_size -
                         1) // self.config.batch_size
        batch_results = []

        logger.info(
            f"📦 Processing {len(products)} products in {total_batches} batches")

        # Debug: Check first few products
        for idx, product in enumerate(products[:3]):
            logger.info(f"🔍 Product {idx+1} type: {type(product)}")
            if isinstance(product, dict):
                logger.info(
                    f"    Product name: {product.get('product_name', 'N/A')}")
            else:
                logger.info(f"    Product value: {str(product)[:100]}...")

        for i in range(0, len(products), self.config.batch_size):
            batch_id = i // self.config.batch_size + 1
            batch = products[i:i + self.config.batch_size]

            try:
                # Process batch
                result = await self.batch_processor.process_batch(batch, batch_id)
                batch_results.append(result)

                # Progress reporting
                progress = (batch_id / total_batches) * 100
                logger.info(
                    f"📊 Batch {batch_id}/{total_batches} completed ({progress:.1f}%)")

                # Optional memory cleanup
                if self.config.clear_cache_after_batch:
                    await asyncio.sleep(0.1)  # Brief pause for memory cleanup

            except Exception as e:
                logger.error(f"❌ Failed to process batch {batch_id}: {e}")
                batch_results.append({
                    "batch_id": batch_id,
                    "processed": 0,
                    "errors": [{"batch_error": str(e)}],
                    "metadata_summary": {}
                })

        # Compile comprehensive results
        final_results = self._compile_final_results(
            products, batch_results, start_time
        )

        # Log final summary
        self._log_final_summary(final_results)

        return final_results

    def _compile_final_results(self,
                               products: List[Dict[str, Any]],
                               batch_results: List[Dict[str, Any]],
                               start_time: datetime) -> Dict[str, Any]:
        """Compile comprehensive final results"""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Aggregate basic statistics
        total_processed = sum(r.get("processed", 0) for r in batch_results)
        total_errors = sum(len(r.get("errors", [])) for r in batch_results)

        # Aggregate metadata summaries
        aggregated_metadata = self._aggregate_metadata_summaries(batch_results)

        # Compile error analysis
        error_analysis = self._compile_error_analysis(batch_results)

        # Performance metrics
        performance_metrics = {
            "duration_seconds": duration,
            "products_per_second": total_processed / duration if duration > 0 else 0,
            "average_batch_time": duration / len(batch_results) if batch_results else 0,
            "success_rate": (total_processed / len(products)) * 100 if products else 0
        }

        return {
            "status": "completed",
            "timestamp": end_time.isoformat(),
            "duration_seconds": duration,
            "total_products": len(products),
            "total_processed": total_processed,
            "total_errors": total_errors,
            "batch_count": len(batch_results),
            "performance_metrics": performance_metrics,
            "metadata_summary": aggregated_metadata,
            "error_analysis": error_analysis,
            "batch_results": batch_results
        }

    def _aggregate_metadata_summaries(self, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate metadata summaries across all batches"""
        from collections import defaultdict

        # Initialize aggregated counters
        all_categories = defaultdict(int)
        all_companies = defaultdict(int)
        all_price_ranges = defaultdict(int)
        all_rating_tiers = defaultdict(int)
        all_market_positions = defaultdict(int)
        all_feature_richness = defaultdict(int)
        all_industries = defaultdict(int)

        # Aggregate statistics
        total_reviews = 0
        total_rating_sum = 0.0
        total_rated_products = 0
        total_features = 0
        total_integrations = 0

        for result in batch_results:
            summary = result.get("metadata_summary", {})

            # Aggregate distributions
            for category, count in summary.get("categories", {}).items():
                all_categories[category] += count
            for company, count in summary.get("companies", {}).items():
                all_companies[company] += count
            for price_range, count in summary.get("price_ranges", {}).items():
                all_price_ranges[price_range] += count
            for rating_tier, count in summary.get("rating_tiers", {}).items():
                all_rating_tiers[rating_tier] += count
            for market_pos, count in summary.get("market_positions", {}).items():
                all_market_positions[market_pos] += count
            for feature_rich, count in summary.get("feature_richness", {}).items():
                all_feature_richness[feature_rich] += count
            for industry, count in summary.get("industries", {}).items():
                all_industries[industry] += count

            # Aggregate statistics
            stats = summary.get("statistics", {})
            total_reviews += stats.get("total_reviews", 0)
            total_rated_products += stats.get("products_with_ratings", 0)

            # For averages, we need to weight by number of products
            batch_products = result.get("processed", 0)
            if batch_products > 0:
                avg_rating = stats.get("average_rating", 0)
                total_rating_sum += avg_rating * \
                    stats.get("products_with_ratings", 0)

        # Calculate final averages
        overall_avg_rating = total_rating_sum / \
            total_rated_products if total_rated_products > 0 else 0.0

        return {
            "categories": dict(all_categories),
            "companies": dict(all_companies),
            "price_ranges": dict(all_price_ranges),
            "rating_tiers": dict(all_rating_tiers),
            "market_positions": dict(all_market_positions),
            "feature_richness": dict(all_feature_richness),
            "industries": dict(all_industries),
            "overall_statistics": {
                "total_reviews": total_reviews,
                "products_with_ratings": total_rated_products,
                "average_rating": round(overall_avg_rating, 2),
                "unique_categories": len(all_categories),
                "unique_companies": len(all_companies),
                "unique_industries": len(all_industries)
            }
        }

    def _compile_error_analysis(self, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compile error analysis across all batches"""
        from collections import defaultdict

        error_types = defaultdict(int)
        all_errors = []

        for result in batch_results:
            errors = result.get("errors", [])
            for error in errors:
                error_type = error.get("error_type", "unknown")
                error_types[error_type] += 1
                all_errors.append({
                    "batch_id": result.get("batch_id"),
                    "error": error
                })

        return {
            "total_errors": len(all_errors),
            "error_types": dict(error_types),
            "error_details": all_errors[:10]  # First 10 errors for debugging
        }

    def _log_final_summary(self, results: Dict[str, Any]):
        """Log comprehensive final summary"""
        logger.info("🎉 Product ingestion completed!")
        logger.info(f"📊 Final Results:")
        logger.info(f"   Duration: {results['duration_seconds']:.2f}s")
        logger.info(f"   Total Products: {results['total_products']}")
        logger.info(f"   Successfully Processed: {results['total_processed']}")
        logger.info(f"   Errors: {results['total_errors']}")
        logger.info(
            f"   Success Rate: {results['performance_metrics']['success_rate']:.1f}%")
        logger.info(
            f"   Throughput: {results['performance_metrics']['products_per_second']:.2f} products/sec")

        # Log top categories and companies
        metadata = results.get('metadata_summary', {})
        if metadata.get('categories'):
            top_categories = sorted(
                metadata['categories'].items(), key=lambda x: x[1], reverse=True)[:5]
            logger.info(
                f"📈 Top Categories: {', '.join([f'{cat}({count})' for cat, count in top_categories])}")

        if metadata.get('companies'):
            top_companies = sorted(
                metadata['companies'].items(), key=lambda x: x[1], reverse=True)[:5]
            logger.info(
                f"🏢 Top Companies: {', '.join([f'{comp}({count})' for comp, count in top_companies])}")

    async def query_for_rfp(self, requirements: str, **kwargs) -> str:
        """Query for RFP generation using hybrid mode"""
        return await self.lightrag_client.query_rfp(requirements, **kwargs)

    async def semantic_search(self, query: str, **kwargs) -> str:
        """Query for semantic search using local mode"""
        return await self.lightrag_client.query_semantic(query, **kwargs)

    async def custom_query(self, query: str, mode: str = "mix", **kwargs) -> str:
        """Custom query with specified mode"""
        return await self.lightrag_client.query_custom(query, mode, **kwargs)

    def close(self):
        """Clean up resources"""
        self.mongodb_client.close()
        logger.info("🔒 ProductIngestionService resources cleaned up")
