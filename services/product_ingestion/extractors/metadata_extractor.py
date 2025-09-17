"""Enhanced metadata extraction from product JSON"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.metadata import EnhancedProductMetadata
from ..utils.objectid_utils import ObjectIdUtils, safe_str, safe_get_oid

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extracts comprehensive metadata from product JSON documents"""

    def __init__(self):
        """Initialize the metadata extractor"""
        self.category_cache = {}  # Cache for category ID to name resolution
        self.industry_cache = {}  # Cache for industry ID to name resolution

    def extract_metadata(self, product_json: Dict[str, Any]) -> EnhancedProductMetadata:
        """
        Extract comprehensive metadata from product JSON

        Args:
            product_json: Raw product document from MongoDB

        Returns:
            EnhancedProductMetadata with all extracted fields
        """
        try:
            # Core identifiers - use ObjectId utilities
            product_id = ObjectIdUtils.extract_product_id(product_json)
            product_name = product_json.get('product_name', 'Unknown Product')
            weburl = product_json.get('weburl', '')
            company = product_json.get('company', 'Unknown Company')

            # Visual and branding
            logo_key = product_json.get('logo_key')
            logo_url = product_json.get('logo_url')
            company_website = product_json.get('company_website')

            # Extract pricing information using utilities with safe defaults
            pricing_info = ObjectIdUtils.extract_pricing_summary(
                product_json.get('pricing', []))

            # Extract ratings with safe defaults
            ratings = product_json.get('ratings', {})

            # Extract timestamps - use ObjectId utilities with safe defaults
            created_on = self._parse_timestamp(product_json.get('created_on'))
            updated_on = self._parse_timestamp(
                ObjectIdUtils.extract_timestamp_field(product_json, 'updated_on'))

            # Extract features using utilities with safe defaults
            features = ObjectIdUtils.extract_feature_ids(product_json)
            other_features = ObjectIdUtils.safe_str_list(
                product_json.get('other_features', []))

            # Extract integrations using utilities with safe defaults
            integrations = ObjectIdUtils.normalize_integration_list(
                product_json.get('integrations', []))

            # Create metadata object
            metadata = EnhancedProductMetadata(
                # Core identifiers
                product_id=product_id,
                product_name=product_name,
                weburl=weburl,
                company=company,

                # Visual and branding
                logo_key=logo_key,
                logo_url=logo_url,
                company_website=company_website,

                # Categorization using utilities
                categories=ObjectIdUtils.extract_category_ids(product_json),
                parent_categories=ObjectIdUtils.extract_category_ids(
                    {'category': product_json.get('parent_categories', [])}),
                industry=ObjectIdUtils.extract_industry_ids(product_json),
                industry_size=ObjectIdUtils.safe_str_list(
                    product_json.get('industry_size', [])),

                # Pricing - with safe defaults
                pricing_plans=pricing_info.get('plans', []),
                has_free_plan=pricing_info.get('has_free_plan', False),
                custom_pricing=pricing_info.get('custom_pricing', False),
                pricing_currency=pricing_info.get('currency', 'USD'),
                price_range=pricing_info.get('price_range', 'Unknown'),

                # Content
                description=product_json.get('description', ''),
                overview=product_json.get('overview', ''),
                usp=product_json.get('usp', ''),

                # Features
                features=features,
                other_features=other_features,
                supports=ObjectIdUtils.extract_support_ids(product_json),

                # Ratings
                overall_rating=ratings.get('overall_rating', 0.0),
                ease_of_use=ratings.get('ease_of_use', 0.0),
                breadth_of_features=ratings.get('breadth_of_features', 0.0),
                ease_of_implementation=ratings.get(
                    'ease_of_implementation', 0.0),
                value_for_money=ratings.get('value_for_money', 0.0),
                customer_support=ratings.get('customer_support', 0.0),
                total_reviews=ratings.get('total_reviews', 0),

                # Technical
                integrations=integrations,
                tech_stack=ObjectIdUtils.safe_str_list(
                    product_json.get('tech_stack', [])),
                languages=ObjectIdUtils.safe_str_list(
                    product_json.get('languages', [])),

                # Company info using utilities
                year_founded=ObjectIdUtils.safe_year_founded(product_json),
                hq_location=product_json.get('hq_location'),
                contact=ObjectIdUtils.safe_contact_number(product_json),
                support_email=product_json.get('support_email'),

                # Status
                is_active=product_json.get('is_active', True),
                is_verified=product_json.get('is_verify', False),
                admin_verified=product_json.get('admin_verified', False),
                subscription_plan=product_json.get(
                    'subscription_plan', 'Basic'),

                # Timestamps
                created_on=created_on,
                updated_on=updated_on,
            )

            return metadata

        except Exception as e:
            import traceback
            logger.error(
                f"Error extracting metadata for product {product_json.get('product_name', 'unknown')}: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Return minimal metadata on error using utilities
            return EnhancedProductMetadata(
                product_id=ObjectIdUtils.extract_product_id(product_json),
                product_name=product_json.get(
                    'product_name', 'Unknown Product'),
                weburl=product_json.get('weburl', ''),
                company=product_json.get('company', 'Unknown Company')
            )

    def _extract_pricing_info(self, pricing_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract and analyze pricing information"""
        if not pricing_data:
            return {
                'plans': [],
                'has_free_plan': False,
                'custom_pricing': True,
                'currency': 'USD',
                'price_range': 'custom'
            }

        has_free_plan = any(plan.get('isPlanFree', False)
                            for plan in pricing_data)
        custom_pricing = any(plan.get('plan', '').lower()
                             == 'custom' for plan in pricing_data)

        # Determine price range based on amounts
        amounts = []
        for plan in pricing_data:
            try:
                amount = float(plan.get('amount', 0))
                if amount > 0:
                    amounts.append(amount)
            except (ValueError, TypeError):
                pass

        if not amounts or custom_pricing:
            price_range = 'custom'
        else:
            max_amount = max(amounts)
            if max_amount < 50:
                price_range = 'budget'
            elif max_amount < 200:
                price_range = 'mid-range'
            elif max_amount < 1000:
                price_range = 'premium'
            else:
                price_range = 'luxury'

        currency = pricing_data[0].get(
            'currency', 'USD') if pricing_data else 'USD'

        return {
            'plans': pricing_data,
            'has_free_plan': has_free_plan,
            'custom_pricing': custom_pricing,
            'currency': currency,
            'price_range': price_range
        }

    def _extract_features(self, product_json: Dict[str, Any]) -> List[str]:
        """Extract feature names from feature IDs (placeholder for now)"""
        # TODO: If you have a features collection, resolve IDs to names here
        feature_ids = product_json.get('features', [])
        if not feature_ids:
            return []

        # For now, return the IDs as strings - handle ObjectId properly
        # In a real implementation, you'd resolve these from a features collection
        result = []
        for feature_id in feature_ids:
            if feature_id:
                if isinstance(feature_id, dict) and '$oid' in feature_id:
                    result.append(str(feature_id['$oid']))
                else:
                    result.append(str(feature_id))
        return result

    def _extract_supports(self, supports_data: List[Dict[str, Any]]) -> List[str]:
        """Extract support information"""
        if not supports_data:
            return []

        # TODO: Resolve support IDs to names if needed - handle ObjectId properly
        result = []
        for support in supports_data:
            if support:
                if isinstance(support, dict) and '$oid' in support:
                    result.append(str(support['$oid']))
                else:
                    result.append(str(support))
        return result

    def _extract_category_names(self, category_data: List[Dict[str, Any]]) -> List[str]:
        """Extract category names from category IDs"""
        if not category_data:
            return []

        # TODO: If you have a categories collection, resolve IDs to names here
        # For now, return the IDs as strings
        category_names = []
        for cat in category_data:
            if isinstance(cat, dict) and '$oid' in cat:
                category_names.append(cat['$oid'])
            else:
                category_names.append(str(cat))

        return category_names

    def _extract_industry_names(self, industry_data: List[Dict[str, Any]]) -> List[str]:
        """Extract industry names from industry IDs"""
        if not industry_data:
            return []

        # TODO: If you have an industries collection, resolve IDs to names here
        industry_names = []
        for ind in industry_data:
            if isinstance(ind, dict) and '$oid' in ind:
                industry_names.append(ind['$oid'])
            else:
                industry_names.append(str(ind))

        return industry_names

    def _parse_timestamp(self, timestamp_data) -> Optional[datetime]:
        """Parse various timestamp formats from MongoDB"""
        if not timestamp_data:
            return None

        try:
            if isinstance(timestamp_data, str):
                # ISO format string
                return datetime.fromisoformat(timestamp_data.replace('Z', '+00:00'))
            elif isinstance(timestamp_data, dict) and '$date' in timestamp_data:
                # MongoDB date object
                date_str = timestamp_data['$date']
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                return None
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse timestamp {timestamp_data}: {e}")
            return None

    def set_category_resolver(self, resolver_func):
        """Set a function to resolve category IDs to names"""
        self.category_resolver = resolver_func

    def set_industry_resolver(self, resolver_func):
        """Set a function to resolve industry IDs to names"""
        self.industry_resolver = resolver_func
