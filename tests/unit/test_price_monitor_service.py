"""
Tests for PriceMonitorService.

Covers:
- check_price: price changed, unchanged, scraper error
- check_all_for_user: multiple products, no active listings
- PriceCheckResult serialization
"""

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.models import Product, Listing
from app.services.price_monitor_service import PriceMonitorService, PriceCheckResult


# ─── Fixtures ──────────────────────────────────────────────


def _make_product(
    price: float = 29.99,
    marketplace: str = "amazon",
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock Product with realistic attributes."""
    product = MagicMock(spec=Product)
    product.id = uuid.uuid4()
    product.user_id = user_id or uuid.uuid4()
    product.source_marketplace = marketplace
    product.source_url = f"https://www.{marketplace}.com/dp/B09TEST123"
    product.source_product_id = "B09TEST123"
    product.title = "Test Product"
    product.price = price
    product.brand = "TestBrand"
    return product


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_scraper():
    scraper = AsyncMock()
    return scraper


@pytest.fixture
def mock_factory(mock_scraper):
    factory = MagicMock()
    factory.create = MagicMock(return_value=mock_scraper)
    return factory


@pytest.fixture
def service(mock_session, mock_factory):
    return PriceMonitorService(
        session=mock_session,
        scraper_factory=mock_factory,
    )


# ─── PriceCheckResult Tests ───────────────────────────────


class TestPriceCheckResult:
    def test_to_dict(self):
        pid = uuid.uuid4()
        result = PriceCheckResult(
            product_id=pid,
            old_price=29.99,
            new_price=34.99,
            changed=True,
        )
        d = result.to_dict()
        assert d["product_id"] == str(pid)
        assert d["old_price"] == 29.99
        assert d["new_price"] == 34.99
        assert d["changed"] is True
        assert d["error"] is None

    def test_to_dict_with_error(self):
        pid = uuid.uuid4()
        result = PriceCheckResult(
            product_id=pid,
            old_price=29.99,
            error="Connection timeout",
        )
        d = result.to_dict()
        assert d["new_price"] is None
        assert d["changed"] is False
        assert d["error"] == "Connection timeout"


# ─── check_price Tests ────────────────────────────────────


class TestCheckPrice:
    @pytest.mark.asyncio
    async def test_price_changed(self, service, mock_scraper):
        """When source price differs, record history and update product."""
        product = _make_product(price=29.99)
        scraped = MagicMock()
        scraped.price = 34.99
        mock_scraper.scrape = AsyncMock(return_value=scraped)

        with patch.object(service, "_price_repo") as price_repo, \
             patch.object(service, "_product_repo") as product_repo:
            price_repo.record_price = AsyncMock()
            product_repo.update = AsyncMock()

            result = await service.check_price(product)

        assert result.changed is True
        assert result.old_price == 29.99
        assert result.new_price == 34.99
        assert result.error is None
        price_repo.record_price.assert_called_once_with(
            product_id=product.id,
            price=34.99,
        )
        product_repo.update.assert_called_once_with(product.id, price=34.99)

    @pytest.mark.asyncio
    async def test_price_unchanged(self, service, mock_scraper):
        """When source price is the same, record history but don't update product."""
        product = _make_product(price=29.99)
        scraped = MagicMock()
        scraped.price = 29.99
        mock_scraper.scrape = AsyncMock(return_value=scraped)

        with patch.object(service, "_price_repo") as price_repo, \
             patch.object(service, "_product_repo") as product_repo:
            price_repo.record_price = AsyncMock()
            product_repo.update = AsyncMock()

            result = await service.check_price(product)

        assert result.changed is False
        assert result.old_price == 29.99
        assert result.new_price == 29.99
        price_repo.record_price.assert_called_once()
        product_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_scraper_error(self, service, mock_scraper):
        """When scraper fails, return error result without recording."""
        product = _make_product(price=29.99)
        mock_scraper.scrape = AsyncMock(side_effect=Exception("Connection timeout"))

        with patch.object(service, "_price_repo") as price_repo:
            price_repo.record_price = AsyncMock()

            result = await service.check_price(product)

        assert result.changed is False
        assert result.new_price is None
        assert result.error == "Connection timeout"
        price_repo.record_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_tiny_price_difference_not_considered_change(self, service, mock_scraper):
        """Price difference within floating-point tolerance is not a change."""
        product = _make_product(price=29.99)
        scraped = MagicMock()
        scraped.price = 29.9900001  # within 0.001 tolerance
        mock_scraper.scrape = AsyncMock(return_value=scraped)

        with patch.object(service, "_price_repo") as price_repo, \
             patch.object(service, "_product_repo") as product_repo:
            price_repo.record_price = AsyncMock()
            product_repo.update = AsyncMock()

            result = await service.check_price(product)

        assert result.changed is False
        product_repo.update.assert_not_called()


# ─── check_all_for_user Tests ─────────────────────────────


class TestCheckAllForUser:
    @pytest.mark.asyncio
    async def test_no_active_listings(self, service):
        """When user has no active listings, return empty list."""
        user_id = uuid.uuid4()

        with patch.object(service, "_listing_repo") as listing_repo:
            listing_repo.find_active_by_user = AsyncMock(return_value=[])

            results = await service.check_all_for_user(user_id)

        assert results == []

    @pytest.mark.asyncio
    async def test_checks_all_products(self, service, mock_scraper):
        """When user has active listings, check all products."""
        user_id = uuid.uuid4()
        products = [_make_product(user_id=user_id) for _ in range(3)]
        listings = [MagicMock(spec=Listing) for _ in range(2)]

        scraped = MagicMock()
        scraped.price = 29.99  # same price — no change
        mock_scraper.scrape = AsyncMock(return_value=scraped)

        with patch.object(service, "_listing_repo") as listing_repo, \
             patch.object(service, "_product_repo") as product_repo, \
             patch.object(service, "_price_repo") as price_repo:
            listing_repo.find_active_by_user = AsyncMock(return_value=listings)
            product_repo.find_by_user = AsyncMock(return_value=products)
            price_repo.record_price = AsyncMock()

            results = await service.check_all_for_user(user_id)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_mixed_results(self, service, mock_scraper):
        """Handles a mix of changed and unchanged prices."""
        user_id = uuid.uuid4()
        p1 = _make_product(price=29.99, user_id=user_id)
        p2 = _make_product(price=19.99, user_id=user_id)

        listings = [MagicMock(spec=Listing)]

        call_count = 0

        async def mock_scrape(url):
            nonlocal call_count
            call_count += 1
            s = MagicMock()
            s.price = 34.99 if call_count == 1 else 19.99
            return s

        mock_scraper.scrape = mock_scrape

        with patch.object(service, "_listing_repo") as listing_repo, \
             patch.object(service, "_product_repo") as product_repo, \
             patch.object(service, "_price_repo") as price_repo:
            listing_repo.find_active_by_user = AsyncMock(return_value=listings)
            product_repo.find_by_user = AsyncMock(return_value=[p1, p2])
            product_repo.update = AsyncMock()
            price_repo.record_price = AsyncMock()

            results = await service.check_all_for_user(user_id)

        assert len(results) == 2
        assert results[0].changed is True
        assert results[1].changed is False
