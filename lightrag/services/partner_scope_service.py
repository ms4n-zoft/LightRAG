"""
Partner scope resolution service.

Resolves a partner_id to a set of product IDs that define the partner's
allowed scope for RAG queries. Product IDs are loaded from the partner's
MongoDB database and cached in-memory with a configurable TTL.

Usage:
    scope_service = PartnerScopeService()

    # At startup or on first query:
    product_ids = await scope_service.get_scope_product_ids("peko")

    # Pass to QueryParam:
    param.scope_product_ids = product_ids
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PartnerConfig:
    """Configuration for a single partner's scope."""

    partner_id: str
    """Unique identifier for the partner (e.g., 'peko')."""

    mongo_uri: str
    """MongoDB connection URI for the partner database."""

    db_name: str
    """MongoDB database name for the partner."""

    product_collection: str = "products"
    """Collection name containing the partner's products."""

    category_ids: list[str] = field(default_factory=list)
    """Parent category IDs that define this partner's scope (informational)."""


# ──────────────────────────────────────────────────────────────
# Partner configurations
# ──────────────────────────────────────────────────────────────

PARTNER_CONFIGS: dict[str, PartnerConfig] = {
    "peko": PartnerConfig(
        partner_id="peko",
        mongo_uri=os.getenv(
            "PEKO_MONGO_URI",
            "mongodb://localhost:27017/?directConnection=true",
        ),
        db_name=os.getenv("PEKO_DB_NAME", "PekoPartnerDB"),
        product_collection="products",
        category_ids=[
            "64e5e7db6295fca3e00f3245",  # CRM & Sales
            "64e5e7db6295fca3e00f323b",  # Finance & Accounting
            "64e5e7db6295fca3e00f3247",  # Marketing
            "64e5e7db6295fca3e00f3241",  # Digital Workspace & Productivity
            "64e5e7db6295fca3e00f3249",  # Security
            "64e5e7db6295fca3e00f323f",  # Customer Service & Communication
            "64e5e7db6295fca3e00f3251",  # Cloud & Infrastructure
            "64e5e7db6295fca3e00f3258",  # Creativity & Design
        ],
    ),
}


@dataclass
class _CacheEntry:
    product_ids: set[str]
    loaded_at: float
    count: int


class PartnerScopeService:
    """
    Resolves partner_id → set of product IDs with in-memory caching.

    The product IDs are the main Zoftware DB _id values stored in the
    partner's MongoDB products collection (we replaced partner _ids with
    main DB _ids so they match the RAG store product_id references).
    """

    def __init__(self, cache_ttl_seconds: int = 3600):
        """
        Args:
            cache_ttl_seconds: How long to cache product IDs before refreshing.
                               Default: 1 hour.
        """
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_ttl = cache_ttl_seconds
        self._locks: dict[str, asyncio.Lock] = {}

    def get_partner_ids(self) -> list[str]:
        """Return all configured partner IDs."""
        return list(PARTNER_CONFIGS.keys())

    async def get_scope_product_ids(self, partner_id: str) -> set[str] | None:
        """
        Get the set of product IDs for a partner.

        Returns None if the partner_id is not configured.
        Returns cached set if available and not expired.
        Otherwise loads from MongoDB and caches.
        """
        if partner_id not in PARTNER_CONFIGS:
            logger.warning(f"Unknown partner_id: {partner_id}")
            return None

        # Check cache
        if partner_id in self._cache:
            entry = self._cache[partner_id]
            age = time.time() - entry.loaded_at
            if age < self._cache_ttl:
                logger.debug(
                    f"Partner scope cache hit: {partner_id} "
                    f"({entry.count} products, age={age:.0f}s)"
                )
                return entry.product_ids

        # Use per-partner lock to prevent thundering herd
        if partner_id not in self._locks:
            self._locks[partner_id] = asyncio.Lock()

        async with self._locks[partner_id]:
            # Double-check after acquiring lock
            if partner_id in self._cache:
                entry = self._cache[partner_id]
                if time.time() - entry.loaded_at < self._cache_ttl:
                    return entry.product_ids

            # Load from MongoDB
            product_ids = await self._load_product_ids(partner_id)
            if product_ids is not None:
                self._cache[partner_id] = _CacheEntry(
                    product_ids=product_ids,
                    loaded_at=time.time(),
                    count=len(product_ids),
                )
                logger.info(
                    f"Partner scope loaded: {partner_id} → {len(product_ids)} product IDs"
                )
            return product_ids

    async def _load_product_ids(self, partner_id: str) -> set[str] | None:
        """Load all product IDs from the partner's MongoDB collection."""
        config = PARTNER_CONFIGS[partner_id]

        try:
            # Use motor for async MongoDB access if available, fall back to pymongo
            try:
                from motor.motor_asyncio import AsyncIOMotorClient

                client = AsyncIOMotorClient(config.mongo_uri)
                db = client[config.db_name]
                collection = db[config.product_collection]

                product_ids = set()
                async for doc in collection.find({}, {"_id": 1}):
                    product_ids.add(str(doc["_id"]))

                client.close()

            except ImportError:
                # Fallback to synchronous pymongo
                from pymongo import MongoClient

                client = MongoClient(config.mongo_uri)
                db = client[config.db_name]
                collection = db[config.product_collection]

                product_ids = set()
                for doc in collection.find({}, {"_id": 1}):
                    product_ids.add(str(doc["_id"]))

                client.close()

            return product_ids

        except Exception as e:
            logger.error(
                f"Failed to load product IDs for partner {partner_id}: {e}"
            )
            return None

    def invalidate_cache(self, partner_id: str | None = None):
        """
        Invalidate cached product IDs.

        Args:
            partner_id: If provided, only invalidate this partner's cache.
                        If None, invalidate all.
        """
        if partner_id:
            self._cache.pop(partner_id, None)
        else:
            self._cache.clear()
        logger.info(
            f"Partner scope cache invalidated: {partner_id or 'all'}"
        )


# Singleton instance
_partner_scope_service: PartnerScopeService | None = None


def get_partner_scope_service() -> PartnerScopeService:
    """Get or create the singleton PartnerScopeService instance."""
    global _partner_scope_service
    if _partner_scope_service is None:
        ttl = int(os.getenv("PARTNER_SCOPE_CACHE_TTL", "3600"))
        _partner_scope_service = PartnerScopeService(cache_ttl_seconds=ttl)
    return _partner_scope_service
