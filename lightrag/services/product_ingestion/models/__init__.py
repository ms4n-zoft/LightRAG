"""Data models for product ingestion service"""

from .config import IngestionConfig
from .metadata import ProductMetadata, EnhancedProductMetadata

__all__ = ['IngestionConfig', 'ProductMetadata', 'EnhancedProductMetadata']
