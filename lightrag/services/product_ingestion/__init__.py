"""
Product Ingestion Service Package

Modular service for ingesting product data into LightRAG with:
- Enhanced metadata extraction
- Rich text normalization  
- Batch processing with progress tracking
- Knowledge graph construction for RFP use cases
- Vector embeddings for semantic search
"""

from .core.service import ProductIngestionService
from .models.config import IngestionConfig
from .models.metadata import ProductMetadata, EnhancedProductMetadata

__all__ = [
    'ProductIngestionService',
    'IngestionConfig',
    'ProductMetadata',
    'EnhancedProductMetadata'
]
