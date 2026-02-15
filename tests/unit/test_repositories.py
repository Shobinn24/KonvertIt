"""
Comprehensive tests for all database repositories and ORM mappers.

Uses an in-memory async SQLite database so no external services are needed.
Tests cover:
- ConversionRepository — CRUD, status queries, update_status, link_listing, count_by_status
- EbayCredentialRepository — find_by_user, find_active, find_by_store_name, update_tokens
- PriceHistoryRepository — record_price, get_history, get_latest_price, get_price_range, get_price_stats
- ProductRepository — find_by_source_id, find_by_user, find_by_brand
- ListingRepository — find_by_user, find_by_ebay_id, find_active_by_user, count_by_status
- Mappers — product_from_scraped, scraped_from_product, listing_from_draft, conversion_from_result
- Repository __init__ exports
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.models import (
    ListingDraft,
    ListingResult,
    ListingStatus,
    ScrapedProduct,
    SourceMarketplace,
    TargetMarketplace,
)
from app.db.mappers import (
    conversion_from_result,
    listing_from_draft,
    product_from_scraped,
    scraped_from_product,
)
from app.db.models import (
    Base,
    Conversion,
    EbayCredential,
    Listing,
    PriceHistory,
    Product,
    User,
)
from app.db.repositories.conversion_repo import ConversionRepository
from app.db.repositories.ebay_credential_repo import EbayCredentialRepository
from app.db.repositories.listing_repo import ListingRepository
from app.db.repositories.price_history_repo import PriceHistoryRepository
from app.db.repositories.product_repo import ProductRepository


# ─── Fixtures ────────────────────────────────────────────────


@pytest.fixture
async def engine():
    """Create an in-memory async SQLite engine for testing."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # SQLite needs PRAGMA foreign_keys for FK enforcement
    @event.listens_for(eng.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def session(engine):
    """Create a fresh async session for each test."""
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as sess:
        yield sess


@pytest.fixture
async def user(session: AsyncSession) -> User:
    """Create a test user."""
    u = User(
        email="test@example.com",
        password_hash="fakehash123",
        tier="pro",
    )
    session.add(u)
    await session.flush()
    return u


@pytest.fixture
async def user2(session: AsyncSession) -> User:
    """Create a second test user for tenant isolation tests."""
    u = User(
        email="other@example.com",
        password_hash="fakehash456",
        tier="free",
    )
    session.add(u)
    await session.flush()
    return u


@pytest.fixture
async def product(session: AsyncSession, user: User) -> Product:
    """Create a test product."""
    p = Product(
        user_id=user.id,
        source_marketplace="amazon",
        source_url="https://www.amazon.com/dp/B09C5RG6KV",
        source_product_id="B09C5RG6KV",
        title="Anker USB C Charger 40W",
        price=25.99,
        brand="Anker",
        category="Electronics",
        image_urls=["https://example.com/img1.jpg"],
        raw_data={"asin": "B09C5RG6KV"},
    )
    session.add(p)
    await session.flush()
    return p


@pytest.fixture
async def listing(session: AsyncSession, user: User) -> Listing:
    """Create a test listing."""
    lst = Listing(
        user_id=user.id,
        title="Anker USB C Charger 40W Compact",
        description_html="<p>Test</p>",
        price=39.99,
        status="draft",
    )
    session.add(lst)
    await session.flush()
    return lst


@pytest.fixture
async def conversion(
    session: AsyncSession, user: User, product: Product
) -> Conversion:
    """Create a test conversion."""
    c = Conversion(
        user_id=user.id,
        product_id=product.id,
        status="completed",
    )
    session.add(c)
    await session.flush()
    return c


# ─── TestConversionRepository ────────────────────────────────


class TestConversionRepository:
    """Tests for ConversionRepository CRUD and queries."""

    async def test_create_conversion(self, session, user, product):
        repo = ConversionRepository(session)
        conv = await repo.create(
            user_id=user.id,
            product_id=product.id,
            status="pending",
        )
        assert conv.id is not None
        assert conv.status == "pending"

    async def test_get_by_id(self, session, conversion):
        repo = ConversionRepository(session)
        found = await repo.get_by_id(conversion.id)
        assert found is not None
        assert found.id == conversion.id

    async def test_get_by_id_not_found(self, session):
        repo = ConversionRepository(session)
        found = await repo.get_by_id(uuid.uuid4())
        assert found is None

    async def test_find_by_user(self, session, user, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="completed")
        await repo.create(user_id=user.id, product_id=product.id, status="failed")

        results = await repo.find_by_user(user.id)
        assert len(results) == 2

    async def test_find_by_user_with_status_filter(self, session, user, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="completed")
        await repo.create(user_id=user.id, product_id=product.id, status="failed")
        await repo.create(user_id=user.id, product_id=product.id, status="completed")

        results = await repo.find_by_user(user.id, status="completed")
        assert len(results) == 2
        assert all(r.status == "completed" for r in results)

    async def test_find_by_user_tenant_isolation(
        self, session, user, user2, product
    ):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="completed")

        # User2 should see nothing
        results = await repo.find_by_user(user2.id)
        assert len(results) == 0

    async def test_find_by_product(self, session, user, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="completed")
        await repo.create(user_id=user.id, product_id=product.id, status="failed")

        results = await repo.find_by_product(product.id)
        assert len(results) == 2

    async def test_find_pending(self, session, user, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="pending")
        await repo.create(user_id=user.id, product_id=product.id, status="processing")
        await repo.create(user_id=user.id, product_id=product.id, status="completed")

        results = await repo.find_pending()
        assert len(results) == 2
        statuses = {r.status for r in results}
        assert statuses == {"pending", "processing"}

    async def test_find_by_status_range(self, session, user, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="pending")
        await repo.create(user_id=user.id, product_id=product.id, status="completed")
        await repo.create(user_id=user.id, product_id=product.id, status="failed")

        results = await repo.find_by_status_range(
            user.id, ["completed", "failed"]
        )
        assert len(results) == 2

    async def test_update_status(self, session, user, product):
        repo = ConversionRepository(session)
        conv = await repo.create(
            user_id=user.id, product_id=product.id, status="pending"
        )

        updated = await repo.update_status(conv.id, "completed")
        assert updated is not None
        assert updated.status == "completed"
        assert updated.converted_at is not None

    async def test_update_status_with_error(self, session, user, product):
        repo = ConversionRepository(session)
        conv = await repo.create(
            user_id=user.id, product_id=product.id, status="processing"
        )

        updated = await repo.update_status(
            conv.id, "failed", error_message="VeRO violation"
        )
        assert updated.status == "failed"
        assert updated.error_message == "VeRO violation"
        assert updated.converted_at is None  # Not completed

    async def test_update_status_not_found(self, session):
        repo = ConversionRepository(session)
        result = await repo.update_status(uuid.uuid4(), "completed")
        assert result is None

    async def test_link_listing(self, session, user, product, listing):
        repo = ConversionRepository(session)
        conv = await repo.create(
            user_id=user.id, product_id=product.id, status="completed"
        )

        updated = await repo.link_listing(conv.id, listing.id)
        assert updated is not None
        assert updated.listing_id == listing.id

    async def test_link_listing_not_found(self, session):
        repo = ConversionRepository(session)
        result = await repo.link_listing(uuid.uuid4(), uuid.uuid4())
        assert result is None

    async def test_count_by_status(self, session, user, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="completed")
        await repo.create(user_id=user.id, product_id=product.id, status="completed")
        await repo.create(user_id=user.id, product_id=product.id, status="failed")

        counts = await repo.count_by_status(user.id)
        assert counts.get("completed") == 2
        assert counts.get("failed") == 1

    async def test_delete_conversion(self, session, user, product):
        repo = ConversionRepository(session)
        conv = await repo.create(
            user_id=user.id, product_id=product.id, status="pending"
        )

        deleted = await repo.delete(conv.id)
        assert deleted is True
        found = await repo.get_by_id(conv.id)
        assert found is None

    async def test_pagination(self, session, user, product):
        repo = ConversionRepository(session)
        for _ in range(5):
            await repo.create(
                user_id=user.id, product_id=product.id, status="completed"
            )

        page1 = await repo.find_by_user(user.id, limit=2, offset=0)
        page2 = await repo.find_by_user(user.id, limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2


# ─── TestEbayCredentialRepository ────────────────────────────


class TestEbayCredentialRepository:
    """Tests for EbayCredentialRepository token management."""

    async def test_create_credential(self, session, user):
        repo = EbayCredentialRepository(session)
        cred = await repo.create(
            user_id=user.id,
            store_name="TestStore",
            access_token="enc_access_token",
            refresh_token="enc_refresh_token",
            sandbox_mode=True,
        )
        assert cred.id is not None
        assert cred.store_name == "TestStore"

    async def test_find_by_user(self, session, user):
        repo = EbayCredentialRepository(session)
        await repo.create(
            user_id=user.id,
            store_name="Store1",
            access_token="tok1",
            refresh_token="ref1",
        )
        await repo.create(
            user_id=user.id,
            store_name="Store2",
            access_token="tok2",
            refresh_token="ref2",
        )

        results = await repo.find_by_user(user.id)
        assert len(results) == 2

    async def test_find_active_excludes_expired(self, session, user):
        repo = EbayCredentialRepository(session)
        past = datetime.now(UTC) - timedelta(hours=1)
        future = datetime.now(UTC) + timedelta(hours=1)

        await repo.create(
            user_id=user.id,
            store_name="Expired",
            access_token="tok1",
            refresh_token="ref1",
            token_expiry=past,
        )
        await repo.create(
            user_id=user.id,
            store_name="Active",
            access_token="tok2",
            refresh_token="ref2",
            token_expiry=future,
        )

        active = await repo.find_active(user.id)
        assert len(active) == 1
        assert active[0].store_name == "Active"

    async def test_find_active_includes_null_expiry(self, session, user):
        repo = EbayCredentialRepository(session)
        await repo.create(
            user_id=user.id,
            store_name="NoExpiry",
            access_token="tok",
            refresh_token="ref",
            token_expiry=None,
        )

        active = await repo.find_active(user.id)
        assert len(active) == 1

    async def test_find_active_sandbox_filter(self, session, user):
        repo = EbayCredentialRepository(session)
        await repo.create(
            user_id=user.id,
            store_name="Sandbox",
            access_token="tok1",
            refresh_token="ref1",
            sandbox_mode=True,
        )
        await repo.create(
            user_id=user.id,
            store_name="Production",
            access_token="tok2",
            refresh_token="ref2",
            sandbox_mode=False,
        )

        sandbox = await repo.find_active(user.id, sandbox=True)
        assert len(sandbox) == 1
        assert sandbox[0].store_name == "Sandbox"

        prod = await repo.find_active(user.id, sandbox=False)
        assert len(prod) == 1
        assert prod[0].store_name == "Production"

    async def test_find_by_store_name(self, session, user):
        repo = EbayCredentialRepository(session)
        await repo.create(
            user_id=user.id,
            store_name="MyStore",
            access_token="tok",
            refresh_token="ref",
        )

        found = await repo.find_by_store_name(user.id, "MyStore")
        assert found is not None
        assert found.store_name == "MyStore"

    async def test_find_by_store_name_not_found(self, session, user):
        repo = EbayCredentialRepository(session)
        found = await repo.find_by_store_name(user.id, "NonExistent")
        assert found is None

    async def test_update_tokens(self, session, user):
        repo = EbayCredentialRepository(session)
        cred = await repo.create(
            user_id=user.id,
            store_name="Store",
            access_token="old_access",
            refresh_token="old_refresh",
        )
        new_expiry = datetime.now(UTC) + timedelta(hours=2)

        updated = await repo.update_tokens(
            cred.id,
            access_token="new_access",
            refresh_token="new_refresh",
            token_expiry=new_expiry,
        )
        assert updated is not None
        assert updated.access_token == "new_access"
        assert updated.refresh_token == "new_refresh"
        assert updated.token_expiry == new_expiry

    async def test_update_tokens_not_found(self, session):
        repo = EbayCredentialRepository(session)
        result = await repo.update_tokens(
            uuid.uuid4(), "tok", "ref"
        )
        assert result is None


# ─── TestPriceHistoryRepository ──────────────────────────────


class TestPriceHistoryRepository:
    """Tests for PriceHistoryRepository append-only price tracking."""

    async def test_record_price(self, session, product):
        repo = PriceHistoryRepository(session)
        record = await repo.record_price(product.id, 25.99)
        assert record.id is not None
        assert record.price == 25.99
        assert record.currency == "USD"

    async def test_record_price_custom_currency(self, session, product):
        repo = PriceHistoryRepository(session)
        record = await repo.record_price(product.id, 19.99, currency="GBP")
        assert record.currency == "GBP"

    async def test_get_history(self, session, product):
        repo = PriceHistoryRepository(session)
        await repo.record_price(product.id, 25.99)
        await repo.record_price(product.id, 24.99)
        await repo.record_price(product.id, 23.99)

        history = await repo.get_history(product.id)
        assert len(history) == 3

    async def test_get_history_pagination(self, session, product):
        repo = PriceHistoryRepository(session)
        for i in range(5):
            await repo.record_price(product.id, 20.0 + i)

        page = await repo.get_history(product.id, limit=2, offset=0)
        assert len(page) == 2

    async def test_get_latest_price(self, session, product):
        repo = PriceHistoryRepository(session)
        await repo.record_price(product.id, 25.99)
        await repo.record_price(product.id, 29.99)

        latest = await repo.get_latest_price(product.id)
        assert latest is not None
        assert latest.price == 29.99

    async def test_get_latest_price_no_history(self, session, product):
        repo = PriceHistoryRepository(session)
        latest = await repo.get_latest_price(product.id)
        assert latest is None

    async def test_get_price_range(self, session, product):
        repo = PriceHistoryRepository(session)
        now = datetime.now(UTC)

        # Create records with explicit timestamps
        r1 = PriceHistory(
            product_id=product.id,
            price=20.0,
            recorded_at=now - timedelta(days=3),
        )
        r2 = PriceHistory(
            product_id=product.id,
            price=22.0,
            recorded_at=now - timedelta(days=1),
        )
        r3 = PriceHistory(
            product_id=product.id,
            price=25.0,
            recorded_at=now,
        )
        session.add_all([r1, r2, r3])
        await session.flush()

        # Query last 2 days
        results = await repo.get_price_range(
            product.id,
            start=now - timedelta(days=2),
            end=now,
        )
        assert len(results) == 2
        assert results[0].price == 22.0
        assert results[1].price == 25.0

    async def test_get_price_stats(self, session, product):
        repo = PriceHistoryRepository(session)
        await repo.record_price(product.id, 10.0)
        await repo.record_price(product.id, 20.0)
        await repo.record_price(product.id, 30.0)

        stats = await repo.get_price_stats(product.id)
        assert stats["min_price"] == 10.0
        assert stats["max_price"] == 30.0
        assert stats["avg_price"] == 20.0
        assert stats["count"] == 3

    async def test_get_price_stats_empty(self, session, product):
        repo = PriceHistoryRepository(session)
        stats = await repo.get_price_stats(product.id)
        assert stats["min_price"] is None
        assert stats["max_price"] is None
        assert stats["avg_price"] is None
        assert stats["count"] == 0

    async def test_count_for_product(self, session, product):
        repo = PriceHistoryRepository(session)
        await repo.record_price(product.id, 25.0)
        await repo.record_price(product.id, 26.0)

        count = await repo.count_for_product(product.id)
        assert count == 2


# ─── TestProductRepository ───────────────────────────────────


class TestProductRepository:
    """Tests for ProductRepository existing methods + new tests."""

    async def test_find_by_source_id(self, session, user, product):
        repo = ProductRepository(session)
        found = await repo.find_by_source_id(
            user.id, "amazon", "B09C5RG6KV"
        )
        assert found is not None
        assert found.title == "Anker USB C Charger 40W"

    async def test_find_by_source_id_not_found(self, session, user):
        repo = ProductRepository(session)
        found = await repo.find_by_source_id(
            user.id, "amazon", "NONEXISTENT"
        )
        assert found is None

    async def test_find_by_user(self, session, user, product):
        repo = ProductRepository(session)
        results = await repo.find_by_user(user.id)
        assert len(results) == 1
        assert results[0].id == product.id

    async def test_find_by_user_marketplace_filter(self, session, user):
        repo = ProductRepository(session)
        p1 = Product(
            user_id=user.id,
            source_marketplace="amazon",
            source_url="https://amazon.com/dp/A001",
            source_product_id="A001",
            title="Amazon Product",
            price=10.0,
        )
        p2 = Product(
            user_id=user.id,
            source_marketplace="walmart",
            source_url="https://walmart.com/ip/W001",
            source_product_id="W001",
            title="Walmart Product",
            price=15.0,
        )
        session.add_all([p1, p2])
        await session.flush()

        amazon_results = await repo.find_by_user(user.id, marketplace="amazon")
        assert len(amazon_results) == 1
        assert amazon_results[0].source_marketplace == "amazon"

    async def test_find_by_brand(self, session, user, product):
        repo = ProductRepository(session)
        results = await repo.find_by_brand(user.id, "Anker")
        assert len(results) == 1

    async def test_tenant_isolation(self, session, user, user2, product):
        repo = ProductRepository(session)
        results = await repo.find_by_user(user2.id)
        assert len(results) == 0


# ─── TestListingRepository ───────────────────────────────────


class TestListingRepository:
    """Tests for ListingRepository existing methods + new tests."""

    async def test_find_by_user(self, session, user, listing):
        repo = ListingRepository(session)
        results = await repo.find_by_user(user.id)
        assert len(results) == 1

    async def test_find_by_user_status_filter(self, session, user):
        repo = ListingRepository(session)
        l1 = Listing(
            user_id=user.id,
            title="Draft Listing",
            price=20.0,
            status="draft",
        )
        l2 = Listing(
            user_id=user.id,
            title="Active Listing",
            price=30.0,
            status="active",
        )
        session.add_all([l1, l2])
        await session.flush()

        active = await repo.find_by_user(user.id, status="active")
        assert len(active) == 1
        assert active[0].status == "active"

    async def test_find_by_ebay_id(self, session, user):
        repo = ListingRepository(session)
        lst = Listing(
            user_id=user.id,
            title="Test",
            price=10.0,
            ebay_item_id="EBAY-12345",
            status="active",
        )
        session.add(lst)
        await session.flush()

        found = await repo.find_by_ebay_id("EBAY-12345")
        assert found is not None
        assert found.ebay_item_id == "EBAY-12345"

    async def test_find_by_ebay_id_not_found(self, session):
        repo = ListingRepository(session)
        found = await repo.find_by_ebay_id("NONEXISTENT")
        assert found is None

    async def test_find_active_by_user(self, session, user):
        repo = ListingRepository(session)
        session.add(
            Listing(
                user_id=user.id, title="Active", price=10.0, status="active"
            )
        )
        session.add(
            Listing(
                user_id=user.id, title="Draft", price=10.0, status="draft"
            )
        )
        await session.flush()

        active = await repo.find_active_by_user(user.id)
        assert len(active) == 1
        assert active[0].status == "active"

    async def test_count_by_status(self, session, user):
        repo = ListingRepository(session)
        session.add(
            Listing(
                user_id=user.id, title="A", price=10.0, status="active"
            )
        )
        session.add(
            Listing(
                user_id=user.id, title="B", price=10.0, status="active"
            )
        )
        session.add(
            Listing(
                user_id=user.id, title="C", price=10.0, status="draft"
            )
        )
        await session.flush()

        counts = await repo.count_by_status(user.id)
        assert counts.get("active") == 2
        assert counts.get("draft") == 1


# ─── TestMappers ─────────────────────────────────────────────


class TestMappers:
    """Tests for Pydantic ↔ ORM mapping helpers."""

    def _make_scraped(self) -> ScrapedProduct:
        return ScrapedProduct(
            title="Test Product Title",
            price=29.99,
            currency="USD",
            brand="TestBrand",
            images=["https://example.com/img1.jpg", "https://example.com/img2.jpg"],
            description="A great product.",
            category="Electronics > Gadgets",
            availability="In Stock",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/T000001",
            source_product_id="T000001",
            raw_data={"asin": "T000001"},
        )

    def _make_draft(self) -> ListingDraft:
        return ListingDraft(
            title="Optimized eBay Title",
            description_html="<p>Great product</p>",
            price=39.99,
            images=["https://example.com/img1.jpg"],
            condition="New",
            sku="KI-T000001",
            target_marketplace=TargetMarketplace.EBAY,
            source_product_id="T000001",
            source_marketplace=SourceMarketplace.AMAZON,
        )

    # ── product_from_scraped ──

    def test_product_from_scraped_maps_fields(self):
        scraped = self._make_scraped()
        user_id = uuid.uuid4()
        product = product_from_scraped(scraped, user_id)

        assert product.user_id == user_id
        assert product.source_marketplace == "amazon"
        assert product.source_product_id == "T000001"
        assert product.title == "Test Product Title"
        assert product.price == 29.99
        assert product.brand == "TestBrand"
        assert product.category == "Electronics > Gadgets"
        assert product.image_urls == scraped.images
        assert product.raw_data == {"asin": "T000001"}

    def test_product_from_scraped_preserves_url(self):
        scraped = self._make_scraped()
        product = product_from_scraped(scraped, uuid.uuid4())
        assert product.source_url == "https://www.amazon.com/dp/T000001"

    def test_product_from_scraped_preserves_scraped_at(self):
        scraped = self._make_scraped()
        product = product_from_scraped(scraped, uuid.uuid4())
        assert product.scraped_at == scraped.scraped_at

    # ── scraped_from_product ──

    def test_scraped_from_product_roundtrip(self):
        original = self._make_scraped()
        user_id = uuid.uuid4()
        product_orm = product_from_scraped(original, user_id)
        roundtrip = scraped_from_product(product_orm)

        assert roundtrip.title == original.title
        assert roundtrip.price == original.price
        assert roundtrip.brand == original.brand
        assert roundtrip.images == original.images
        assert roundtrip.source_marketplace == original.source_marketplace
        assert roundtrip.source_product_id == original.source_product_id
        assert roundtrip.raw_data == original.raw_data

    def test_scraped_from_product_handles_empty_images(self):
        product = Product(
            user_id=uuid.uuid4(),
            source_marketplace="amazon",
            source_url="https://example.com",
            source_product_id="X001",
            title="Test",
            price=10.0,
            image_urls=None,  # Could be None in DB
        )
        scraped = scraped_from_product(product)
        assert scraped.images == []

    def test_scraped_from_product_handles_empty_raw_data(self):
        product = Product(
            user_id=uuid.uuid4(),
            source_marketplace="walmart",
            source_url="https://example.com",
            source_product_id="W001",
            title="Test",
            price=10.0,
            raw_data=None,
        )
        scraped = scraped_from_product(product)
        assert scraped.raw_data == {}

    # ── listing_from_draft ──

    def test_listing_from_draft_basic(self):
        draft = self._make_draft()
        user_id = uuid.uuid4()
        listing = listing_from_draft(draft, user_id)

        assert listing.user_id == user_id
        assert listing.title == "Optimized eBay Title"
        assert listing.description_html == "<p>Great product</p>"
        assert listing.price == 39.99
        assert listing.status == "draft"
        assert listing.ebay_item_id is None

    def test_listing_from_draft_with_result(self):
        draft = self._make_draft()
        result = ListingResult(
            marketplace_item_id="EBAY-99999",
            status=ListingStatus.ACTIVE,
            url="https://ebay.com/itm/99999",
        )
        listing = listing_from_draft(draft, uuid.uuid4(), listing_result=result)

        assert listing.ebay_item_id == "EBAY-99999"
        assert listing.status == "active"
        assert listing.listed_at is not None

    def test_listing_from_draft_with_draft_result(self):
        draft = self._make_draft()
        result = ListingResult(status=ListingStatus.DRAFT)
        listing = listing_from_draft(draft, uuid.uuid4(), listing_result=result)

        assert listing.status == "draft"
        assert listing.listed_at is None

    # ── conversion_from_result ──

    def test_conversion_from_result_completed(self):
        user_id = uuid.uuid4()
        product_id = uuid.uuid4()
        listing_id = uuid.uuid4()

        conv = conversion_from_result(
            user_id=user_id,
            product_id=product_id,
            status="completed",
            listing_id=listing_id,
        )
        assert conv.user_id == user_id
        assert conv.product_id == product_id
        assert conv.listing_id == listing_id
        assert conv.status == "completed"
        assert conv.converted_at is not None

    def test_conversion_from_result_failed(self):
        conv = conversion_from_result(
            user_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            status="failed",
            error_message="VeRO violation: Nike is blocked",
        )
        assert conv.status == "failed"
        assert conv.error_message == "VeRO violation: Nike is blocked"
        assert conv.converted_at is None

    def test_conversion_from_result_pending(self):
        conv = conversion_from_result(
            user_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            status="pending",
        )
        assert conv.status == "pending"
        assert conv.listing_id is None
        assert conv.error_message is None


# ─── TestRepositoryExports ───────────────────────────────────


class TestRepositoryExports:
    """Tests that __init__.py exports are correct."""

    def test_can_import_all_repositories(self):
        from app.db.repositories import (
            BaseRepository,
            ConversionRepository,
            EbayCredentialRepository,
            ListingRepository,
            PriceHistoryRepository,
            ProductRepository,
            UserRepository,
        )
        assert BaseRepository is not None
        assert ConversionRepository is not None
        assert EbayCredentialRepository is not None
        assert ListingRepository is not None
        assert PriceHistoryRepository is not None
        assert ProductRepository is not None
        assert UserRepository is not None

    def test_all_in_dunder_all(self):
        import app.db.repositories as repo_module

        assert "ConversionRepository" in repo_module.__all__
        assert "EbayCredentialRepository" in repo_module.__all__
        assert "PriceHistoryRepository" in repo_module.__all__
        assert "ProductRepository" in repo_module.__all__
        assert "ListingRepository" in repo_module.__all__
        assert "UserRepository" in repo_module.__all__
        assert "BaseRepository" in repo_module.__all__


# ─── TestBaseRepository ──────────────────────────────────────


class TestBaseRepository:
    """Tests for BaseRepository CRUD via a concrete repo."""

    async def test_count(self, session, user, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="pending")
        await repo.create(user_id=user.id, product_id=product.id, status="completed")

        total = await repo.count()
        assert total == 2

    async def test_count_with_user_filter(self, session, user, user2, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="pending")

        count_user1 = await repo.count(user_id=user.id)
        count_user2 = await repo.count(user_id=user2.id)
        assert count_user1 == 1
        assert count_user2 == 0

    async def test_get_all(self, session, user, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="pending")
        await repo.create(user_id=user.id, product_id=product.id, status="completed")

        all_records = await repo.get_all()
        assert len(all_records) == 2

    async def test_get_all_with_user_filter(self, session, user, user2, product):
        repo = ConversionRepository(session)
        await repo.create(user_id=user.id, product_id=product.id, status="pending")

        results = await repo.get_all(user_id=user.id)
        assert len(results) == 1

        results2 = await repo.get_all(user_id=user2.id)
        assert len(results2) == 0

    async def test_update(self, session, user, product):
        repo = ConversionRepository(session)
        conv = await repo.create(
            user_id=user.id, product_id=product.id, status="pending"
        )

        updated = await repo.update(conv.id, status="processing")
        assert updated is not None
        assert updated.status == "processing"

    async def test_update_not_found(self, session):
        repo = ConversionRepository(session)
        result = await repo.update(uuid.uuid4(), status="completed")
        assert result is None

    async def test_delete_not_found(self, session):
        repo = ConversionRepository(session)
        deleted = await repo.delete(uuid.uuid4())
        assert deleted is False
