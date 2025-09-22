#!/usr/bin/env python3
"""
Script to restart product ingestion with enhanced retry logic and resume capability.
This script demonstrates how to use the new resilient ingestion system.
"""

import asyncio
import logging
from lightrag.services.product_ingestion.core.service import ProductIngestionService
from lightrag.services.product_ingestion.models.config import IngestionConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to restart ingestion with enhanced configuration"""

    # Create enhanced configuration
    config = IngestionConfig(
        batch_size=5,  # Small batches for reliability
        job_timeout_minutes=180,  # 3 hours (was 30 minutes)
        batch_timeout_minutes=15,  # 15 minutes per batch
        enable_auto_resume=True,  # Enable resume capability
        max_retries=3,  # Retry failed batches 3 times
        retry_delay=2.0,  # 2 seconds base delay
        max_consecutive_failures=5,  # Stop after 5 consecutive failures
        checkpoint_interval=10,  # Save progress every 10 batches
        working_dir="./rag_storage"  # Same as main server
    )

    # Create service
    service = ProductIngestionService(config)

    try:
        # Initialize LightRAG
        await service.initialize_lightrag()

        # Start ingestion with resume capability
        logger.info("🚀 Starting enhanced product ingestion...")
        logger.info(f"   Job timeout: {config.job_timeout_minutes} minutes")
        logger.info(
            f"   Batch timeout: {config.batch_timeout_minutes} minutes")
        logger.info(f"   Auto-resume: {config.enable_auto_resume}")
        logger.info(f"   Max retries: {config.max_retries}")

        results = await service.ingest_products(
            database="Zoftware",
            collection="Products",
            filter_query={"is_active": True},  # Only active products
            limit=None,  # Process all products
            skip=0,
            resume_from_checkpoint=True  # Enable resume from checkpoint
        )

        # Print results
        logger.info(f"\n{'='*60}")
        logger.info(f"INGESTION RESULTS")
        logger.info(f"{'='*60}")
        logger.info(f"Status: {results['status']}")
        logger.info(f"Total Products: {results['total_products']:,}")
        logger.info(
            f"Completed Batches: {results['completed_batches']}/{results['total_batches']}")
        logger.info(f"Successful Batches: {results['successful_batches']}")
        logger.info(f"Failed Batches: {results['failed_batches']}")
        logger.info(f"Total Processed: {results['total_processed']:,}")
        logger.info(f"Duration: {results['duration_minutes']:.1f} minutes")
        logger.info(f"Can Resume: {results.get('can_resume', False)}")

        if results.get('can_resume'):
            logger.info(
                f"\n💡 To resume: Run this script again - it will continue from batch {results['completed_batches'] + 1}")

    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}")
        logger.info(f"💡 Check the logs and restart - progress has been saved")

    finally:
        # Cleanup
        service.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
