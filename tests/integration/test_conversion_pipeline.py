"""
Integration tests for the full KonvertIt conversion pipeline.

Tests end-to-end flow with REAL service instances (ComplianceService,
ProfitEngine, EbayConverter) but MOCKED external I/O (scrapers, eBay API).

This ensures all internal components (title optimizer, description builder,
profit calculator, compliance checker) work together correctly through
the ConversionService orchestrator.

Key differences from unit tests:
    - Uses real ComplianceService, ProfitEngine, EbayConverter instances
    - Only mocks external I/O: scraper.scrape() and lister.create_listing()
    - Validates data flows correctly between components
    - Tests real title optimization, description building, profit calculation
    - Verifies SSE integration with real ConversionService callbacks
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.converters.ebay_converter import EbayConverter
from app.core.exceptions import (
    ComplianceViolationError,
    ListingError,
    ScrapingError,
)
from app.core.models import (
    ComplianceResult,
    ConversionStatus,
    ListingDraft,
    ListingResult,
    ListingStatus,
    ProfitBreakdown,
    RiskLevel,
    ScrapedProduct,
    SourceMarketplace,
    TargetMarketplace,
)
from app.services.compliance_service import ComplianceService
from app.services.conversion_service import (
    BulkConversionProgress,
    ConversionResult,
    ConversionService,
    ConversionStep,
)
from app.services.profit_engine import ProfitEngine
from app.services.sse_manager import SSEEventType, SSEProgressManager


# ─── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def mock_proxy_manager():
    return MagicMock()


@pytest.fixture
def mock_browser_manager():
    return MagicMock()


@pytest.fixture
def real_compliance():
    """Real ComplianceService with VeRO brand list."""
    return ComplianceService()


@pytest.fixture
def real_profit_engine():
    """Real ProfitEngine with actual fee calculations."""
    return ProfitEngine()


@pytest.fixture
def real_converter():
    """Real EbayConverter with title optimizer + description builder."""
    return EbayConverter()


@pytest.fixture
def mock_lister():
    """Mock eBay lister — simulates successful listing creation."""
    lister = AsyncMock()
    lister.create_listing = AsyncMock(return_value=ListingResult(
        marketplace_item_id="EBAY-12345678",
        status=ListingStatus.ACTIVE,
        url="https://www.ebay.com/itm/EBAY-12345678",
    ))
    return lister


@pytest.fixture
def amazon_product():
    """Realistic Amazon product for pipeline testing."""
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
def walmart_product():
    """Realistic Walmart product for pipeline testing."""
    return ScrapedProduct(
        title="onn. 32 Class HD (720P) LED Roku Smart TV (100012589)",
        price=98.00,
        currency="USD",
        brand="onn.",
        images=["https://i5.walmartimages.com/seo/onn-32-class-hd-tv.jpg"],
        description="The onn. 32 inch HD LED Roku Smart TV gives you outstanding viewing.",
        category="Electronics > TVs",
        availability="In Stock",
        source_marketplace=SourceMarketplace.WALMART,
        source_url="https://www.walmart.com/ip/100012589",
        source_product_id="100012589",
        raw_data={"product_id": "100012589"},
    )


@pytest.fixture
def vero_blocked_product():
    """Product from a VeRO-protected brand (Nike)."""
    return ScrapedProduct(
        title="Nike Air Max 90 Men's Running Shoes - White/Black",
        price=130.00,
        brand="Nike",
        images=["https://example.com/nike.jpg"],
        description="Classic Nike Air Max 90 with visible Air unit.",
        category="Shoes > Athletic Shoes",
        source_marketplace=SourceMarketplace.AMAZON,
        source_url="https://www.amazon.com/dp/B0NIKE001",
        source_product_id="B0NIKE001",
    )


@pytest.fixture
def restricted_keyword_product():
    """Product with restricted keywords in description."""
    return ScrapedProduct(
        title="Designer Wallet Leather Bifold Card Holder",
        price=29.99,
        brand="GenericBrand",
        images=["https://example.com/wallet.jpg"],
        description="This is a high quality replica of a designer wallet, inspired by luxury brands.",
        category="Clothing > Accessories > Wallets",
        source_marketplace=SourceMarketplace.AMAZON,
        source_url="https://www.amazon.com/dp/B0WALLET01",
        source_product_id="B0WALLET01",
    )


@pytest.fixture
def mock_scraper_for(amazon_product):
    """Factory for creating a mock scraper that returns a specific product."""
    def _create(product=None):
        scraper = AsyncMock()
        scraper.scrape = AsyncMock(return_value=product or amazon_product)
        return scraper
    return _create


@pytest.fixture
def integration_service(
    mock_proxy_manager,
    mock_browser_manager,
    real_compliance,
    real_profit_engine,
    real_converter,
):
    """ConversionService with real internal services, no lister (draft mode)."""
    return ConversionService(
        proxy_manager=mock_proxy_manager,
        browser_manager=mock_browser_manager,
        compliance_service=real_compliance,
        profit_engine=real_profit_engine,
        ebay_converter=real_converter,
        ebay_lister=None,
    )


@pytest.fixture
def integration_service_with_lister(
    mock_proxy_manager,
    mock_browser_manager,
    real_compliance,
    real_profit_engine,
    real_converter,
    mock_lister,
):
    """ConversionService with real internal services + mock lister (publish mode)."""
    return ConversionService(
        proxy_manager=mock_proxy_manager,
        browser_manager=mock_browser_manager,
        compliance_service=real_compliance,
        profit_engine=real_profit_engine,
        ebay_converter=real_converter,
        ebay_lister=mock_lister,
    )


# ─── Happy Path: Single Conversion ─────────────────────────


class TestHappyPathSingleConversion:
    """End-to-end happy path tests for single URL conversion."""

    @pytest.mark.asyncio
    async def test_amazon_product_draft_mode(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Full pipeline: Amazon product → compliant → converted → priced → draft."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
                publish=False,
            )

        # Overall status
        assert result.status == ConversionStatus.COMPLETED
        assert result.step == ConversionStep.COMPLETE
        assert result.error == ""
        assert result.is_successful
        assert result.completed_at is not None

        # Scraped product preserved
        assert result.product is not None
        assert result.product.title == amazon_product.title
        assert result.product.price == 25.99
        assert result.product.brand == "Anker"

        # Compliance passed (Anker is not VeRO-blocked)
        assert result.compliance is not None
        assert result.compliance.is_compliant is True
        assert result.compliance.risk_level != RiskLevel.BLOCKED

        # Title was optimized (real TitleOptimizer ran)
        assert result.draft is not None
        assert len(result.draft.title) <= 80
        assert result.draft.title  # Non-empty

        # Description was built (real DescriptionBuilder ran)
        assert result.draft.description_html
        assert "Anker" in result.draft.description_html or "anker" in result.draft.description_html.lower()

        # SKU generated
        assert result.draft.sku == "KI-B09C5RG6KV"

        # Profit calculated (real ProfitEngine ran)
        assert result.profit is not None
        assert result.profit.cost == 25.99
        assert result.profit.sell_price > result.profit.cost  # Markup applied
        assert result.profit.ebay_fee > 0
        assert result.profit.payment_fee > 0
        assert result.profit.shipping_cost > 0

        # Draft mode — listing is draft status
        assert result.listing is not None
        assert result.listing.status == ListingStatus.DRAFT

    @pytest.mark.asyncio
    async def test_walmart_product_draft_mode(
        self, integration_service, mock_scraper_for, walmart_product
    ):
        """Full pipeline: Walmart product → compliant → converted → priced → draft."""
        mock_scraper = mock_scraper_for(walmart_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.walmart.com/ip/100012589",
                user_id="user-123",
            )

        assert result.status == ConversionStatus.COMPLETED
        assert result.product.price == 98.00
        assert result.draft.sku == "KI-100012589"
        assert result.profit.cost == 98.00
        assert result.profit.sell_price > 98.00

    @pytest.mark.asyncio
    async def test_publish_mode_calls_lister(
        self, integration_service_with_lister, mock_scraper_for, mock_lister, amazon_product
    ):
        """Publish mode: pipeline creates listing via eBay lister."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service_with_lister, "_get_scraper", return_value=mock_scraper):
            result = await integration_service_with_lister.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
                publish=True,
            )

        assert result.status == ConversionStatus.COMPLETED
        assert result.listing.status == ListingStatus.ACTIVE
        assert result.listing.marketplace_item_id == "EBAY-12345678"
        assert "ebay.com" in result.listing.url

        # Lister was called with the draft
        mock_lister.create_listing.assert_called_once()
        call_args = mock_lister.create_listing.call_args
        draft_passed = call_args[0][0]  # First positional arg
        assert isinstance(draft_passed, ListingDraft)
        assert draft_passed.sku == "KI-B09C5RG6KV"

    @pytest.mark.asyncio
    async def test_draft_price_updated_by_profit_engine(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Draft price should be the profit-engine-suggested price, not the original."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
            )

        # Draft price should match suggested price (not the raw cost)
        assert result.draft.price == result.profit.sell_price
        assert result.draft.price != amazon_product.price  # Not the original cost


# ─── Custom Sell Price ─────────────────────────────────────


class TestCustomSellPrice:
    """Tests for user-provided custom selling price."""

    @pytest.mark.asyncio
    async def test_custom_price_overrides_auto(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Custom sell_price should override automatic price suggestion."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
                sell_price=99.99,
            )

        assert result.status == ConversionStatus.COMPLETED
        assert result.draft.price == 99.99
        assert result.profit.sell_price == 99.99
        assert result.profit.cost == 25.99
        # With $99.99 sell on $25.99 cost, profit should be positive
        assert result.profit.is_profitable

    @pytest.mark.asyncio
    async def test_low_custom_price_shows_loss(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """A very low custom price should show negative profit margin."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
                sell_price=1.00,
            )

        assert result.status == ConversionStatus.COMPLETED
        assert result.profit.sell_price == 1.00
        assert result.profit.profit < 0  # Selling at a loss
        assert not result.profit.is_profitable


# ─── Compliance Integration ────────────────────────────────


class TestComplianceIntegration:
    """Tests for real compliance checking within the pipeline."""

    @pytest.mark.asyncio
    async def test_vero_brand_blocks_conversion(
        self, integration_service, mock_scraper_for, vero_blocked_product
    ):
        """VeRO-protected brand should block the conversion."""
        mock_scraper = mock_scraper_for(vero_blocked_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B0NIKE001",
                user_id="user-123",
            )

        assert result.status == ConversionStatus.FAILED
        assert result.step == ConversionStep.FAILED
        assert "Compliance violation" in result.error or "Nike" in result.error

        # Product was scraped before compliance blocked it
        assert result.product is not None
        assert result.compliance is not None
        assert result.compliance.risk_level == RiskLevel.BLOCKED

        # No draft/profit/listing was generated
        assert result.draft is None
        assert result.profit is None

    @pytest.mark.asyncio
    async def test_restricted_keywords_produce_warning_but_continue(
        self, integration_service, mock_scraper_for, restricted_keyword_product
    ):
        """Products with restricted keywords should get warnings but still convert."""
        mock_scraper = mock_scraper_for(restricted_keyword_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B0WALLET01",
                user_id="user-123",
            )

        assert result.status == ConversionStatus.COMPLETED
        assert result.compliance is not None
        assert result.compliance.risk_level == RiskLevel.WARNING
        assert len(result.compliance.violations) > 0
        # "replica" and/or "inspired by" should be flagged
        violations_text = " ".join(result.compliance.violations).lower()
        assert "replica" in violations_text or "inspired" in violations_text

        # Despite warning, conversion completed successfully
        assert result.draft is not None
        assert result.profit is not None

    @pytest.mark.asyncio
    async def test_clean_brand_passes_compliance(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """A non-VeRO brand should pass compliance with CLEAR risk."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
            )

        assert result.compliance.risk_level == RiskLevel.CLEAR
        assert result.compliance.is_compliant is True
        assert len(result.compliance.violations) == 0


# ─── Error Handling ────────────────────────────────────────


class TestErrorHandling:
    """Tests for error scenarios at each pipeline stage."""

    @pytest.mark.asyncio
    async def test_scraping_error_fails_gracefully(
        self, integration_service
    ):
        """ScrapingError should result in FAILED with meaningful message."""
        mock_scraper = AsyncMock()
        mock_scraper.scrape = AsyncMock(
            side_effect=ScrapingError("Bot detection triggered — CAPTCHA page")
        )

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09FAIL123",
                user_id="user-123",
            )

        assert result.status == ConversionStatus.FAILED
        assert result.step == ConversionStep.FAILED
        assert "Scraping failed" in result.error
        assert "Bot detection" in result.error
        assert result.product is None

    @pytest.mark.asyncio
    async def test_listing_error_fails_gracefully(
        self, integration_service_with_lister, mock_scraper_for, mock_lister, amazon_product
    ):
        """ListingError from eBay API should fail with listing-specific message."""
        mock_scraper = mock_scraper_for(amazon_product)
        mock_lister.create_listing.side_effect = ListingError(
            "eBay API error (400): Invalid category ID"
        )

        with patch.object(integration_service_with_lister, "_get_scraper", return_value=mock_scraper):
            result = await integration_service_with_lister.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
                publish=True,
            )

        assert result.status == ConversionStatus.FAILED
        assert "Listing failed" in result.error
        assert "Invalid category" in result.error

        # Product, compliance, draft, profit should still be populated
        assert result.product is not None
        assert result.compliance is not None
        assert result.draft is not None
        assert result.profit is not None

    @pytest.mark.asyncio
    async def test_unsupported_url_fails(self, integration_service):
        """Unsupported marketplace URL should fail immediately."""
        result = await integration_service.convert_url(
            url="https://www.etsy.com/listing/123456",
            user_id="user-123",
        )

        assert result.status == ConversionStatus.FAILED
        assert "Unsupported" in result.error
        assert result.product is None

    @pytest.mark.asyncio
    async def test_unexpected_exception_caught(self, integration_service):
        """Unexpected exceptions should be caught and reported."""
        mock_scraper = AsyncMock()
        mock_scraper.scrape = AsyncMock(
            side_effect=RuntimeError("Something completely unexpected")
        )

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09UNEXP01",
                user_id="user-123",
            )

        assert result.status == ConversionStatus.FAILED
        assert "Unexpected error" in result.error
        assert "RuntimeError" in result.error


# ─── Title Optimization Integration ────────────────────────


class TestTitleOptimizationIntegration:
    """Tests that real TitleOptimizer runs correctly in the pipeline."""

    @pytest.mark.asyncio
    async def test_long_title_truncated_to_80_chars(
        self, integration_service, mock_scraper_for
    ):
        """Titles exceeding 80 chars should be optimized by the real TitleOptimizer."""
        long_product = ScrapedProduct(
            title=(
                "Amazon's Choice Stainless Steel Professional Grade "
                "Waterproof Bluetooth Portable Rechargeable "
                "Wireless Speaker System with Built-in Microphone "
                "and LED Lights for Indoor Outdoor Use"
            ),
            price=49.99,
            brand="TestBrand",
            images=["https://example.com/img.jpg"],
            description="Great speaker",
            category="Electronics > Speakers",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/B09LONG001",
            source_product_id="B09LONG001",
        )
        mock_scraper = mock_scraper_for(long_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09LONG001",
                user_id="user-123",
            )

        assert result.status == ConversionStatus.COMPLETED
        assert len(result.draft.title) <= 80
        # TitleOptimizer should have applied abbreviations/noise removal
        assert "Amazon's Choice" not in result.draft.title

    @pytest.mark.asyncio
    async def test_short_title_preserved(
        self, integration_service, mock_scraper_for
    ):
        """Short titles that already fit should be preserved (mostly)."""
        short_product = ScrapedProduct(
            title="USB Cable 6ft White",
            price=5.99,
            brand="Basics",
            images=[],
            description="Basic USB cable",
            category="Electronics",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/B09SHORT01",
            source_product_id="B09SHORT01",
        )
        mock_scraper = mock_scraper_for(short_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09SHORT01",
                user_id="user-123",
            )

        assert result.status == ConversionStatus.COMPLETED
        assert len(result.draft.title) <= 80
        # Core words should remain
        assert "USB" in result.draft.title
        assert "Cable" in result.draft.title


# ─── Description Builder Integration ──────────────────────


class TestDescriptionBuilderIntegration:
    """Tests that real DescriptionBuilder produces valid HTML in the pipeline."""

    @pytest.mark.asyncio
    async def test_description_contains_product_info(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Generated description should contain key product details."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
            )

        html = result.draft.description_html
        assert html  # Non-empty
        # Should contain the product title somewhere
        assert "Anker" in html
        # Should have KonvertIt branding (modern template default)
        assert "KonvertIt" in html
        # Should have inline CSS (eBay strips <style> tags)
        assert "style=" in html.lower()

    @pytest.mark.asyncio
    async def test_description_has_image_if_provided(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Description should include hero image when product has images."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
            )

        html = result.draft.description_html
        assert "<img" in html.lower()
        assert "31lDxoycJsL" in html  # From the Amazon image URL


# ─── Profit Engine Integration ─────────────────────────────


class TestProfitEngineIntegration:
    """Tests that real ProfitEngine calculates correctly in the pipeline."""

    @pytest.mark.asyncio
    async def test_profit_breakdown_has_all_fees(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """ProfitBreakdown should have non-zero eBay fees, payment fees, shipping."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
            )

        profit = result.profit
        assert profit.cost == 25.99
        assert profit.sell_price > 0
        assert profit.ebay_fee > 0  # Real eBay fee rate applied
        assert profit.payment_fee > 0  # 2.9% + $0.30
        assert profit.shipping_cost > 0  # Default $5.00
        assert profit.total_fees > 0
        assert profit.margin_pct > 0  # Should be profitable at target margin

    @pytest.mark.asyncio
    async def test_expensive_product_has_higher_fees(
        self, integration_service, mock_scraper_for, walmart_product
    ):
        """Higher-priced products should have proportionally higher fees."""
        mock_scraper = mock_scraper_for(walmart_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.walmart.com/ip/100012589",
                user_id="user-123",
            )

        profit = result.profit
        # $98 product → higher absolute fees
        assert profit.cost == 98.00
        assert profit.ebay_fee > 10  # 13.25% of >$100 sell price
        assert profit.sell_price > 98.00  # Markup applied


# ─── Bulk Conversion Integration ───────────────────────────


class TestBulkConversionIntegration:
    """Integration tests for bulk URL conversion."""

    @pytest.mark.asyncio
    async def test_bulk_all_succeed(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """All URLs in a bulk conversion should succeed with real services."""
        mock_scraper = mock_scraper_for(amazon_product)
        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
            "https://www.amazon.com/dp/B09TEST003",
        ]

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            progress = await integration_service.convert_bulk(
                urls=urls, user_id="user-123"
            )

        assert progress.total == 3
        assert progress.completed == 3
        assert progress.failed == 0
        assert progress.is_done
        assert progress.progress_pct == 100.0

        # Each result should have full pipeline data
        for r in progress.results:
            assert r.status == ConversionStatus.COMPLETED
            assert r.product is not None
            assert r.compliance is not None
            assert r.draft is not None
            assert r.profit is not None

    @pytest.mark.asyncio
    async def test_bulk_mixed_success_and_failure(
        self, integration_service, mock_scraper_for, amazon_product, vero_blocked_product
    ):
        """Bulk with mix of compliant and VeRO-blocked products."""
        call_count = 0

        async def side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return vero_blocked_product  # Nike — blocked
            return amazon_product  # Anker — passes

        mock_scraper = AsyncMock()
        mock_scraper.scrape = AsyncMock(side_effect=side_effect)

        urls = [
            "https://www.amazon.com/dp/B09OK001",
            "https://www.amazon.com/dp/B09NIKE01",
            "https://www.amazon.com/dp/B09OK002",
        ]

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            progress = await integration_service.convert_bulk(
                urls=urls, user_id="user-123"
            )

        assert progress.total == 3
        assert progress.completed == 2
        assert progress.failed == 1

        # First succeeded
        assert progress.results[0].status == ConversionStatus.COMPLETED
        # Second failed (Nike blocked)
        assert progress.results[1].status == ConversionStatus.FAILED
        assert "Nike" in progress.results[1].error or "Compliance" in progress.results[1].error
        # Third succeeded
        assert progress.results[2].status == ConversionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_bulk_with_scraping_failure(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Bulk with a scraping failure mid-batch."""
        call_count = 0

        async def side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ScrapingError("Rate limited by Amazon")
            return amazon_product

        mock_scraper = AsyncMock()
        mock_scraper.scrape = AsyncMock(side_effect=side_effect)

        urls = [
            "https://www.amazon.com/dp/B09OK001",
            "https://www.amazon.com/dp/B09FAIL01",
            "https://www.amazon.com/dp/B09OK002",
        ]

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            progress = await integration_service.convert_bulk(
                urls=urls, user_id="user-123"
            )

        assert progress.completed == 2
        assert progress.failed == 1
        assert progress.results[1].status == ConversionStatus.FAILED
        assert "Scraping failed" in progress.results[1].error

    @pytest.mark.asyncio
    async def test_bulk_empty_list(self, integration_service):
        """Empty URL list should return empty progress."""
        progress = await integration_service.convert_bulk(
            urls=[], user_id="user-123"
        )
        assert progress.total == 0
        assert progress.is_done
        assert len(progress.results) == 0


# ─── Bulk Cancellation ────────────────────────────────────


class TestBulkCancellation:
    """Tests for cancelling bulk conversions mid-flight."""

    @pytest.mark.asyncio
    async def test_cancellation_stops_processing(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """cancel_check returning True should stop after current item."""
        mock_scraper = mock_scraper_for(amazon_product)
        cancel_count = 0

        def cancel_check():
            nonlocal cancel_count
            cancel_count += 1
            return cancel_count > 2  # Cancel after 2nd item

        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
            "https://www.amazon.com/dp/B09TEST003",
            "https://www.amazon.com/dp/B09TEST004",
            "https://www.amazon.com/dp/B09TEST005",
        ]

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            progress = await integration_service.convert_bulk(
                urls=urls,
                user_id="user-123",
                cancel_check=cancel_check,
            )

        # Should have processed exactly 2 items before cancellation
        assert len(progress.results) == 2
        assert progress.total == 5  # Total is set upfront
        assert progress.completed == 2

    @pytest.mark.asyncio
    async def test_immediate_cancellation(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Cancelling immediately should process zero items."""
        mock_scraper = mock_scraper_for(amazon_product)

        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
        ]

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            progress = await integration_service.convert_bulk(
                urls=urls,
                user_id="user-123",
                cancel_check=lambda: True,  # Always cancelled
            )

        assert len(progress.results) == 0
        assert progress.completed == 0


# ─── Callback Integration ─────────────────────────────────


class TestCallbackIntegration:
    """Tests for on_step and on_item_complete callbacks with real services."""

    @pytest.mark.asyncio
    async def test_on_step_callback_order(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """on_step callback should fire in correct pipeline order."""
        mock_scraper = mock_scraper_for(amazon_product)
        steps_recorded = []

        async def on_step(url, step):
            steps_recorded.append(step)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
                on_step=on_step,
            )

        assert result.status == ConversionStatus.COMPLETED

        # Verify step order
        expected_steps = [
            ConversionStep.SCRAPING.value,
            ConversionStep.COMPLIANCE.value,
            ConversionStep.CONVERTING.value,
            ConversionStep.PRICING.value,
            ConversionStep.COMPLETE.value,
        ]
        assert steps_recorded == expected_steps

    @pytest.mark.asyncio
    async def test_on_step_callback_with_publish(
        self, integration_service_with_lister, mock_scraper_for, amazon_product
    ):
        """on_step in publish mode should include LISTING step."""
        mock_scraper = mock_scraper_for(amazon_product)
        steps_recorded = []

        async def on_step(url, step):
            steps_recorded.append(step)

        with patch.object(integration_service_with_lister, "_get_scraper", return_value=mock_scraper):
            result = await integration_service_with_lister.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
                publish=True,
                on_step=on_step,
            )

        assert result.status == ConversionStatus.COMPLETED
        assert ConversionStep.LISTING.value in steps_recorded

    @pytest.mark.asyncio
    async def test_on_item_complete_callback(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """on_item_complete should fire for each bulk item with correct data."""
        mock_scraper = mock_scraper_for(amazon_product)
        completed_items = []

        async def on_item_complete(index, url, success, result_data, error):
            completed_items.append({
                "index": index,
                "url": url,
                "success": success,
                "has_data": result_data is not None,
                "error": error,
            })

        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
        ]

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            progress = await integration_service.convert_bulk(
                urls=urls,
                user_id="user-123",
                on_item_complete=on_item_complete,
            )

        assert len(completed_items) == 2

        # First item
        assert completed_items[0]["index"] == 0
        assert completed_items[0]["success"] is True
        assert completed_items[0]["has_data"] is True
        assert completed_items[0]["error"] == ""

        # Second item
        assert completed_items[1]["index"] == 1
        assert completed_items[1]["success"] is True

    @pytest.mark.asyncio
    async def test_on_item_complete_with_failure(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """on_item_complete should report failures with error message."""
        call_count = 0

        async def side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ScrapingError("Blocked by Amazon")
            return amazon_product

        mock_scraper = AsyncMock()
        mock_scraper.scrape = AsyncMock(side_effect=side_effect)
        completed_items = []

        async def on_item_complete(index, url, success, result_data, error):
            completed_items.append({
                "index": index,
                "success": success,
                "has_data": result_data is not None,
                "error": error,
            })

        urls = [
            "https://www.amazon.com/dp/B09OK001",
            "https://www.amazon.com/dp/B09FAIL01",
            "https://www.amazon.com/dp/B09OK002",
        ]

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            await integration_service.convert_bulk(
                urls=urls,
                user_id="user-123",
                on_item_complete=on_item_complete,
            )

        assert len(completed_items) == 3
        # First: success
        assert completed_items[0]["success"] is True
        # Second: failure
        assert completed_items[1]["success"] is False
        assert completed_items[1]["has_data"] is False
        assert "Blocked" in completed_items[1]["error"]
        # Third: success
        assert completed_items[2]["success"] is True


# ─── SSE Progress Manager Integration ─────────────────────


class TestSSEIntegration:
    """Tests for SSE event streaming with real ConversionService."""

    @pytest.mark.asyncio
    async def test_sse_job_lifecycle(self):
        """SSE manager should track job from start to finish."""
        manager = SSEProgressManager(heartbeat_interval=30.0)

        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
        ]
        job_id = manager.create_job(urls)

        # Job exists
        job = manager.get_job(job_id)
        assert job is not None
        assert job.total == 2
        assert job.completed == 0

        # Emit events
        await manager.emit_job_started(job_id)
        await manager.emit_item_started(job_id, 0, urls[0])
        await manager.emit_item_step(job_id, 0, urls[0], "scraping")
        await manager.emit_item_completed(job_id, 0, urls[0], success=True)

        # Check progress updated
        assert job.completed == 1

        await manager.emit_item_started(job_id, 1, urls[1])
        await manager.emit_item_completed(job_id, 1, urls[1], success=False, error="Failed")

        assert job.completed == 1
        assert job.failed == 1

        await manager.emit_job_completed(job_id)

        # Verify all events in queue
        queue = manager._queues[job_id]
        events = []
        while not queue.empty():
            event = await queue.get()
            if event is not None:
                events.append(event)

        # Should have: job_started, item_started, item_step,
        # item_completed, job_progress, item_started,
        # item_completed, job_progress, job_completed
        event_types = [e.event for e in events]
        assert SSEEventType.JOB_STARTED in event_types
        assert SSEEventType.ITEM_STARTED in event_types
        assert SSEEventType.ITEM_STEP in event_types
        assert SSEEventType.ITEM_COMPLETED in event_types
        assert SSEEventType.JOB_PROGRESS in event_types
        assert SSEEventType.JOB_COMPLETED in event_types

    @pytest.mark.asyncio
    async def test_sse_cancel_stops_job(self):
        """Cancelling an SSE job should mark it as cancelled."""
        manager = SSEProgressManager()

        job_id = manager.create_job(["url1", "url2", "url3"])
        assert not manager.get_job(job_id).is_cancelled

        result = manager.cancel_job(job_id)
        assert result is True
        assert manager.get_job(job_id).is_cancelled

    @pytest.mark.asyncio
    async def test_sse_event_format(self):
        """SSE events should be formatted as valid SSE text blocks."""
        manager = SSEProgressManager()
        job_id = manager.create_job(["url1"])

        await manager.emit_job_started(job_id)

        queue = manager._queues[job_id]
        event = await queue.get()
        formatted = event.format()

        assert "event: job_started" in formatted
        assert "data: " in formatted
        assert formatted.endswith("\n\n")  # SSE spec: double newline

    @pytest.mark.asyncio
    async def test_sse_cleanup_finished_jobs(self):
        """cleanup_finished_jobs should remove completed jobs."""
        manager = SSEProgressManager()

        job1 = manager.create_job(["url1"])
        job2 = manager.create_job(["url2"])

        # Complete job1
        await manager.emit_item_completed(job1, 0, "url1", success=True)
        await manager.emit_job_completed(job1)

        # job1 is done, job2 is still active
        assert manager.get_job(job1).is_done
        assert not manager.get_job(job2).is_done

        cleaned = manager.cleanup_finished_jobs()
        assert cleaned == 1
        assert manager.get_job(job1) is None
        assert manager.get_job(job2) is not None


# ─── Result Serialization ─────────────────────────────────


class TestResultSerialization:
    """Tests for end-to-end result serialization through the pipeline."""

    @pytest.mark.asyncio
    async def test_successful_result_to_dict(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Successful conversion result should serialize completely."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09C5RG6KV",
                user_id="user-123",
            )

        d = result.to_dict()

        # Top level
        assert d["status"] == "completed"
        assert d["step"] == "complete"
        assert d["url"] == "https://www.amazon.com/dp/B09C5RG6KV"
        assert d["error"] == ""

        # Product section
        assert d["product"] is not None
        assert d["product"]["title"] == amazon_product.title
        assert d["product"]["price"] == 25.99
        assert d["product"]["brand"] == "Anker"
        assert d["product"]["source_product_id"] == "B09C5RG6KV"

        # Compliance section
        assert d["compliance"] is not None
        assert d["compliance"]["is_compliant"] is True
        assert d["compliance"]["risk_level"] == "clear"

        # Draft section
        assert d["draft"] is not None
        assert len(d["draft"]["title"]) <= 80
        assert d["draft"]["price"] > 0
        assert d["draft"]["sku"] == "KI-B09C5RG6KV"

        # Profit section
        assert d["profit"] is not None
        assert d["profit"]["cost"] == 25.99
        assert d["profit"]["sell_price"] > 0
        assert d["profit"]["profit"] is not None
        assert d["profit"]["total_fees"] > 0

        # Listing section
        assert d["listing"] is not None
        assert d["listing"]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_failed_result_to_dict(
        self, integration_service
    ):
        """Failed conversion result should serialize with error info."""
        mock_scraper = AsyncMock()
        mock_scraper.scrape = AsyncMock(side_effect=ScrapingError("Timeout"))

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            result = await integration_service.convert_url(
                url="https://www.amazon.com/dp/B09FAIL123",
                user_id="user-123",
            )

        d = result.to_dict()
        assert d["status"] == "failed"
        assert d["product"] is None
        assert d["compliance"] is None
        assert d["draft"] is None
        assert d["profit"] is None
        assert "Timeout" in d["error"]

    @pytest.mark.asyncio
    async def test_bulk_progress_to_dict(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Bulk progress should serialize all results."""
        mock_scraper = mock_scraper_for(amazon_product)

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            progress = await integration_service.convert_bulk(
                urls=[
                    "https://www.amazon.com/dp/B09TEST001",
                    "https://www.amazon.com/dp/B09TEST002",
                ],
                user_id="user-123",
            )

        d = progress.to_dict()
        assert d["total"] == 2
        assert d["completed"] == 2
        assert d["failed"] == 0
        assert d["pending"] == 0
        assert d["progress_pct"] == 100.0
        assert len(d["results"]) == 2
        assert all(r["status"] == "completed" for r in d["results"])


# ─── Cross-Marketplace Integration ────────────────────────


class TestCrossMarketplace:
    """Tests for handling products from different source marketplaces."""

    @pytest.mark.asyncio
    async def test_amazon_and_walmart_in_same_bulk(
        self, integration_service, amazon_product, walmart_product
    ):
        """Bulk should handle mixed Amazon + Walmart URLs."""
        call_count = 0

        async def side_effect(url):
            nonlocal call_count
            call_count += 1
            if "walmart" in url.lower():
                return walmart_product
            return amazon_product

        mock_scraper = AsyncMock()
        mock_scraper.scrape = AsyncMock(side_effect=side_effect)

        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.walmart.com/ip/100012589",
        ]

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            progress = await integration_service.convert_bulk(
                urls=urls, user_id="user-123"
            )

        assert progress.total == 2
        assert progress.completed == 2

        # Verify different products processed
        assert progress.results[0].product.brand == "Anker"
        assert progress.results[1].product.brand == "onn."

        # Both should have valid drafts
        assert progress.results[0].draft.sku == "KI-B09C5RG6KV"
        assert progress.results[1].draft.sku == "KI-100012589"

    @pytest.mark.asyncio
    async def test_unsupported_url_in_bulk_doesnt_stop_others(
        self, integration_service, mock_scraper_for, amazon_product
    ):
        """Unsupported URLs in bulk should fail individually, not stop the batch."""
        mock_scraper = mock_scraper_for(amazon_product)

        urls = [
            "https://www.amazon.com/dp/B09OK001",
            "https://www.etsy.com/listing/123",  # Unsupported
            "https://www.amazon.com/dp/B09OK002",
        ]

        with patch.object(integration_service, "_get_scraper", return_value=mock_scraper):
            progress = await integration_service.convert_bulk(
                urls=urls, user_id="user-123"
            )

        assert progress.total == 3
        assert progress.completed == 2
        assert progress.failed == 1
        assert "Unsupported" in progress.results[1].error
