"""
MongoDB ObjectId utility functions

Provides consistent handling of ObjectId objects across the ingestion pipeline,
converting them to strings safely for text processing and metadata extraction.
"""

import logging
from typing import Any, List, Union, Optional, Dict
from bson import ObjectId

logger = logging.getLogger(__name__)


def safe_str(obj: Any, default: str = "") -> str:
    """
    Safely convert any object to string, handling ObjectIds properly

    Args:
        obj: Object to convert to string
        default: Default value if obj is None or empty

    Returns:
        String representation of the object
    """
    if obj is None:
        return default

    if isinstance(obj, ObjectId):
        return str(obj)

    if isinstance(obj, dict) and '$oid' in obj:
        return str(obj['$oid'])

    if isinstance(obj, (int, float)):
        return str(obj)

    if isinstance(obj, str):
        return obj

    if isinstance(obj, bool):
        return str(obj).lower()

    if isinstance(obj, (list, tuple)):
        logger.warning(
            f"Attempting to convert list/tuple to string: {obj[:3] if len(obj) > 3 else obj}...")
        return str(obj)

    # For other types, convert to string safely
    try:
        return str(obj)
    except Exception as e:
        logger.warning(
            f"Error converting object to string: {type(obj)}, error: {e}")
        return default


def safe_get_oid(data: Dict[str, Any], field: str, default: str = "unknown") -> str:
    """
    Safely extract ObjectId from a dictionary field and convert to string

    Args:
        data: Dictionary containing the field
        field: Field name to extract
        default: Default value if field is missing or invalid

    Returns:
        String representation of the ObjectId
    """
    try:
        value = data.get(field)
        if not value:
            return default

        if isinstance(value, ObjectId):
            return str(value)

        if isinstance(value, dict) and '$oid' in value:
            return str(value['$oid'])

        return str(value)

    except Exception as e:
        logger.warning(f"Error extracting ObjectId from field '{field}': {e}")
        return default


def safe_str_list(obj_list: List[Any], default: Optional[List[str]] = None) -> List[str]:
    """
    Safely convert a list of objects to strings, handling ObjectIds

    Args:
        obj_list: List of objects to convert
        default: Default list if obj_list is None or empty

    Returns:
        List of string representations
    """
    if not obj_list:
        return default or []

    # Handle case where obj_list is not actually a list
    if not isinstance(obj_list, (list, tuple)):
        logger.warning(f"Expected list but got {type(obj_list)}: {obj_list}")
        return default or []

    result = []
    for obj in obj_list:
        if obj is not None:  # Skip None values but allow empty strings
            try:
                result.append(safe_str(obj))
            except Exception as e:
                logger.warning(
                    f"Error converting object to string: {obj}, error: {e}")
                continue

    return result


def safe_join(obj_list: List[Any], separator: str = ", ", default: str = "") -> str:
    """
    Safely join a list of objects into a string, handling ObjectIds

    Args:
        obj_list: List of objects to join
        separator: String to use as separator
        default: Default value if list is empty

    Returns:
        Joined string
    """
    if not obj_list:
        return default

    str_list = safe_str_list(obj_list)
    return separator.join(str_list) if str_list else default


class ObjectIdUtils:
    """Utility class for handling ObjectId conversions in product data"""

    @staticmethod
    def safe_str_list(obj_list: List[Any], default: Optional[List[str]] = None) -> List[str]:
        """Safely convert a list of objects to strings, handling ObjectIds"""
        return safe_str_list(obj_list, default)

    @staticmethod
    def extract_product_id(product: Dict[str, Any]) -> str:
        """Extract product ID safely"""
        return safe_get_oid(product, '_id', 'unknown')

    @staticmethod
    def extract_feature_ids(product: Dict[str, Any]) -> List[str]:
        """Extract feature IDs as strings"""
        features = product.get('features', [])
        return safe_str_list(features)

    @staticmethod
    def extract_category_ids(product: Dict[str, Any]) -> List[str]:
        """Extract category IDs as strings"""
        categories = product.get('category', [])
        return safe_str_list(categories)

    @staticmethod
    def extract_industry_ids(product: Dict[str, Any]) -> List[str]:
        """Extract industry IDs as strings"""
        industries = product.get('industry', [])
        return safe_str_list(industries)

    @staticmethod
    def extract_support_ids(product: Dict[str, Any]) -> List[str]:
        """Extract support IDs as strings"""
        supports = product.get('supports', [])
        return safe_str_list(supports)

    @staticmethod
    def extract_company_id(product: Dict[str, Any]) -> str:
        """Extract company ID safely"""
        return safe_get_oid(product, 'company_id', '')

    @staticmethod
    def safe_contact_number(product: Dict[str, Any]) -> Optional[str]:
        """Safely extract contact number"""
        contact = product.get('contact')
        if contact is not None:
            return safe_str(contact)
        return None

    @staticmethod
    def safe_year_founded(product: Dict[str, Any]) -> Optional[int]:
        """Safely extract year founded"""
        year = product.get('year_founded')
        if year is not None:
            try:
                return int(year)
            except (ValueError, TypeError):
                logger.warning(f"Invalid year_founded value: {year}")
        return None

    @staticmethod
    def extract_timestamp_field(product: Dict[str, Any], field: str) -> Any:
        """Safely extract timestamp fields that might be in different formats"""
        value = product.get(field)
        if not value:
            return None

        # Handle MongoDB date format
        if isinstance(value, dict) and '$date' in value:
            return value['$date']

        return value

    @staticmethod
    def normalize_integration_list(integrations: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract integration information from integration objects"""
        if not integrations:
            return []

        result = []
        for integration in integrations:
            if isinstance(integration, dict):
                name = integration.get('name', 'Unknown Integration')
                website = integration.get('website', '')
                integration_dict = {
                    'name': safe_str(name),
                    'website': safe_str(website)
                }
                result.append(integration_dict)
            else:
                # Handle case where integration is already a string
                integration_dict = {
                    'name': safe_str(integration),
                    'website': ''
                }
                result.append(integration_dict)

        return result

    @staticmethod
    def extract_pricing_summary(pricing_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract and summarize pricing information"""
        if not pricing_data:
            return {
                'has_free_plan': False,
                'custom_pricing': False,
                'currency': 'USD',
                'plans': []
            }

        has_free = False
        custom_pricing = False
        currency = 'USD'
        plans = []

        for plan in pricing_data:
            if isinstance(plan, dict):
                plan_name = plan.get('plan', '')
                is_free = plan.get('isPlanFree', False)
                amount = plan.get('amount', 0)
                plan_currency = plan.get('currency', 'USD')

                # Keep plan as dictionary for normalizer, but ensure all values are strings
                plan_dict = {
                    'plan': safe_str(plan_name),
                    'amount': safe_str(amount),
                    'currency': safe_str(plan_currency),
                    'period': safe_str(plan.get('period', 'Month')),
                    'isPlanFree': is_free
                }
                plans.append(plan_dict)

                if is_free or (amount and str(amount) == '0'):
                    has_free = True

                if plan_name and 'custom' in plan_name.lower():
                    custom_pricing = True

                if plan_currency:
                    currency = plan_currency

        # Determine price range based on plans
        price_range = "Unknown"
        if has_free:
            price_range = "Free"
        elif custom_pricing:
            price_range = "Custom"
        else:
            # Could add more sophisticated price range logic here
            price_range = "Paid"

        return {
            'has_free_plan': has_free,
            'custom_pricing': custom_pricing,
            'currency': currency,
            'plans': plans,
            'price_range': price_range
        }
