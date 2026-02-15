"""
Unit tests for ConversionService.

Tests the full pipeline orchestration: scrape → compliance → convert → price → list.
Uses mocked scrapers, compliance, and listers to test orchestration logic.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ComplianceViolationError, ConversionError, ScrapingError
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
from app.services.conversion_service import (
    BulkConversionProgress,
    ConversionResult,
    ConversionService,
    ConversionStep,
    _detect_marketplace,
)


# ─── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def mock_proxy_manager():
    return MagicMock()


@pytest.fixture
def mock_browser_manager():
    return MagicMock()


@pytest.fixture
def mock_scraper():
    scraper = AsyncMock()
    scraper.scrape = AsyncMock(return_value=ScrapedProduct(
        title="Test Product - Premium Quality Widget",
        price=25.99,
        brand="TestBrand",
        images=["https://example.com/img1.jpg"],
        description="A high-quality test product",
        category="Electronics > Gadgets",
        availability="In Stock",
        source_marketplace=SourceMarketplace.AMAZON,
        source_url="https://www.amazon.com/dp/B09TEST123",
        source_product_id="B09TEST123",
    ))
    return scraper


@pytest.fixture
def mock_compliance():
    compliance = MagicMock()
    compliance.check_product = MagicMock(return_value=ComplianceResult(
        is_compliant=True,
        brand="TestBrand",
        risk_level=RiskLevel.CLEAR,
        violations=[],
    ))
    return compliance


@pytest.fixture
def mock_profit_engine():
    engine = MagicMock()
    engine.suggest_price = MagicMock(return_value=39.99)
    engine.calculate_profit = MagicMock(return_value=ProfitBreakdown(
        cost=25.99,
        sell_price=39.99,
        ebay_fee=5.30,
        payment_fee=1.46,
        shipping_cost=5.00,
        profit=2.24,
        margin_pct=5.6,
    ))
    return engine


@pytest.fixture
def mock_converter():
    converter = MagicMock()
    converter.convert = MagicMock(return_value=ListingDraft(
        title="Test Product Premium Quality Widget",
        description_html="<p>A high-quality test product</p>",
        price=25.99,
        images=["https://example.com/img1.jpg"],
        sku="KI-B09TEST123",
        target_marketplace=TargetMarketplace.EBAY,
        source_product_id="B09TEST123",
        source_marketplace=SourceMarketplace.AMAZON,
    ))
    return converter


@pytest.fixture
def mock_lister():
    lister = AsyncMock()
    lister.create_listing = AsyncMock(return_value=ListingResult(
        marketplace_item_id="123456789",
        status=ListingStatus.ACTIVE,
        url="https://www.ebay.com/itm/123456789",
    ))
    return lister


@pytest.fixture
def service(
    mock_proxy_manager,
    mock_browser_manager,
    mock_compliance,
    mock_profit_engine,
    mock_converter,
    mock_lister,
    mock_scraper,
):
    svc = ConversionService(
        proxy_manager=mock_proxy_manager,
        browser_manager=mock_browser_manager,
        compliance_service=mock_compliance,
        profit_engine=mock_profit_engine,
        ebay_converter=mock_converter,
        ebay_lister=mock_lister,
    )
    return svc


# ─── Marketplace Detection Tests ──────────────────────────


class TestMarketplaceDetection:
    """Tests for URL marketplace detection."""

    def test_detect_amazon(self):
        assert _detect_marketplace("https://www.amazon.com/dp/B09C5RG6KV") == "amazon"

    def test_detect_amazon_short_url(self):
        assert _detect_marketplace("https://amzn.to/3abc") == "amazon"

    def test_detect_walmart(self):
        assert _detect_marketplace("https://www.walmart.com/ip/product/123456") == "walmart"

    def test_unsupported_marketplace(self):
        with pytest.raises(ConversionError):
            _detect_marketplace("https://www.ebay.com/itm/123456")

    def test_unsupported_random_url(self):
        with pytest.raises(ConversionError):
            _detect_marketplace("https://www.example.com/product")


# ─── Single Conversion Tests ─────────────────────────────


class TestConvertUrl:
    """Tests for single URL conversion."""

    @pytest.mark.asyncio
    async def test_successful_conversion_draft_mode(
        self, service, mock_scraper, mock_compliance, mock_converter, mock_profit_engine
    ):
        """Should complete full pipeline in draft mode (no publish)."""
        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            result = await service.convert_url(
                url="https://www.amazon.com/dp/B09TEST123",
                user_id="user-1",
                publish=False,
            )

        assert result.status == ConversionStatus.COMPLETED
        assert result.step == ConversionStep.COMPLETE
        assert result.product is not None
        assert result.compliance is not None
        assert result.draft is not None
        assert result.profit is not None
        assert result.listing is not None
        assert result.listing.status == ListingStatus.DRAFT
        assert result.error == ""

    @pytest.mark.asyncio
    async def test_successful_conversion_publish_mode(
        self, service, mock_scraper, mock_lister
    ):
        """Should publish to eBay when publish=True."""
        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            result = await service.convert_url(
                url="https://www.amazon.com/dp/B09TEST123",
                user_id="user-1",
                publish=True,
            )

        assert result.status == ConversionStatus.COMPLETED
        assert result.listing.status == ListingStatus.ACTIVE
        assert result.listing.marketplace_item_id == "123456789"
        mock_lister.create_listing.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_sell_price(
        self, service, mock_scraper, mock_profit_engine
    ):
        """Should use custom sell_price when provided."""
        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            result = await service.convert_url(
                url="https://www.amazon.com/dp/B09TEST123",
                user_id="user-1",
                sell_price=49.99,
            )

        assert result.status == ConversionStatus.COMPLETED
        # Profit engine should have been called with the custom price
        mock_profit_engine.calculate_profit.assert_called_once()
        call_kwargs = mock_profit_engine.calculate_profit.call_args
        assert call_kwargs.kwargs.get("sell_price") == 49.99 or call_kwargs[1].get("sell_price") == 49.99

    @pytest.mark.asyncio
    async def test_scraping_failure(self, service, mock_scraper):
        """Should handle scraping errors gracefully."""
        mock_scraper.scrape.side_effect = ScrapingError("Bot detection triggered")

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            result = await service.convert_url(
                url="https://www.amazon.com/dp/B09TEST123",
                user_id="user-1",
            )

        assert result.status == ConversionStatus.FAILED
        assert result.step == ConversionStep.FAILED
        assert "Scraping failed" in result.error

    @pytest.mark.asyncio
    async def test_compliance_blocked(self, service, mock_scraper, mock_compliance):
        """Should fail when product is blocked by compliance."""
        mock_compliance.check_product.return_value = ComplianceResult(
            is_compliant=False,
            brand="Nike",
            risk_level=RiskLevel.BLOCKED,
            violations=["Brand 'Nike' is on the eBay VeRO protected brands list"],
        )

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            result = await service.convert_url(
                url="https://www.amazon.com/dp/B09TEST123",
                user_id="user-1",
            )

        assert result.status == ConversionStatus.FAILED
        assert "Compliance violation" in result.error

    @pytest.mark.asyncio
    async def test_compliance_warning_continues(self, service, mock_scraper, mock_compliance):
        """Should continue with warnings but not block."""
        mock_compliance.check_product.return_value = ComplianceResult(
            is_compliant=True,
            brand="SimilarBrand",
            risk_level=RiskLevel.WARNING,
            violations=["Brand closely matches VeRO brand"],
        )

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            result = await service.convert_url(
                url="https://www.amazon.com/dp/B09TEST123",
                user_id="user-1",
            )

        assert result.status == ConversionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_unsupported_url(self, service):
        """Should fail for unsupported marketplace URLs."""
        result = await service.convert_url(
            url="https://www.etsy.com/listing/123",
            user_id="user-1",
        )

        assert result.status == ConversionStatus.FAILED
        assert "Unsupported" in result.error


# ─── Bulk Conversion Tests ────────────────────────────────


class TestBulkConversion:
    """Tests for bulk URL conversion."""

    @pytest.mark.asyncio
    async def test_bulk_all_successful(self, service, mock_scraper):
        """Should process all URLs and track progress."""
        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
            "https://www.amazon.com/dp/B09TEST003",
        ]

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            progress = await service.convert_bulk(urls=urls, user_id="user-1")

        assert progress.total == 3
        assert progress.completed == 3
        assert progress.failed == 0
        assert progress.is_done
        assert progress.progress_pct == 100.0
        assert len(progress.results) == 3

    @pytest.mark.asyncio
    async def test_bulk_mixed_results(self, service, mock_scraper):
        """Should handle mix of successes and failures."""
        original_product = ScrapedProduct(
            title="Test Product - Premium Quality Widget",
            price=25.99,
            brand="TestBrand",
            images=["https://example.com/img1.jpg"],
            description="A high-quality test product",
            category="Electronics > Gadgets",
            availability="In Stock",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/B09TEST123",
            source_product_id="B09TEST123",
        )
        call_count = 0

        async def side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ScrapingError("Scraping failed for second URL")
            return original_product

        mock_scraper.scrape = AsyncMock(side_effect=side_effect)

        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
            "https://www.amazon.com/dp/B09TEST003",
        ]

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            progress = await service.convert_bulk(urls=urls, user_id="user-1")

        assert progress.total == 3
        assert progress.completed == 2
        assert progress.failed == 1

    @pytest.mark.asyncio
    async def test_bulk_empty_list(self, service):
        """Should handle empty URL list."""
        progress = await service.convert_bulk(urls=[], user_id="user-1")

        assert progress.total == 0
        assert progress.completed == 0
        assert progress.is_done


# ─── ConversionResult Tests ──────────────────────────────


class TestConversionResult:
    """Tests for ConversionResult serialization."""

    def test_to_dict_successful(self):
        """Should serialize a successful result."""
        result = ConversionResult(
            url="https://amazon.com/dp/TEST",
            status=ConversionStatus.COMPLETED,
            step=ConversionStep.COMPLETE,
            product=ScrapedProduct(
                title="Test",
                price=10.0,
                source_marketplace=SourceMarketplace.AMAZON,
                source_url="https://amazon.com/dp/TEST",
                source_product_id="TEST",
            ),
            compliance=ComplianceResult(
                is_compliant=True,
                risk_level=RiskLevel.CLEAR,
            ),
            draft=ListingDraft(
                title="Test",
                price=15.0,
                sku="KI-TEST",
            ),
            profit=ProfitBreakdown(
                cost=10.0,
                sell_price=15.0,
                profit=1.0,
                margin_pct=6.7,
            ),
            listing=ListingResult(
                status=ListingStatus.DRAFT,
            ),
        )

        d = result.to_dict()
        assert d["status"] == "completed"
        assert d["product"]["title"] == "Test"
        assert d["compliance"]["is_compliant"] is True
        assert d["draft"]["sku"] == "KI-TEST"
        assert d["profit"]["profit"] == 1.0
        assert d["error"] == ""

    def test_to_dict_failed(self):
        """Should serialize a failed result."""
        result = ConversionResult(
            url="https://amazon.com/dp/TEST",
            status=ConversionStatus.FAILED,
            error="Scraping failed: Bot detection",
        )

        d = result.to_dict()
        assert d["status"] == "failed"
        assert d["product"] is None
        assert "Bot detection" in d["error"]


# ─── BulkConversionProgress Tests ────────────────────────


class TestBulkConversionProgress:
    """Tests for progress tracking."""

    def test_progress_calculation(self):
        progress = BulkConversionProgress(total=10, completed=3, failed=2)
        assert progress.pending == 5
        assert progress.progress_pct == 50.0
        assert not progress.is_done

    def test_progress_empty(self):
        progress = BulkConversionProgress(total=0)
        assert progress.progress_pct == 0.0
        assert progress.is_done

    def test_progress_complete(self):
        progress = BulkConversionProgress(total=5, completed=4, failed=1)
        assert progress.is_done
        assert progress.progress_pct == 100.0

    def test_to_dict(self):
        progress = BulkConversionProgress(total=2, completed=1, failed=1)
        d = progress.to_dict()
        assert d["total"] == 2
        assert d["completed"] == 1
        assert d["failed"] == 1
        assert d["pending"] == 0
