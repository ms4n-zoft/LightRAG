"""Batch processing logic for product ingestion"""

import logging
import asyncio
from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict

from ..models.metadata import EnhancedProductMetadata
from ..extractors.metadata_extractor import MetadataExtractor
from ..normalizers.rfp_optimized_normalizer import RFPOptimizedNormalizer
from ..clients.lightrag_client import LightRAGClient
from ..utils.objectid_utils import ObjectIdUtils

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Handles batch processing of products with progress tracking"""

    def __init__(self, lightrag_client: LightRAGClient, db=None):
        """Initialize batch processor"""
        self.lightrag_client = lightrag_client
        self.metadata_extractor = MetadataExtractor(db)
        self.product_normalizer = RFPOptimizedNormalizer()

    async def process_batch(self,
                            products: List[Dict[str, Any]],
                            batch_id: int) -> Dict[str, Any]:
        """
        Process a batch of products with comprehensive error handling

        Args:
            products: List of product documents
            batch_id: Batch identifier for tracking

        Returns:
            Batch processing results with metadata summary
        """
        start_time = datetime.now()
        logger.info(
            f"🔄 Processing batch {batch_id} ({len(products)} products)")

        batch_results = {
            "batch_id": batch_id,
            "start_time": start_time.isoformat(),
            "processed": 0,
            "errors": [],
            "metadata_summary": {},
            "normalized_texts": [],
            "product_metadata": []
        }

        # Process each product in the batch
        logger.info(
            f"📋 Processing {len(products)} products in batch {batch_id}")

        # Validate the products list structure
        if not isinstance(products, list):
            logger.error(f"❌ Products is not a list, it's {type(products)}")
            batch_results["errors"].append({
                "batch_error": f"Products parameter is {type(products)}, expected list",
                "error_type": "TypeError"
            })
            return batch_results

        for i, product in enumerate(products):
            try:
                # Get product name for logging
                product_name = product.get('product_name', 'Unknown') if isinstance(
                    product, dict) else 'Invalid Product'

                # Validate product is a dictionary
                if not isinstance(product, dict):
                    logger.warning(
                        f"⚠️  Skipping invalid product {i+1} - not a dictionary")
                    error_info = {
                        "product_index": i,
                        "product_id": "unknown",
                        "product_name": "unknown",
                        "error": "Product is not a dictionary",
                        "error_type": "TypeError"
                    }
                    batch_results["errors"].append(error_info)
                    continue

                # Validate product has required fields
                if not product.get('product_name'):
                    logger.warning(
                        f"⚠️  Skipping product {i+1} - missing product_name field")
                    error_info = {
                        "product_index": i,
                        "product_id": ObjectIdUtils.extract_product_id(product),
                        "product_name": "missing",
                        "error": "Product missing product_name field",
                        "error_type": "ValidationError"
                    }
                    batch_results["errors"].append(error_info)
                    continue

                # Extract enhanced metadata
                try:
                    metadata = self.metadata_extractor.extract_metadata(
                        product)
                    logger.debug(
                        f"📊 Extracted metadata for: {metadata.product_name}")
                except Exception as e:
                    logger.error(
                        f"❌ Failed to extract metadata for {product_name}: {e}")
                    error_info = {
                        "product_index": i,
                        "product_id": ObjectIdUtils.extract_product_id(product),
                        "product_name": product_name,
                        "error": f"Metadata extraction failed: {e}",
                        "error_type": "MetadataExtractionError"
                    }
                    batch_results["errors"].append(error_info)
                    continue

                # Normalize to rich text
                try:
                    normalized_text = self.product_normalizer.normalize_product(
                        product, metadata)
                    logger.debug(
                        f"📝 Normalized text for {metadata.product_name} ({len(normalized_text)} chars)")
                except Exception as e:
                    logger.error(f"❌ Failed to normalize {product_name}: {e}")
                    error_info = {
                        "product_index": i,
                        "product_id": metadata.product_id if 'metadata' in locals() else "unknown",
                        "product_name": metadata.product_name if 'metadata' in locals() else product_name,
                        "error": f"Text normalization failed: {e}",
                        "error_type": "NormalizationError"
                    }
                    batch_results["errors"].append(error_info)
                    continue

                # Store results
                batch_results["normalized_texts"].append(normalized_text)
                batch_results["product_metadata"].append(metadata)
                batch_results["processed"] += 1

                logger.info(
                    f"✅ Processed {metadata.product_name} ({i+1}/{len(products)})")

            except Exception as e:
                # Safe error handling
                try:
                    product_id = ObjectIdUtils.extract_product_id(
                        product) if isinstance(product, dict) else "unknown"
                    product_name = product.get('product_name', 'unknown') if isinstance(
                        product, dict) else "unknown"
                except:
                    product_id = "unknown"
                    product_name = "unknown"

                error_info = {
                    "product_index": i,
                    "product_id": product_id,
                    "product_name": product_name,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                batch_results["errors"].append(error_info)
                logger.warning(f"⚠️  Error processing product {i+1}: {e}")

        # Insert batch into LightRAG if we have processed texts
        if batch_results["normalized_texts"]:
            try:
                await self._insert_batch_to_lightrag(
                    batch_results["normalized_texts"],
                    batch_id,
                    batch_results["product_metadata"]
                )
                logger.info(
                    f"✅ Batch {batch_id} successfully inserted into LightRAG knowledge graph")
            except Exception as e:
                logger.error(
                    f"❌ Failed to insert batch {batch_id} into LightRAG: {e}")
                batch_results["errors"].append({
                    "batch_error": str(e),
                    "error_type": "lightrag_insertion"
                })

        # Generate metadata summary
        batch_results["metadata_summary"] = self._generate_metadata_summary(
            batch_results["product_metadata"]
        )

        # Calculate processing time
        end_time = datetime.now()
        batch_results["end_time"] = end_time.isoformat()
        batch_results["duration_seconds"] = (
            end_time - start_time).total_seconds()

        logger.info(
            f"📊 Batch {batch_id} completed in {batch_results['duration_seconds']:.2f}s")
        logger.info(
            f"   Processed: {batch_results['processed']}, Errors: {len(batch_results['errors'])}")

        return batch_results

    async def _insert_batch_to_lightrag(self, normalized_texts: List[str], batch_id: int, product_metadata: List = None):
        """Insert batch of normalized texts into LightRAG with progressive processing"""

        # For very small batches (≤3 products), process individually for better performance
        if len(normalized_texts) <= 3:
            logger.info(
                f"🔄 Processing batch {batch_id} individually ({len(normalized_texts)} products)")

            for i, text in enumerate(normalized_texts):
                product_header = f"PRODUCT {i+1} FROM BATCH {batch_id}\n\n"
                final_text = product_header + text
                source_name = f"product_batch_{batch_id}_item_{i+1}"

                # Extract product info for enhanced metadata if available
                product_id = None
                category = None
                extracted_metadata = None
                if product_metadata and i < len(product_metadata):
                    metadata = product_metadata[i]
                    product_id = metadata.product_id
                    category = metadata.categories[0] if metadata.categories else None

                    # Extract essential metadata for vector storage (only from normalizer)
                    extracted_metadata = {
                        "weburl": metadata.weburl,
                        "company": metadata.company,
                        "company_website": metadata.company_website,
                        "category_ids": metadata.categories,  # List of category IDs
                        "logo_key": metadata.logo_key,
                        "logo_url": metadata.logo_url
                    }

                success = await self.lightrag_client.insert_text_with_source(
                    final_text, source_name, product_id, category, extracted_metadata)
                if not success:
                    raise Exception(
                        f"Failed to insert product {i+1} from batch {batch_id} into LightRAG")

                logger.info(
                    f"✅ Product {i+1}/{len(normalized_texts)} from batch {batch_id} processed (ID: {product_id})")
        else:
            # For larger batches, use original combined approach
            batch_separator = f"\n\n{'='*80}\nBATCH {batch_id} PRODUCT SEPARATOR\n{'='*80}\n\n"
            combined_text = batch_separator.join(normalized_texts)

            # Add batch header
            batch_header = f"PRODUCT BATCH {batch_id} - {len(normalized_texts)} PRODUCTS\n\n"
            final_text = batch_header + combined_text

            # Insert into LightRAG with proper source identification
            source_name = f"product_batch_{batch_id}"

            # For combined batches, use first product's metadata for category
            category = None
            if product_metadata and len(product_metadata) > 0:
                first_metadata = product_metadata[0]
                category = first_metadata.categories[0] if first_metadata.categories else None

            success = await self.lightrag_client.insert_text_with_source(
                # No single product_id for combined batch
                final_text, source_name, None, category)
            if not success:
                raise Exception(
                    f"Failed to insert batch {batch_id} into LightRAG")

    def _generate_metadata_summary(self, metadata_list: List[EnhancedProductMetadata]) -> Dict[str, Any]:
        """Generate comprehensive metadata summary for the batch"""
        if not metadata_list:
            return {}

        # Initialize counters
        categories = defaultdict(int)
        companies = defaultdict(int)
        price_ranges = defaultdict(int)
        rating_tiers = defaultdict(int)
        market_positions = defaultdict(int)
        feature_richness = defaultdict(int)
        industries = defaultdict(int)

        # Aggregate statistics
        total_features = 0
        total_integrations = 0
        total_reviews = 0
        rating_sum = 0.0
        rated_products = 0

        for metadata in metadata_list:
            # Category distribution
            for category in metadata.categories:
                categories[category] += 1

            # Company distribution
            companies[metadata.company] += 1

            # Price range distribution
            price_ranges[metadata.price_range] += 1

            # Rating tier distribution
            rating_tiers[metadata.rating_tier] += 1

            # Market position distribution
            market_positions[metadata.market_position] += 1

            # Feature richness distribution
            feature_richness[metadata.feature_richness] += 1

            # Industry distribution
            for industry in metadata.industry:
                industries[industry] += 1

            # Aggregate stats
            total_features += len(metadata.features) + \
                len(metadata.other_features)
            total_integrations += len(metadata.integrations)
            total_reviews += metadata.total_reviews

            if metadata.overall_rating > 0:
                rating_sum += metadata.overall_rating
                rated_products += 1

        # Calculate averages
        avg_rating = rating_sum / rated_products if rated_products > 0 else 0.0
        avg_features = total_features / \
            len(metadata_list) if metadata_list else 0
        avg_integrations = total_integrations / \
            len(metadata_list) if metadata_list else 0

        return {
            "total_products": len(metadata_list),
            "categories": dict(categories),
            "companies": dict(companies),
            "price_ranges": dict(price_ranges),
            "rating_tiers": dict(rating_tiers),
            "market_positions": dict(market_positions),
            "feature_richness": dict(feature_richness),
            "industries": dict(industries),
            "statistics": {
                "average_rating": round(avg_rating, 2),
                "average_features_per_product": round(avg_features, 1),
                "average_integrations_per_product": round(avg_integrations, 1),
                "total_reviews": total_reviews,
                "products_with_ratings": rated_products
            }
        }
