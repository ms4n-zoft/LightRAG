"""RFP and Semantic Search Optimized Product Normalizer"""

import logging
from typing import Dict, Any
from ..models.metadata import EnhancedProductMetadata

logger = logging.getLogger(__name__)


class RFPOptimizedNormalizer:
    """
    Purpose-built normalizer for RFP generation and semantic search

    Optimized for:
    1. RFP matching: capabilities, integrations, pricing, market fit
    2. Semantic search: searchable descriptions, use cases, problem-solving context

    Focus: Essential business context without over-engineering
    """

    def normalize_product(self, product_json: Dict[str, Any], metadata: EnhancedProductMetadata) -> str:
        """
        Generate RFP and search-optimized product text

        Strategy:
        - Lead with searchable business context
        - Emphasize capabilities and use cases
        - Include integration and pricing context for RFPs
        - Keep technical details minimal but present
        """

        # Start with clear business identity and use case
        text = f"""Product: {metadata.product_name}
Product ID: {metadata.product_id}
Company: {metadata.company}
Company Website: {metadata.company_website or 'Not specified'}
Category: {', '.join(metadata.categories) if metadata.categories else 'Software Solution'}"""

        # Add parent categories for broader context
        if metadata.parent_categories:
            text += f"\nParent Categories: {', '.join(metadata.parent_categories)}"

        text += f"\n\nBusiness Purpose: {metadata.description}\n\n"

        # Value proposition and detailed overview for semantic search
        if metadata.usp:
            text += f"Key Differentiators: {metadata.usp}\n\n"

        if metadata.overview:
            text += f"Solution Overview: {metadata.overview}\n\n"

        # Core capabilities (essential for RFP matching)
        if metadata.features or metadata.other_features:
            capabilities = []

            # Add core features
            if metadata.features:
                # Top 6 core features
                capabilities.extend(metadata.features[:6])

            # Add key capabilities
            if metadata.other_features:
                # Top 12 additional
                capabilities.extend(metadata.other_features[:12])

            text += f"Capabilities: {', '.join(capabilities)}\n\n"

        # Target market and use cases (critical for RFP matching)
        market_context = []
        if metadata.industry_size:
            market_context.append(
                f"Target Market: {', '.join(metadata.industry_size)}")
        if metadata.industry:
            market_context.append(
                f"Industries: {', '.join(metadata.industry)}")

        # Add headquarters for geographic/timezone considerations
        if metadata.hq_location:
            market_context.append(f"Headquarters: {metadata.hq_location}")

        if market_context:
            text += f"{' | '.join(market_context)}\n\n"

        # Integration ecosystem (essential for RFP technical requirements)
        if metadata.integrations:
            integration_names = [integration['name']
                                 for integration in metadata.integrations[:8]]
            text += f"Integrations: {', '.join(integration_names)}\n\n"

        # Business model and pricing (critical for RFP budget considerations)
        pricing_info = [f"Pricing: {metadata.price_range}"]
        if metadata.has_free_plan:
            pricing_info.append("Free Plan Available")
        if metadata.custom_pricing:
            pricing_info.append("Custom Pricing Available")

        text += f"{' | '.join(pricing_info)}\n"
        text += f"Customer Rating: {metadata.overall_rating}/5.0 ({metadata.total_reviews} reviews)\n"

        # Add detailed user experience ratings (important for RFP evaluation)
        ux_ratings = []
        if metadata.ease_of_use > 0:
            ux_ratings.append(f"Ease of Use: {metadata.ease_of_use}/5.0")
        if metadata.ease_of_implementation > 0:
            ux_ratings.append(
                f"Implementation: {metadata.ease_of_implementation}/5.0")
        if metadata.customer_support > 0:
            ux_ratings.append(f"Support: {metadata.customer_support}/5.0")
        if metadata.value_for_money > 0:
            ux_ratings.append(f"Value: {metadata.value_for_money}/5.0")

        if ux_ratings:
            text += f"User Experience: {' | '.join(ux_ratings)}\n"

        text += "\n"

        # Company credibility (important for RFP vendor evaluation)
        company_context = [
            f"Market Position: {metadata.market_position.title()}"]
        if metadata.year_founded:
            years_in_business = 2024 - metadata.year_founded
            company_context.append(f"Established: {years_in_business} years")

        text += f"{' | '.join(company_context)}\n"

        # Technical platform support (for RFP technical requirements)
        technical_specs = []
        if metadata.supports:
            technical_specs.append(
                f"Platform Support: {', '.join(metadata.supports[:6])}")

        # Technology stack for technical compatibility
        if metadata.tech_stack:
            technical_specs.append(
                f"Tech Stack: {', '.join(metadata.tech_stack[:6])}")

        if technical_specs:
            text += f"{' | '.join(technical_specs)}\n"

        # Language support for localization requirements
        if metadata.languages:
            text += f"Supported Languages: {', '.join(metadata.languages[:8])}\n"

        # Visual assets for branding context
        brand_assets = []
        if metadata.logo_key:
            brand_assets.append(f"Logo Key: {metadata.logo_key}")
        if metadata.logo_url:
            brand_assets.append(f"Logo URL: {metadata.logo_url}")

        if brand_assets:
            text += f"Brand Assets: {' | '.join(brand_assets)}\n"

        return text.strip()
