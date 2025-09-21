"""Metadata models for product data"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


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

    # Ratings and reviews
    overall_rating: float = 0.0
    ease_of_use: float = 0.0
    breadth_of_features: float = 0.0
    ease_of_implementation: float = 0.0
    value_for_money: float = 0.0
    customer_support: float = 0.0
    total_reviews: int = 0
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
        """Compute derived fields after initialization"""
        if self.features is None:
            self.features = []
        if self.other_features is None:
            self.other_features = []
        if self.categories is None:
            self.categories = []
        if self.integrations is None:
            self.integrations = []

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

        # Compute market position based on company info and ratings
        if self.year_founded and self.year_founded < 2010:
            self.market_position = "established"
        elif self.total_reviews > 100 and self.overall_rating > 4.0:
            self.market_position = "enterprise"
        elif self.year_founded and self.year_founded > 2018:
            self.market_position = "startup"
        else:
            self.market_position = "standard"

        # Compute rating tier
        if self.overall_rating >= 4.5:
            self.rating_tier = "excellent"
        elif self.overall_rating >= 3.5:
            self.rating_tier = "good"
        elif self.overall_rating >= 2.5:
            self.rating_tier = "average"
        elif self.overall_rating > 0:
            self.rating_tier = "poor"
        else:
            self.rating_tier = "unrated"
