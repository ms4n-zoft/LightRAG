"""Enhanced MongoDB client for product data access"""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, OperationFailure
import certifi

logger = logging.getLogger(__name__)


class MongoDBClient:
    """Enhanced MongoDB client with connection pooling and optimizations for Zoftware database"""

    def __init__(self):
        """Initialize MongoDB client with enhanced configuration"""
        self.product_mongo_uri = os.getenv("PRODUCT_MONGO_URI")
        if not self.product_mongo_uri:
            raise ValueError(
                "PRODUCT_MONGO_URI environment variable is required")

        # Enhanced connection configuration for production workloads
        self.client = MongoClient(
            self.product_mongo_uri,
            tlsCAFile=certifi.where(),
            # Connection pooling for better performance
            maxPoolSize=20,  # Max connections in pool
            minPoolSize=5,   # Min connections to maintain
            maxIdleTimeMS=30000,  # Close connections after 30s idle
            # Timeout configurations
            serverSelectionTimeoutMS=5000,  # 5s server selection timeout
            connectTimeoutMS=10000,  # 10s connection timeout
            socketTimeoutMS=30000,   # 30s socket timeout
            # Read preferences for better performance
            readPreference='secondaryPreferred',  # Prefer secondary for reads
            # Write concern for reliability
            w='majority',  # Wait for majority acknowledgment
            # Compression for better network performance
            compressors='zstd,zlib,snappy'
        )

        # Cache frequently used database and collection references
        self._db_cache = {}
        self._stats_cache = {}
        self._stats_cache_ttl = {}

        # Test connection with retry logic
        self._test_connection_with_retry()

    def _test_connection_with_retry(self, max_retries: int = 3):
        """Test connection with retry logic"""
        for attempt in range(max_retries):
            try:
                # Test connection with timeout
                self.client.admin.command('ping', maxTimeMS=5000)
                logger.info("✅ Connected to product MongoDB")

                # Get server info for diagnostics
                server_info = self.client.server_info()
                logger.info(
                    f"📊 MongoDB Server Version: {server_info.get('version', 'Unknown')}")
                return

            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"⚠️ Connection attempt {attempt + 1} failed, retrying...")
                    continue
                else:
                    logger.error(
                        f"❌ Failed to connect to MongoDB after {max_retries} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"❌ Unexpected error connecting to MongoDB: {e}")
                raise

    def _get_database(self, database: str):
        """Get database with caching"""
        if database not in self._db_cache:
            self._db_cache[database] = self.client[database]
        return self._db_cache[database]

    def fetch_products(self,
                       database: str = "Zoftware",
                       collection: str = "Products",
                       filter_query: Optional[Dict[str, Any]] = None,
                       limit: Optional[int] = None,
                       skip: int = 0,
                       sort_field: Optional[str] = None,
                       sort_direction: int = 1,
                       projection: Optional[Dict[str, int]] = None,
                       batch_size: int = 1000) -> List[Dict[str, Any]]:
        """
        Enhanced product fetching with optimizations for large datasets

        Args:
            database: Database name (defaults to "Zoftware")
            collection: Collection name (defaults to "Products")
            filter_query: MongoDB query filter
            limit: Maximum number of documents to return
            skip: Number of documents to skip
            sort_field: Field to sort by
            sort_direction: Sort direction (1 for ascending, -1 for descending)
            projection: Fields to include/exclude in results
            batch_size: Batch size for cursor iteration

        Returns:
            List of product documents
        """
        try:
            db = self._get_database(database)
            coll = db[collection]

            # Build optimized query with default filters for active products
            query = filter_query or {}

            # Default to active products only if no specific filter provided
            if not filter_query:
                query = {'is_active': True}

            # Create cursor with projection for better performance
            cursor = coll.find(query, projection)

            # Apply sorting with index hints for common patterns
            if sort_field:
                cursor = cursor.sort(sort_field, sort_direction)
            # Remove default sort to avoid memory limit issues with large collections
            # For large datasets, natural order is more efficient

            # Apply pagination efficiently
            if skip > 0:
                cursor = cursor.skip(skip)

            if limit:
                cursor = cursor.limit(limit)

            # Set batch size for efficient network usage
            cursor = cursor.batch_size(batch_size)

            # Execute query with progress tracking for large datasets
            products = []
            processed = 0

            try:
                for doc in cursor:
                    products.append(doc)
                    processed += 1

                    # Log progress for large fetches
                    if limit and limit > 1000 and processed % 1000 == 0:
                        logger.info(
                            f"📊 Fetched {processed}/{limit} products...")

            except OperationFailure as e:
                logger.error(f"❌ MongoDB operation failed: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ Error during cursor iteration: {e}")
                raise

            logger.info(
                f"📦 Successfully fetched {len(products)} products from {database}.{collection}")

            if filter_query:
                logger.debug(f"Applied filter: {filter_query}")

            return products

        except Exception as e:
            logger.error(f"❌ Error fetching products: {e}")
            raise

    def get_collection_stats(self, database: str = "Zoftware", collection: str = "Products",
                             use_cache: bool = True, cache_ttl_minutes: int = 30) -> Dict[str, Any]:
        """Get comprehensive collection statistics with caching"""
        cache_key = f"{database}.{collection}"

        # Check cache first
        if use_cache and cache_key in self._stats_cache:
            if datetime.now() < self._stats_cache_ttl.get(cache_key, datetime.min):
                logger.debug(f"📊 Using cached stats for {cache_key}")
                return self._stats_cache[cache_key]

        try:
            db = self._get_database(database)
            coll = db[collection]

            # Get comprehensive statistics
            stats = {
                'total_documents': coll.count_documents({}),
                'active_products': coll.count_documents({'is_active': True}),
                'verified_products': coll.count_documents({'admin_verified': True}),
                'with_ratings': coll.count_documents({'ratings.total_reviews': {'$gt': 0}}),
                'with_integrations': coll.count_documents({'integrations': {'$exists': True, '$ne': []}}),
                'with_pricing': coll.count_documents({'pricing': {'$exists': True, '$ne': []}}),
                'recently_updated': coll.count_documents({
                    'updated_on': {'$gte': datetime.now() - timedelta(days=30)}
                }),
                # Rough estimate
                'collection_size_mb': round(coll.estimated_document_count() * 0.005, 2)
            }

            # Add distribution analysis
            try:
                # Get top categories (limited aggregation for performance)
                category_pipeline = [
                    {'$match': {'is_active': True, 'category': {'$exists': True}}},
                    {'$unwind': '$category'},
                    {'$group': {'_id': '$category', 'count': {'$sum': 1}}},
                    {'$sort': {'count': -1}},
                    {'$limit': 10}
                ]
                top_categories = list(coll.aggregate(
                    category_pipeline, maxTimeMS=10000))
                stats['top_categories'] = {
                    str(cat['_id']): cat['count'] for cat in top_categories}

            except Exception as e:
                logger.warning(f"⚠️ Could not get category distribution: {e}")
                stats['top_categories'] = {}

            # Cache results
            if use_cache:
                self._stats_cache[cache_key] = stats
                self._stats_cache_ttl[cache_key] = datetime.now(
                ) + timedelta(minutes=cache_ttl_minutes)

            logger.info(f"📊 Collection stats for {cache_key}: {stats['total_documents']:,} total, "
                        f"{stats['active_products']:,} active")
            return stats

        except Exception as e:
            logger.error(f"❌ Error getting collection stats: {e}")
            return {}

    def get_sample_products(self, database: str = "Zoftware", collection: str = "Products",
                            count: int = 3, filter_query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get multiple sample products for testing and validation"""
        try:
            # Get diverse samples by using different sort orders
            samples = []

            # Get products without sorting to avoid memory issues
            recent_products = self.fetch_products(
                database, collection,
                filter_query=filter_query or {'is_active': True},
                limit=count//3 + 1
                # Remove sort to avoid MongoDB memory limit
            )
            samples.extend(recent_products[:count//3 + 1])

            # Get highest rated products
            if len(samples) < count:
                rated_products = self.fetch_products(
                    database, collection,
                    filter_query={**(filter_query or {}),
                                  'ratings.overall_rating': {'$gte': 4.0}},
                    limit=count - len(samples)
                    # Remove sort to avoid MongoDB memory limit
                )
                samples.extend(rated_products)

            # Fill remaining with random products if needed
            if len(samples) < count:
                remaining = count - len(samples)
                random_products = self.fetch_products(
                    database, collection,
                    filter_query=filter_query or {'is_active': True},
                    limit=remaining,
                    skip=100  # Skip first 100 to get different products
                )
                samples.extend(random_products[:remaining])

            # Remove duplicates while preserving order
            seen_ids = set()
            unique_samples = []
            for product in samples:
                product_id = str(product.get('_id'))
                if product_id not in seen_ids:
                    seen_ids.add(product_id)
                    unique_samples.append(product)
                    if len(unique_samples) >= count:
                        break

            logger.info(f"📦 Retrieved {len(unique_samples)} sample products")
            return unique_samples[:count]

        except Exception as e:
            logger.error(f"❌ Error getting sample products: {e}")
            return []

    def get_sample_product(self, database: str = "Zoftware", collection: str = "Products") -> Optional[Dict[str, Any]]:
        """Get a single sample product for testing and validation"""
        samples = self.get_sample_products(database, collection, count=1)
        return samples[0] if samples else None

    def fetch_products_by_category(self, category_ids: List[str],
                                   database: str = "Zoftware", collection: str = "Products",
                                   limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch products by specific category IDs"""
        try:
            # Convert string IDs to ObjectId format if needed
            from bson import ObjectId

            category_filter = []
            for cat_id in category_ids:
                try:
                    # Try as ObjectId first
                    category_filter.append(ObjectId(cat_id))
                except:
                    # Fall back to string
                    category_filter.append(cat_id)

            filter_query = {
                'is_active': True,
                'category': {'$in': category_filter}
            }

            return self.fetch_products(
                database=database,
                collection=collection,
                filter_query=filter_query,
                limit=limit
            )

        except Exception as e:
            logger.error(f"❌ Error fetching products by category: {e}")
            return []

    def fetch_products_with_ratings(self, min_rating: float = 3.0,
                                    database: str = "Zoftware", collection: str = "Products",
                                    limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch products with minimum rating threshold"""
        try:
            filter_query = {
                'is_active': True,
                'ratings.overall_rating': {'$gte': min_rating},
                'ratings.total_reviews': {'$gt': 0}
            }

            return self.fetch_products(
                database=database,
                collection=collection,
                filter_query=filter_query,
                limit=limit
                # Remove sort to avoid MongoDB memory limit with large collections
            )

        except Exception as e:
            logger.error(f"❌ Error fetching products with ratings: {e}")
            return []

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information and health status"""
        try:
            server_status = self.client.admin.command("serverStatus")
            return {
                'connected': True,
                'server_version': server_status.get('version', 'Unknown'),
                'uptime_seconds': server_status.get('uptime', 0),
                'connections': server_status.get('connections', {}),
                'network': server_status.get('network', {}),
                'host_info': server_status.get('host', 'Unknown')
            }
        except Exception as e:
            logger.error(f"❌ Error getting connection info: {e}")
            return {'connected': False, 'error': str(e)}

    def clear_cache(self):
        """Clear all cached data"""
        self._stats_cache.clear()
        self._stats_cache_ttl.clear()
        logger.info("🗑️ MongoDB client cache cleared")

    def close(self):
        """Close the MongoDB connection and clear caches"""
        if self.client:
            self.clear_cache()
            self.client.close()
            logger.info("📴 MongoDB connection closed")
