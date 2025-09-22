"""Main product ingestion service orchestrator"""

import logging
import asyncio
import json
import os
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
    - Retry logic and resume capability
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

        # Progress tracking
        self.progress_file = os.path.join(
            self.config.working_dir, "ingestion_progress.json")
        self.checkpoint_file = os.path.join(
            self.config.working_dir, "ingestion_checkpoint.json")

        logger.info(f"🚀 ProductIngestionService initialized")
        logger.info(f"   Working directory: {self.config.working_dir}")
        logger.info(f"   Batch size: {self.config.batch_size}")
        logger.info(f"   Max workers: {self.config.max_workers}")
        logger.info(
            f"   Job timeout: {self.config.job_timeout_minutes} minutes")
        logger.info(f"   Auto-resume: {self.config.enable_auto_resume}")

    async def initialize_lightrag(self):
        """Initialize LightRAG instance"""
        await self.lightrag_client.initialize()
        logger.info("✅ LightRAG initialized successfully")

    def get_collection_stats(self, database: str, collection: str) -> Dict[str, Any]:
        """Get collection statistics"""
        return self.mongodb_client.get_collection_stats(database, collection)

    def _load_progress(self) -> Dict[str, Any]:
        """Load progress from file"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load progress file: {e}")
        return {"completed_batches": 0, "total_batches": 0, "start_time": None}

    def _save_progress(self, progress: Dict[str, Any]):
        """Save progress to file"""
        try:
            os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
            with open(self.progress_file, 'w') as f:
                json.dump(progress, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save progress: {e}")

    def _load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint data"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load checkpoint: {e}")
        return {}

    def _save_checkpoint(self, checkpoint: Dict[str, Any]):
        """Save checkpoint data"""
        try:
            os.makedirs(os.path.dirname(self.checkpoint_file), exist_ok=True)
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save checkpoint: {e}")

    async def ingest_products(self,
                              database: str,
                              collection: str,
                              filter_query: Optional[Dict[str, Any]] = None,
                              limit: Optional[int] = None,
                              skip: int = 0,
                              resume_from_checkpoint: bool = True) -> Dict[str, Any]:
        """
        Enhanced product ingestion with retry logic and resume capability

        Args:
            database: MongoDB database name
            collection: MongoDB collection name
            filter_query: Optional filter query
            limit: Optional limit on products
            skip: Number of products to skip
            resume_from_checkpoint: Whether to resume from previous checkpoint
        """
        start_time = datetime.now()

        # Load previous progress if resuming
        progress = self._load_progress() if resume_from_checkpoint else {
            "completed_batches": 0, "total_batches": 0, "start_time": None}

        if progress.get("start_time") and resume_from_checkpoint:
            logger.info(
                f"🔄 Resuming ingestion from batch {progress['completed_batches'] + 1}")
            logger.info(f"   Previous session: {progress['start_time']}")
        else:
            logger.info(
                f"🚀 Starting new product ingestion from {database}.{collection}")
            progress["start_time"] = start_time.isoformat()

        # Fetch products
        products = self.mongodb_client.fetch_products(
            database, collection, filter_query, limit, skip
        )

        if not products:
            logger.warning("No products found to ingest")
            return {"status": "completed", "total_products": 0}

        # Calculate total batches
        total_batches = (len(products) + self.config.batch_size -
                         1) // self.config.batch_size
        progress["total_batches"] = total_batches

        # Determine starting batch
        start_batch = progress.get(
            "completed_batches", 0) + 1 if resume_from_checkpoint else 1

        logger.info(f"📊 Total products: {len(products)}")
        logger.info(f"📊 Total batches: {total_batches}")
        logger.info(f"📊 Starting from batch: {start_batch}")
        logger.info(f"📊 Batch size: {self.config.batch_size}")

        # Load checkpoint data if resuming
        checkpoint_data = self._load_checkpoint() if resume_from_checkpoint else {}
        batch_results = checkpoint_data.get("batch_results", [])

        # Track consecutive failures
        consecutive_failures = 0

        # Process batches with retry logic
        for i in range(start_batch - 1, total_batches):
            batch_id = i + 1
            batch_start_idx = i * self.config.batch_size
            batch = products[batch_start_idx:batch_start_idx +
                             self.config.batch_size]

            logger.info(
                f"🔄 Processing batch {batch_id}/{total_batches} ({len(batch)} products)")

            # Retry logic for individual batches
            batch_success = False
            for retry_attempt in range(self.config.max_retries):
                try:
                    # Set timeout for individual batch
                    batch_timeout = self.config.batch_timeout_minutes * 60

                    result = await asyncio.wait_for(
                        self.batch_processor.process_batch(batch, batch_id),
                        timeout=batch_timeout
                    )

                    batch_results.append(result)
                    batch_success = True
                    consecutive_failures = 0  # Reset failure counter

                    # Update progress
                    progress["completed_batches"] = batch_id
                    self._save_progress(progress)

                    # Save checkpoint every N batches
                    if batch_id % self.config.checkpoint_interval == 0:
                        checkpoint_data = {
                            "batch_results": batch_results,
                            "last_checkpoint": batch_id,
                            "timestamp": datetime.now().isoformat()
                        }
                        self._save_checkpoint(checkpoint_data)
                        logger.info(f"💾 Checkpoint saved at batch {batch_id}")

                    # Progress reporting
                    progress_percent = (batch_id / total_batches) * 100
                    logger.info(
                        f"📊 Batch {batch_id}/{total_batches} completed ({progress_percent:.1f}%)")

                    break  # Success, exit retry loop

                except asyncio.TimeoutError:
                    consecutive_failures += 1
                    logger.warning(
                        f"⏰ Batch {batch_id} timed out (attempt {retry_attempt + 1}/{self.config.max_retries})")

                    if retry_attempt < self.config.max_retries - 1:
                        wait_time = self.config.retry_delay * \
                            (2 ** retry_attempt)  # Exponential backoff
                        logger.info(
                            f"⏳ Retrying batch {batch_id} in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"❌ Batch {batch_id} failed after {self.config.max_retries} attempts")
                        batch_results.append({
                            "batch_id": batch_id,
                            "processed": 0,
                            "errors": [{"batch_error": f"Timeout after {self.config.max_retries} attempts", "error_type": "TimeoutError"}],
                            "metadata_summary": {}
                        })

                except Exception as e:
                    consecutive_failures += 1
                    logger.error(
                        f"❌ Batch {batch_id} failed (attempt {retry_attempt + 1}/{self.config.max_retries}): {e}")

                    if retry_attempt < self.config.max_retries - 1:
                        wait_time = self.config.retry_delay * \
                            (2 ** retry_attempt)
                        logger.info(
                            f"⏳ Retrying batch {batch_id} in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        batch_results.append({
                            "batch_id": batch_id,
                            "processed": 0,
                            "errors": [{"batch_error": str(e), "error_type": type(e).__name__}],
                            "metadata_summary": {}
                        })

            # Check for too many consecutive failures
            if consecutive_failures >= self.config.max_consecutive_failures:
                logger.error(
                    f"🛑 Stopping ingestion after {consecutive_failures} consecutive failures")
                break

            # Optional memory cleanup
            if self.config.clear_cache_after_batch:
                await asyncio.sleep(0.1)

        # Compile comprehensive results
        final_results = self._compile_final_results(
            products, batch_results, start_time, progress
        )

        # Log final summary
        self._log_final_summary(final_results)

        # Clean up checkpoint files on successful completion
        if final_results.get("status") == "completed":
            try:
                if os.path.exists(self.progress_file):
                    os.remove(self.progress_file)
                if os.path.exists(self.checkpoint_file):
                    os.remove(self.checkpoint_file)
                logger.info("🧹 Cleaned up checkpoint files")
            except Exception as e:
                logger.warning(f"Could not clean up checkpoint files: {e}")

        return final_results

    def _compile_final_results(self,
                               products: List[Dict[str, Any]],
                               batch_results: List[Dict[str, Any]],
                               start_time: datetime,
                               progress: Dict[str, Any]) -> Dict[str, Any]:
        """Compile comprehensive results with progress information"""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        total_processed = sum(r.get("processed", 0) for r in batch_results)
        total_errors = sum(len(r.get("errors", [])) for r in batch_results)
        successful_batches = len(
            [r for r in batch_results if r.get("processed", 0) > 0])
        failed_batches = len(batch_results) - successful_batches

        # Determine status
        if failed_batches == 0:
            status = "completed"
        elif successful_batches > 0:
            status = "partial_success"
        else:
            status = "failed"

        return {
            "status": status,
            "total_products": len(products),
            "total_batches": progress.get("total_batches", 0),
            "completed_batches": progress.get("completed_batches", 0),
            "successful_batches": successful_batches,
            "failed_batches": failed_batches,
            "total_processed": total_processed,
            "total_errors": total_errors,
            "duration_seconds": duration,
            "duration_minutes": duration / 60,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "batch_results": batch_results,
            "can_resume": status in ["partial_success", "failed"] and progress.get("completed_batches", 0) > 0
        }

    def _log_final_summary(self, results: Dict[str, Any]):
        """Log comprehensive final summary"""
        logger.info(f"\n{'='*80}")
        logger.info(f"🎉 PRODUCT INGESTION SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"   Status: {results['status'].upper()}")
        logger.info(f"   Total Products: {results['total_products']:,}")
        logger.info(
            f"   Completed Batches: {results['completed_batches']}/{results['total_batches']}")
        logger.info(f"   Successful Batches: {results['successful_batches']}")
        logger.info(f"   Failed Batches: {results['failed_batches']}")
        logger.info(f"   Total Processed: {results['total_processed']:,}")
        logger.info(f"   Total Errors: {results['total_errors']}")
        logger.info(f"   Duration: {results['duration_minutes']:.1f} minutes")
        logger.info(f"   Can Resume: {results.get('can_resume', False)}")
        logger.info(f"{'='*80}")

    def cleanup(self):
        """Clean up resources"""
        try:
            self.mongodb_client.close()
            logger.info("🔒 ProductIngestionService resources cleaned up")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
