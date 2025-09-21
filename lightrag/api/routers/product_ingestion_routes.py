"""API routes for product ingestion monitoring and control"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from bson import ObjectId

logger = logging.getLogger(__name__)

# Add project root to Python path once at module level for efficient imports
_current_file = Path(__file__)
_project_root = _current_file.parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def sanitize_mongodb_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB ObjectIds to strings for JSON serialization"""
    if doc is None:
        return None

    sanitized = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            sanitized[key] = str(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_mongodb_document(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_mongodb_document(item) if isinstance(item, dict)
                else str(item) if isinstance(item, ObjectId)
                else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


class ProductIngestionRequest(BaseModel):
    """Request model for product ingestion"""
    database: str = Field(description="MongoDB database name")
    collection: str = Field(description="MongoDB collection name")
    filter_query: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional MongoDB query filter"
    )
    limit: Optional[int] = Field(
        default=None, description="Optional limit on number of products to process (None = process all products)"
    )
    skip: int = Field(default=0, description="Number of products to skip")
    batch_size: int = Field(
        default=25, description="Batch size for processing")
    working_dir: str = Field(
        default="./rag_storage", description="Working directory for LightRAG (same as main server)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "database": "product_db",
                "collection": "products",
                "filter_query": {"is_active": True},
                "limit": None,
                "skip": 0,
                "batch_size": 25,
                "working_dir": "./rag_storage"
            }
        }


class ProductIngestionResponse(BaseModel):
    """Response model for product ingestion"""
    job_id: str = Field(description="Unique job identifier")
    status: str = Field(description="Job status (started/failed)")
    message: str = Field(description="Status message")
    estimated_batches: Optional[int] = Field(
        default=None, description="Estimated number of batches"
    )
    job_start: str = Field(description="Job start time")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "product_ingestion_20250917_143022",
                "status": "started",
                "message": "Product ingestion job started successfully",
                "estimated_batches": 320,
                "job_start": "2025-09-17T14:30:22.123456"
            }
        }


class CollectionStatsRequest(BaseModel):
    """Request model for collection statistics"""
    database: str = Field(description="MongoDB database name")
    collection: str = Field(description="MongoDB collection name")


class CollectionStatsResponse(BaseModel):
    """Response model for collection statistics"""
    database: str = Field(description="Database name")
    collection: str = Field(description="Collection name")
    total_documents: int = Field(description="Total number of documents")
    sample_product: Optional[Dict[str, Any]] = Field(
        default=None, description="Sample product for validation"
    )
    estimated_batches: int = Field(
        description="Estimated batches for processing")

    class Config:
        json_schema_extra = {
            "example": {
                "database": "product_db",
                "collection": "products",
                "total_documents": 8247,
                "sample_product": {
                    "product_name": "Salesforce CRM",
                    "company": "Salesforce",
                    "categories": ["CRM", "Sales"]
                },
                "estimated_batches": 330
            }
        }


def create_product_ingestion_routes(api_key: Optional[str] = None):
    """Create product ingestion API routes"""
    router = APIRouter(prefix="/product_ingestion", tags=["Product Ingestion"])

    # No auth dependency for webui - remove auth requirements
    # Store for running jobs
    running_jobs: Dict[str, Dict[str, Any]] = {}

    @router.get(
        "/stats",
        response_model=CollectionStatsResponse
    )
    async def get_collection_stats(
        database: str,
        collection: str
    ) -> CollectionStatsResponse:
        """
        Get statistics about a MongoDB collection for ingestion planning.

        This endpoint helps you understand the size and structure of your data
        before starting a large batch processing job.
        """
        try:
            # Import here to avoid circular imports
            from services.product_ingestion.clients.mongodb_client import MongoDBClient

            mongodb_client = MongoDBClient()

            # Get collection stats
            stats = mongodb_client.get_collection_stats(database, collection)
            sample_product = mongodb_client.get_sample_product(
                database, collection)

            total_docs = stats.get("total_documents", 0)
            # Default batch size of 25
            estimated_batches = (total_docs + 24) // 25

            mongodb_client.close()

            return CollectionStatsResponse(
                database=database,
                collection=collection,
                total_documents=total_docs,
                sample_product=sanitize_mongodb_document(sample_product),
                estimated_batches=estimated_batches
            )

        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get collection statistics: {str(e)}"
            )

    @router.post(
        "/start",
        response_model=ProductIngestionResponse
    )
    async def start_product_ingestion(
        request: ProductIngestionRequest,
        background_tasks: BackgroundTasks
    ) -> ProductIngestionResponse:
        """
        Start a product ingestion job with web UI monitoring.

        This endpoint starts a background job that processes products from MongoDB
        and ingests them into LightRAG. The job progress can be monitored through
        the web UI pipeline status dialog.

        For large datasets (8000+ records), the job will:
        - Process products in configurable batches
        - Update progress in real-time through the web UI
        - Provide detailed error reporting
        - Calculate ETAs and throughput metrics
        """
        try:
            # Generate unique job ID
            job_id = f"product_ingestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            job_start = datetime.now()

            # Import here to avoid circular imports
            from services.product_ingestion.core.service import ProductIngestionService
            from services.product_ingestion.models.config import IngestionConfig

            # Create ingestion config
            config = IngestionConfig(
                batch_size=request.batch_size,
                working_dir=request.working_dir
            )

            # Create service instance
            service = ProductIngestionService(config)

            # Initialize LightRAG with our enhancements
            await service.initialize_lightrag()

            # Estimate job size for response
            try:
                stats = service.get_collection_stats(
                    request.database, request.collection)
                # Use active_products count if available, otherwise total_documents
                total_docs = stats.get(
                    "active_products", stats.get("total_documents", 0))
                if request.limit:
                    total_docs = min(total_docs, request.limit)
                estimated_batches = (
                    total_docs + request.batch_size - 1) // request.batch_size if total_docs > 0 else 0
            except Exception as e:
                logger.warning(f"Could not estimate job size: {e}")
                estimated_batches = None

            # Store job info
            running_jobs[job_id] = {
                "request": request.dict(),
                "start_time": job_start,
                "status": "running"
            }

            # Start background task
            background_tasks.add_task(
                run_ingestion_job,
                job_id,
                service,
                request,
                running_jobs
            )

            logger.info(f"Started product ingestion job: {job_id}")

            return ProductIngestionResponse(
                job_id=job_id,
                status="started",
                message=f"Product ingestion job {job_id} started successfully",
                estimated_batches=estimated_batches,
                job_start=job_start.isoformat()
            )

        except Exception as e:
            logger.error(f"Failed to start product ingestion: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start product ingestion: {str(e)}"
            )

    @router.get(
        "/jobs"
    )
    async def list_jobs() -> Dict[str, Any]:
        """
        List all product ingestion jobs and their status.
        """
        return {
            "jobs": running_jobs,
            "total_jobs": len(running_jobs)
        }

    @router.get(
        "/jobs/{job_id}"
    )
    async def get_job_status(job_id: str):
        """Get the status of a specific ingestion job"""
        if job_id not in running_jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        return {"job_id": job_id, **running_jobs[job_id]}

    @router.post("/cancel/{job_id}")
    async def cancel_ingestion_job(job_id: str):
        """Cancel a running ingestion job"""
        if job_id not in running_jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        job = running_jobs[job_id]
        if job["status"] not in ["running"]:
            raise HTTPException(
                status_code=400, detail=f"Job is not running (status: {job['status']})")

        # Update job status to cancelled
        running_jobs[job_id].update({
            "status": "cancelled",
            "error": "Job cancelled by user",
            "end_time": datetime.now()
        })

        logger.info(f"Product ingestion job {job_id} cancelled by user")

        return {"message": f"Job {job_id} cancelled", "job_id": job_id}

    return router


async def run_ingestion_job(
    job_id: str,
    service,
    request: ProductIngestionRequest,
    running_jobs: Dict[str, Dict[str, Any]]
):
    """Background task to run product ingestion"""
    try:
        logger.info(f"🚀 Running product ingestion job {job_id}")
        logger.info(f"   Database: {request.database}")
        logger.info(f"   Collection: {request.collection}")
        logger.info(f"   Limit: {request.limit}")
        logger.info(f"   Working Directory: {request.working_dir}")

        # Run the ingestion with timeout protection
        try:
            # 30 minute timeout for the entire ingestion job
            timeout_seconds = 30 * 60  # 30 minutes
            logger.info(f"   ⏰ Job timeout: {timeout_seconds//60} minutes")

            results = await asyncio.wait_for(
                service.ingest_products(
                    database=request.database,
                    collection=request.collection,
                    filter_query=request.filter_query,
                    limit=request.limit,
                    skip=request.skip
                ),
                timeout=timeout_seconds
            )

            # Update job status
            running_jobs[job_id].update({
                "status": "completed",
                "results": results,
                "end_time": datetime.now()
            })

            logger.info(
                f"Product ingestion job {job_id} completed successfully")

        except asyncio.TimeoutError:
            logger.error(
                f"Product ingestion job {job_id} timed out after {timeout_seconds//60} minutes")

            # Update job status with timeout error
            running_jobs[job_id].update({
                "status": "failed",
                "error": f"Job timed out after {timeout_seconds//60} minutes - likely LLM processing issue",
                "end_time": datetime.now()
            })

    except Exception as e:
        logger.error(f"Product ingestion job {job_id} failed: {e}")

        # Update job status with error
        running_jobs[job_id].update({
            "status": "failed",
            "error": str(e),
            "end_time": datetime.now()
        })

    finally:
        # Clean up service resources
        try:
            service.close()
        except:
            pass
