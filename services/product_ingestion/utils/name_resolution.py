"""
Utility functions for resolving MongoDB ObjectIds to human-readable names.

This module provides functions to resolve various ID references in product documents
to their corresponding names from lookup collections.
"""

import logging
from typing import Dict, List, Optional, Any
from bson import ObjectId
from pymongo.database import Database

logger = logging.getLogger(__name__)


class NameResolver:
    """
    Resolves ObjectIds to names using MongoDB lookup collections.

    Provides caching and batch resolution for efficient lookups.
    """

    def __init__(self, db: Database):
        """
        Initialize the name resolver with a MongoDB database connection.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self._cache = {
            'features': {},
            'parent_categories': {},
            'sub_categories': {},
            'parent_industries': {},
            'supports': {},
            'languages': {},
            'techstack': {},
            'companies': {}
        }
        self._cache_loaded = {
            'features': False,
            'parent_categories': False,
            'sub_categories': False,
            'parent_industries': False,
            'supports': False,
            'languages': False,
            'techstack': False,
            'companies': False
        }

    def _load_cache(self, collection_type: str, collection_name: str, name_field: str = 'name'):
        """Load all documents from a collection into cache"""
        if self._cache_loaded[collection_type]:
            return

        try:
            collection = self.db[collection_name]
            documents = collection.find({}, {'_id': 1, name_field: 1})

            for doc in documents:
                if name_field in doc and doc[name_field]:
                    self._cache[collection_type][str(
                        doc['_id'])] = doc[name_field]

            self._cache_loaded[collection_type] = True
            logger.debug(
                f"Loaded {len(self._cache[collection_type])} {collection_type} into cache")

        except Exception as e:
            logger.warning(f"Failed to load {collection_type} cache: {e}")

    def resolve_feature_ids(self, feature_ids: List[Any]) -> List[str]:
        """
        Resolve feature ObjectIds to feature names.

        Args:
            feature_ids: List of ObjectIds or strings representing features

        Returns:
            List of feature names
        """
        if not feature_ids:
            return []

        self._load_cache('features', 'Features', 'name')

        resolved_names = []
        for feature_id in feature_ids:
            feature_id_str = str(feature_id)
            if feature_id_str in self._cache['features']:
                resolved_names.append(self._cache['features'][feature_id_str])
            else:
                logger.debug(
                    f"Feature ID not found in cache: {feature_id_str}")

        return resolved_names

    def resolve_parent_category_ids(self, category_ids: List[Any]) -> List[str]:
        """
        Resolve parent category ObjectIds to category names.

        Args:
            category_ids: List of ObjectIds or strings representing parent categories

        Returns:
            List of parent category names
        """
        if not category_ids:
            return []

        self._load_cache('parent_categories', 'ParentCategory', 'name')

        resolved_names = []
        for category_id in category_ids:
            category_id_str = str(category_id)
            if category_id_str in self._cache['parent_categories']:
                resolved_names.append(
                    self._cache['parent_categories'][category_id_str])
            else:
                logger.debug(
                    f"Parent category ID not found in cache: {category_id_str}")

        return resolved_names

    def resolve_sub_category_ids(self, category_ids: List[Any]) -> List[str]:
        """
        Resolve sub category ObjectIds to category names.

        Args:
            category_ids: List of ObjectIds or strings representing sub categories

        Returns:
            List of sub category names
        """
        if not category_ids:
            return []

        self._load_cache('sub_categories', 'SubCategory', 'name')

        resolved_names = []
        for category_id in category_ids:
            category_id_str = str(category_id)
            if category_id_str in self._cache['sub_categories']:
                resolved_names.append(
                    self._cache['sub_categories'][category_id_str])
            else:
                logger.debug(
                    f"Sub category ID not found in cache: {category_id_str}")

        return resolved_names

    def resolve_industry_ids(self, industry_ids: List[Any]) -> List[str]:
        """
        Resolve parent industry ObjectIds to industry names.

        Args:
            industry_ids: List of ObjectIds or strings representing industries

        Returns:
            List of industry names
        """
        if not industry_ids:
            return []

        self._load_cache('parent_industries', 'ParentIndustry', 'name')

        resolved_names = []
        for industry_id in industry_ids:
            industry_id_str = str(industry_id)
            if industry_id_str in self._cache['parent_industries']:
                resolved_names.append(
                    self._cache['parent_industries'][industry_id_str])
            else:
                logger.debug(
                    f"Industry ID not found in cache: {industry_id_str}")

        return resolved_names

    def resolve_support_ids(self, support_ids: List[Any]) -> List[str]:
        """
        Resolve support ObjectIds to support platform names.

        Args:
            support_ids: List of ObjectIds or strings representing support platforms

        Returns:
            List of support platform names
        """
        if not support_ids:
            return []

        self._load_cache('supports', 'Supports', 'name')

        resolved_names = []
        for support_id in support_ids:
            support_id_str = str(support_id)
            if support_id_str in self._cache['supports']:
                resolved_names.append(self._cache['supports'][support_id_str])
            else:
                logger.debug(
                    f"Support ID not found in cache: {support_id_str}")

        return resolved_names

    def resolve_language_ids(self, language_ids: List[Any]) -> List[str]:
        """
        Resolve language ObjectIds to language names.

        Args:
            language_ids: List of ObjectIds or strings representing languages

        Returns:
            List of language names
        """
        if not language_ids:
            return []

        self._load_cache('languages', 'Languages', 'name')

        resolved_names = []
        for language_id in language_ids:
            language_id_str = str(language_id)
            if language_id_str in self._cache['languages']:
                resolved_names.append(
                    self._cache['languages'][language_id_str])
            else:
                logger.debug(
                    f"Language ID not found in cache: {language_id_str}")

        return resolved_names

    def resolve_techstack_ids(self, techstack_ids: List[Any]) -> List[str]:
        """
        Resolve tech stack ObjectIds to technology names.

        Args:
            techstack_ids: List of ObjectIds or strings representing technologies

        Returns:
            List of technology names
        """
        if not techstack_ids:
            return []

        self._load_cache('techstack', 'Techstack', 'name')

        resolved_names = []
        for tech_id in techstack_ids:
            tech_id_str = str(tech_id)
            if tech_id_str in self._cache['techstack']:
                resolved_names.append(self._cache['techstack'][tech_id_str])
            else:
                logger.debug(
                    f"Tech stack ID not found in cache: {tech_id_str}")

        return resolved_names

    def resolve_company_id(self, company_id: Any) -> Optional[str]:
        """
        Resolve company ObjectId to company name.

        Args:
            company_id: ObjectId or string representing a company

        Returns:
            Company name or None if not found
        """
        if not company_id:
            return None

        self._load_cache('companies', 'Company', 'name')

        company_id_str = str(company_id)
        if company_id_str in self._cache['companies']:
            return self._cache['companies'][company_id_str]
        else:
            logger.debug(f"Company ID not found in cache: {company_id_str}")
            return None

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about the cached data.

        Returns:
            Dictionary with cache sizes for each collection type
        """
        return {
            collection_type: len(cache_data)
            for collection_type, cache_data in self._cache.items()
        }
