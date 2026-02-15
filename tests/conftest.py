"""
Shared test fixtures for KonvertIt test suite.
"""

import pytest

from app.core.models import (
    ComplianceResult,
    ListingDraft,
    ProfitBreakdown,
    RiskLevel,
    ScrapedProduct,
    SourceMarketplace,
    TargetMarketplace,
)


@pytest.fixture
def sample_amazon_product() -> ScrapedProduct:
    """A realistic Amazon scraped product for testing."""
    return ScrapedProduct(
        title="Anker USB C Charger 40W, 521 Charger (Nano Pro), PIQ 3.0 Durable Compact Fast Charger",
        price=25.99,
        currency="USD",
        brand="Anker",
        images=[
            "https://m.media-amazon.com/images/I/31lDxoycJsL._AC_.jpg",
            "https://m.media-amazon.com/images/I/41mniZKa2GL._AC_.jpg",
        ],
        description="Ultra-Compact: The cube-shaped charger is 38% smaller than the original 20W charger.",
        category="Cell Phone Accessories > Chargers & Power Adapters",
        availability="In Stock",
        source_marketplace=SourceMarketplace.AMAZON,
        source_url="https://www.amazon.com/dp/B09C5RG6KV",
        source_product_id="B09C5RG6KV",
        raw_data={"asin": "B09C5RG6KV"},
    )


@pytest.fixture
def sample_walmart_product() -> ScrapedProduct:
    """A realistic Walmart scraped product for testing."""
    return ScrapedProduct(
        title="onn. 32 Class HD (720P) LED Roku Smart TV (100012589)",
        price=98.00,
        currency="USD",
        brand="onn.",
        images=["https://i5.walmartimages.com/seo/onn-32-class-hd-tv.jpg"],
        description="The onn. 32\" Class HD (720P) LED Roku Smart TV gives you an outstanding viewing experience.",
        category="Electronics > TVs",
        availability="In Stock",
        source_marketplace=SourceMarketplace.WALMART,
        source_url="https://www.walmart.com/ip/100012589",
        source_product_id="100012589",
        raw_data={"product_id": "100012589"},
    )


@pytest.fixture
def sample_listing_draft() -> ListingDraft:
    """A prepared eBay listing draft for testing."""
    return ListingDraft(
        title="Anker USB C Charger 40W 521 Nano Pro PIQ 3.0 Compact",
        description_html="<p>Ultra-Compact fast charger by Anker.</p>",
        price=39.99,
        images=["https://m.media-amazon.com/images/I/31lDxoycJsL._AC_.jpg"],
        category_id="67580",
        condition="New",
        sku="KI-B09C5RG6KV",
        target_marketplace=TargetMarketplace.EBAY,
        source_product_id="B09C5RG6KV",
        source_marketplace=SourceMarketplace.AMAZON,
    )


@pytest.fixture
def sample_profit_breakdown() -> ProfitBreakdown:
    """A sample profit breakdown for testing."""
    return ProfitBreakdown(
        cost=25.99,
        sell_price=39.99,
        ebay_fee=5.30,
        payment_fee=1.46,
        shipping_cost=5.00,
        profit=2.24,
        margin_pct=5.6,
    )


@pytest.fixture
def compliant_result() -> ComplianceResult:
    """A passing compliance check result."""
    return ComplianceResult(
        is_compliant=True,
        violations=[],
        brand="Anker",
        risk_level=RiskLevel.CLEAR,
    )


@pytest.fixture
def vero_violation_result() -> ComplianceResult:
    """A failing VeRO compliance check result."""
    return ComplianceResult(
        is_compliant=False,
        violations=["Brand 'Nike' is on the eBay VeRO protected brands list"],
        brand="Nike",
        risk_level=RiskLevel.BLOCKED,
    )
