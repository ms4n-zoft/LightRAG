"""Configuration models for product ingestion"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class IngestionConfig:
    """Configuration for the ingestion process"""

    # Batch processing settings
    batch_size: int = 1  # Reduced for faster LLM processing (was 25)
    max_workers: int = 2  # Conservative concurrency

    # Text processing settings
    chunk_size: int = 800  # Smaller chunks for better granularity
    chunk_overlap: int = 150  # Good context preservation

    # Storage settings
    working_dir: str = "./rag_storage"  # Use same directory as main LightRAG server

    # Performance tuning
    enable_progress_tracking: bool = True
    enable_detailed_logging: bool = True

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds

    # Memory optimization
    clear_cache_after_batch: bool = True
    max_memory_usage_mb: Optional[int] = 2048  # 2GB limit

    # Timeout and resilience settings
    job_timeout_minutes: int = 10080  # 1 week (168 hours)
    batch_timeout_minutes: int = 10  # 10 minutes per batch
    enable_auto_resume: bool = True  # Enable automatic resume on timeout
    max_consecutive_failures: int = 6  # Stop after 6 consecutive batch failures
    checkpoint_interval: int = 10  # Save progress every 10 batches
