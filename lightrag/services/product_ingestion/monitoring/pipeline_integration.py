"""Pipeline status integration for product ingestion monitoring"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class PipelineStatusIntegrator:
    """
    Integrates product ingestion service with LightRAG's existing pipeline status system.

    This allows monitoring large batch processing jobs (8000+ records) through the web UI
    without needing terminal monitoring.
    """

    def __init__(self):
        self.pipeline_status = None
        self.pipeline_status_lock = None
        self._initialized = False

    async def initialize(self):
        """Initialize connection to LightRAG's pipeline status system"""
        try:
            # Import LightRAG's pipeline status system
            from lightrag.kg.shared_storage import get_namespace_data, get_pipeline_status_lock

            self.pipeline_status = await get_namespace_data("pipeline_status")
            self.pipeline_status_lock = get_pipeline_status_lock()
            self._initialized = True

            logger.info("✅ Pipeline status integrator initialized")
            return True

        except ImportError as e:
            logger.warning(
                f"⚠️  Could not import LightRAG pipeline status system: {e}")
            logger.info(
                "📋 Running in standalone mode - status will be logged only")
            return False
        except Exception as e:
            logger.error(
                f"❌ Failed to initialize pipeline status integration: {e}")
            return False

    @asynccontextmanager
    async def monitor_job(self, job_name: str, total_records: int, batch_size: int = 25):
        """
        Context manager for monitoring a large batch processing job

        Args:
            job_name: Name of the job (e.g., "Product Ingestion - RFP Dataset")
            total_records: Total number of records to process
            batch_size: Size of each batch

        Usage:
            async with integrator.monitor_job("Product Ingestion", 8000) as monitor:
                for batch_id in range(1, total_batches + 1):
                    # Process batch
                    await monitor.update_progress(batch_id, f"Processing batch {batch_id}")
        """
        total_batches = (total_records + batch_size - 1) // batch_size
        start_time = datetime.now()

        # Initialize job status
        await self._set_job_status(
            busy=True,
            job_name=job_name,
            job_start=start_time,
            docs=total_records,
            batchs=total_batches,
            cur_batch=0,
            latest_message=f"Starting {job_name} - {total_records} records in {total_batches} batches"
        )

        monitor = JobMonitor(self, job_name, total_batches, start_time)

        try:
            yield monitor

            # Job completed successfully
            await self._set_job_status(
                busy=False,
                latest_message=f"✅ {job_name} completed successfully - {total_records} records processed"
            )

        except Exception as e:
            # Job failed
            await self._set_job_status(
                busy=False,
                latest_message=f"❌ {job_name} failed: {str(e)}"
            )
            raise

    async def _set_job_status(self, **status_updates):
        """Update pipeline status with new information"""
        if not self._initialized:
            # Log status updates when not integrated
            logger.info(f"📊 Job Status Update: {status_updates}")
            return

        try:
            async with self.pipeline_status_lock:
                # Update status
                for key, value in status_updates.items():
                    if key == "job_start" and isinstance(value, datetime):
                        # Convert datetime to ISO string
                        self.pipeline_status[key] = value.isoformat()
                    else:
                        self.pipeline_status[key] = value

                # Add to history if we have a message
                if "latest_message" in status_updates:
                    message = status_updates["latest_message"]
                    if "history_messages" not in self.pipeline_status:
                        self.pipeline_status["history_messages"] = []

                    # Add timestamp to message
                    timestamped_message = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
                    self.pipeline_status["history_messages"].append(
                        timestamped_message)

                    # Keep only last 1000 messages to prevent memory issues
                    if len(self.pipeline_status["history_messages"]) > 1000:
                        self.pipeline_status["history_messages"] = self.pipeline_status["history_messages"][-1000:]

        except Exception as e:
            logger.error(f"❌ Failed to update pipeline status: {e}")


class JobMonitor:
    """Monitor for individual batch processing jobs"""

    def __init__(self, integrator: PipelineStatusIntegrator, job_name: str, total_batches: int, start_time: datetime):
        self.integrator = integrator
        self.job_name = job_name
        self.total_batches = total_batches
        self.start_time = start_time
        self.current_batch = 0

    async def update_progress(self, batch_id: int, message: str = None, **extra_data):
        """
        Update job progress

        Args:
            batch_id: Current batch being processed
            message: Optional status message
            **extra_data: Additional data to include in status
        """
        self.current_batch = batch_id
        progress_percent = (batch_id / self.total_batches) * 100

        # Default message if none provided
        if not message:
            message = f"Processing batch {batch_id}/{self.total_batches} ({progress_percent:.1f}%)"

        # Calculate estimated time remaining
        elapsed_time = datetime.now() - self.start_time
        if batch_id > 0:
            avg_time_per_batch = elapsed_time.total_seconds() / batch_id
            remaining_batches = self.total_batches - batch_id
            eta_seconds = remaining_batches * avg_time_per_batch
            eta_message = f" - ETA: {int(eta_seconds//60)}m {int(eta_seconds % 60)}s"
        else:
            eta_message = ""

        full_message = f"{message}{eta_message}"

        # Update status
        status_update = {
            "cur_batch": batch_id,
            "latest_message": full_message,
            **extra_data
        }

        await self.integrator._set_job_status(**status_update)

        # Also log for terminal users
        logger.info(f"📊 {full_message}")

    async def add_message(self, message: str):
        """Add a message to the status history without updating progress"""
        await self.integrator._set_job_status(latest_message=message)
        logger.info(f"📝 {message}")

    async def report_batch_results(self, batch_results: Dict[str, Any]):
        """Report detailed batch processing results"""
        batch_id = batch_results.get("batch_id", "unknown")
        processed = batch_results.get("processed", 0)
        errors = len(batch_results.get("errors", []))
        duration = batch_results.get("duration_seconds", 0)

        message = f"Batch {batch_id}: {processed} processed, {errors} errors, {duration:.1f}s"

        # Include metadata summary if available
        metadata_summary = batch_results.get("metadata_summary", {})
        if metadata_summary:
            total_products = metadata_summary.get("total_products", 0)
            avg_rating = metadata_summary.get(
                "statistics", {}).get("average_rating", 0)
            if avg_rating > 0:
                message += f", avg rating: {avg_rating}"

        await self.add_message(message)


# Global instance for easy access
pipeline_integrator = PipelineStatusIntegrator()


async def get_pipeline_integrator() -> PipelineStatusIntegrator:
    """Get the global pipeline integrator instance"""
    if not pipeline_integrator._initialized:
        await pipeline_integrator.initialize()
    return pipeline_integrator
