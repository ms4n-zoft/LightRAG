"""Metadata models for product data"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Union
from datetime import datetime


class MetadataValidator:
    """Helper class for safe metadata extraction with null checks"""
    
    @staticmethod
    def safe_float(value: Any, default: float = 0.0) -> Optional[float]:
        """Safely convert value to float, return default if None or invalid"""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_int(value: Any, default: int = 0) -> Optional[int]:
        """Safely convert value to int, return default if None or invalid"""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_str(value: Any, default: str = "") -> str:
        """Safely convert value to string, return default if None"""
        if value is None:
            return default
        return str(value)
    
    @staticmethod
    def safe_bool(value: Any, default: bool = False) -> bool:
        """Safely convert value to bool, return default if None"""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return bool(value)
    
    @staticmethod
    def safe_list(value: Any, default: Optional[List] = None) -> List:
        """Safely convert value to list, return default if None or invalid"""
        if value is None:
            return default if default is not None else []
        if isinstance(value, list):
            return value
        return default if default is not None else []
    
    @staticmethod
    def safe_dict(value: Any, default: Optional[Dict] = None) -> Dict:
        """Safely convert value to dict, return default if None or invalid"""
        if value is None:
            return default if default is not None else {}
        if isinstance(value, dict):
            return value
        return default if default is not None else {}
    
    @staticmethod
    def safe_rating_comparison(rating: Optional[float], threshold: float) -> bool:
        """Safely compare rating with threshold, handling None values"""
        if rating is None:
            return False
        try:
            return float(rating) >= threshold
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def safe_count_comparison(count: Optional[int], threshold: int) -> bool:
        """Safely compare count with threshold, handling None values"""
        if count is None:
            return False
        try:
            return int(count) >= threshold
        except (ValueError, TypeError):
            return False


@dataclass
class ProductMetadata:
    """Basic product metadata for filtering and context"""
    product_id: str
    category: str
    brand: str
    price: float
    price_range: str  # "budget", "mid-range", "premium", "luxury"
    availability: str
    rating: float
    rating_tier: str  # "excellent", "good", "average", "poor"
    feature_count: int
    specification_count: int


@dataclass
class EnhancedProductMetadata:
    """Enhanced metadata extracted from your actual product data structure"""

    # Core identifiers
    product_id: str  # _id
    product_name: str
    weburl: str  # SEO-friendly URL slug
    company: str

    # Visual and branding
    logo_key: Optional[str] = None
    logo_url: Optional[str] = None
    company_website: Optional[str] = None

    # Categorization
    categories: List[str] = None  # Resolved category names
    parent_categories: List[str] = None
    industry: List[str] = None
    industry_size: List[str] = None

    # Pricing information
    pricing_plans: List[Dict[str, Any]] = None
    has_free_plan: bool = False
    custom_pricing: bool = False
    pricing_currency: str = "USD"

    # Product details
    description: str = ""
    overview: str = ""
    usp: str = ""  # Unique selling proposition

    # Features and capabilities
    features: List[str] = None
    other_features: List[str] = None
    supports: List[str] = None

    # Ratings and reviews - use Optional to handle None values safely
    overall_rating: Optional[float] = 0.0
    ease_of_use: Optional[float] = 0.0
    breadth_of_features: Optional[float] = 0.0
    ease_of_implementation: Optional[float] = 0.0
    value_for_money: Optional[float] = 0.0
    customer_support: Optional[float] = 0.0
    total_reviews: Optional[int] = 0
    rating_tier: str = "unrated"  # excellent, good, average, poor, unrated

    # Technical information
    integrations: List[Dict[str, str]] = None
    tech_stack: List[str] = None
    languages: List[str] = None

    # Company information
    year_founded: Optional[int] = None
    hq_location: Optional[str] = None
    contact: Optional[str] = None
    support_email: Optional[str] = None

    # Status and verification
    is_active: bool = True
    is_verified: bool = False
    admin_verified: bool = False
    subscription_plan: str = "Basic"

    # Timestamps
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None

    # Computed fields for filtering
    price_range: str = "unknown"  # budget, mid-range, premium, luxury, custom
    feature_richness: str = "basic"  # basic, moderate, rich, comprehensive
    market_position: str = "standard"  # startup, standard, established, enterprise

    def __post_init__(self):
        """Compute derived fields after initialization with safe null handling"""
        # Safely initialize list fields
        if self.features is None:
            self.features = []
        if self.other_features is None:
            self.other_features = []
        if self.categories is None:
            self.categories = []
        if self.integrations is None:
            self.integrations = []
        
        # Safely normalize rating values to handle None
        self.overall_rating = MetadataValidator.safe_float(self.overall_rating, 0.0)
        self.ease_of_use = MetadataValidator.safe_float(self.ease_of_use, 0.0)
        self.breadth_of_features = MetadataValidator.safe_float(self.breadth_of_features, 0.0)
        self.ease_of_implementation = MetadataValidator.safe_float(self.ease_of_implementation, 0.0)
        self.value_for_money = MetadataValidator.safe_float(self.value_for_money, 0.0)
        self.customer_support = MetadataValidator.safe_float(self.customer_support, 0.0)
        self.total_reviews = MetadataValidator.safe_int(self.total_reviews, 0)

        # Compute feature richness
        total_features = len(self.features) + len(self.other_features)
        if total_features >= 20:
            self.feature_richness = "comprehensive"
        elif total_features >= 10:
            self.feature_richness = "rich"
        elif total_features >= 5:
            self.feature_richness = "moderate"
        else:
            self.feature_richness = "basic"

        # Compute market position based on company info and ratings (with safe comparisons)
        if self.year_founded and self.year_founded < 2010:
            self.market_position = "established"
        elif (MetadataValidator.safe_count_comparison(self.total_reviews, 100) and 
              MetadataValidator.safe_rating_comparison(self.overall_rating, 4.0)):
            self.market_position = "enterprise"
        elif self.year_founded and self.year_founded > 2018:
            self.market_position = "startup"
        else:
            self.market_position = "standard"

        # Compute rating tier - using safe comparisons
        if MetadataValidator.safe_rating_comparison(self.overall_rating, 4.5):
            self.rating_tier = "excellent"
        elif MetadataValidator.safe_rating_comparison(self.overall_rating, 3.5):
            self.rating_tier = "good"
        elif MetadataValidator.safe_rating_comparison(self.overall_rating, 2.5):
            self.rating_tier = "average"
        elif MetadataValidator.safe_rating_comparison(self.overall_rating, 0.01):
            self.rating_tier = "poor"
        else:
            self.rating_tier = "unrated"
