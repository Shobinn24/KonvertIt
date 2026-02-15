"""
Tests for JWT-protected API endpoints.

Verifies that all conversion, product, and listing endpoints:
1. Require authentication (401 without valid token)
2. Correctly extract user_id from JWT payload
3. Enforce tenant isolation (users can only access their own resources)
4. Handle DB queries correctly for list/detail/update operations

Uses FastAPI's TestClient with httpx + dependency overrides to avoid
needing a real database or JWT tokens in tests.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConversionError, KonvertItError
from app.db.database import get_db
from app.db.models import Conversion, Listing, Product
from app.main import create_app
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limiter import RateLimitInfo, get_redis


# ─── Fixtures ────────────────────────────────────────────────

TEST_USER_ID = str(uuid.uuid4())
TEST_USER_EMAIL = "testuser@example.com"
TEST_USER_TIER = "pro"

TEST_USER_PAYLOAD = {
    "sub": TEST_USER_ID,
    "email": TEST_USER_EMAIL,
    "tier": TEST_USER_TIER,
    "type": "access",
}


def _mock_redis_for_tests():
    """Create a mock Redis client that always allows requests."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)  # No existing count

    mock_pipe = AsyncMock()
    mock_pipe.incrby = MagicMock(return_value=mock_pipe)
    mock_pipe.expire = MagicMock(return_value=mock_pipe)
    mock_pipe.execute = AsyncMock(return_value=[1, True])
    mock.pipeline = MagicMock(return_value=mock_pipe)

    return mock


@pytest.fixture
def app():
    """Create a test app with dependency overrides."""
    application = create_app()

    # Override auth dependency to return test user payload
    application.dependency_overrides[get_current_user] = lambda: TEST_USER_PAYLOAD

    # Override DB dependency to return a mock session
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    async def mock_get_db():
        yield mock_session

    application.dependency_overrides[get_db] = mock_get_db

    # Override Redis dependency to return a mock that always allows requests
    mock_redis = _mock_redis_for_tests()

    async def mock_get_redis():
        return mock_redis

    application.dependency_overrides[get_redis] = mock_get_redis

    yield application, mock_session

    application.dependency_overrides.clear()


@pytest.fixture
def client(app):
    """Create a test client."""
    application, mock_session = app
    return TestClient(application)


@pytest.fixture
def unauthed_app():
    """Create a test app WITHOUT auth override (for 401 tests)."""
    application = create_app()
    # Only override DB and Redis, not auth
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(return_value=MagicMock())

    async def mock_get_db():
        yield mock_session

    application.dependency_overrides[get_db] = mock_get_db

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    async def mock_get_redis():
        return mock_redis

    application.dependency_overrides[get_redis] = mock_get_redis

    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(unauthed_app):
    """Test client without auth — requests should get 401/403."""
    return TestClient(unauthed_app)


# ─── Helper: Create mock ORM objects ─────────────────────────


def _mock_product(user_id=None, product_id=None) -> Product:
    """Create a mock Product ORM object."""
    p = MagicMock(spec=Product)
    p.id = product_id or uuid.uuid4()
    p.user_id = uuid.UUID(user_id) if user_id else uuid.UUID(TEST_USER_ID)
    p.source_marketplace = "amazon"
    p.source_url = "https://www.amazon.com/dp/B09C5RG6KV"
    p.source_product_id = "B09C5RG6KV"
    p.title = "Test Product"
    p.price = 25.99
    p.brand = "TestBrand"
    p.category = "Electronics"
    p.image_urls = ["https://example.com/img1.jpg"]
    p.scraped_at = datetime.now(UTC)
    p.created_at = datetime.now(UTC)
    return p


def _mock_listing(user_id=None, listing_id=None, status="active") -> Listing:
    """Create a mock Listing ORM object."""
    lst = MagicMock(spec=Listing)
    lst.id = listing_id or uuid.uuid4()
    lst.user_id = uuid.UUID(user_id) if user_id else uuid.UUID(TEST_USER_ID)
    lst.ebay_item_id = "123456789012"
    lst.title = "Test Listing"
    lst.price = 39.99
    lst.ebay_category_id = "67580"
    lst.status = status
    lst.listed_at = datetime.now(UTC)
    lst.last_synced_at = datetime.now(UTC)
    lst.created_at = datetime.now(UTC)
    lst.updated_at = datetime.now(UTC)
    return lst


def _mock_conversion(user_id=None, conversion_id=None) -> Conversion:
    """Create a mock Conversion ORM object."""
    c = MagicMock(spec=Conversion)
    c.id = conversion_id or uuid.uuid4()
    c.user_id = uuid.UUID(user_id) if user_id else uuid.UUID(TEST_USER_ID)
    c.product_id = uuid.uuid4()
    c.listing_id = None
    c.status = "completed"
    c.error_message = None
    c.converted_at = datetime.now(UTC)
    c.created_at = datetime.now(UTC)
    return c


# ─── Auth Required Tests (401 without token) ─────────────────


class TestAuthRequired:
    """Verify all protected endpoints return 401/403 without valid auth."""

    def test_conversions_create_requires_auth(self, unauthed_client):
        """POST /conversions should require auth."""
        resp = unauthed_client.post(
            "/api/v1/conversions/",
            json={"url": "https://amazon.com/dp/B09C5RG6KV"},
        )
        assert resp.status_code in (401, 403)  # HTTPBearer returns 401 or 403 when no token

    def test_conversions_bulk_requires_auth(self, unauthed_client):
        """POST /conversions/bulk should require auth."""
        resp = unauthed_client.post(
            "/api/v1/conversions/bulk",
            json={"urls": ["https://amazon.com/dp/B09C5RG6KV"]},
        )
        assert resp.status_code in (401, 403)

    def test_conversions_preview_requires_auth(self, unauthed_client):
        """POST /conversions/preview should require auth."""
        resp = unauthed_client.post(
            "/api/v1/conversions/preview",
            json={"url": "https://amazon.com/dp/B09C5RG6KV"},
        )
        assert resp.status_code in (401, 403)

    def test_conversions_list_requires_auth(self, unauthed_client):
        """GET /conversions should require auth."""
        resp = unauthed_client.get("/api/v1/conversions/")
        assert resp.status_code in (401, 403)

    def test_conversions_bulk_stream_requires_auth(self, unauthed_client):
        """POST /conversions/bulk/stream should require auth."""
        resp = unauthed_client.post(
            "/api/v1/conversions/bulk/stream",
            json={"urls": ["https://amazon.com/dp/B09C5RG6KV"]},
        )
        assert resp.status_code in (401, 403)

    def test_conversions_job_status_requires_auth(self, unauthed_client):
        """GET /conversions/jobs/{id} should require auth."""
        resp = unauthed_client.get(f"/api/v1/conversions/jobs/{uuid.uuid4()}")
        assert resp.status_code in (401, 403)

    def test_conversions_job_cancel_requires_auth(self, unauthed_client):
        """POST /conversions/jobs/{id}/cancel should require auth."""
        resp = unauthed_client.post(f"/api/v1/conversions/jobs/{uuid.uuid4()}/cancel")
        assert resp.status_code in (401, 403)

    def test_products_scrape_requires_auth(self, unauthed_client):
        """POST /products/scrape should require auth."""
        resp = unauthed_client.post(
            "/api/v1/products/scrape",
            json={"url": "https://amazon.com/dp/B09C5RG6KV"},
        )
        assert resp.status_code in (401, 403)

    def test_products_list_requires_auth(self, unauthed_client):
        """GET /products should require auth."""
        resp = unauthed_client.get("/api/v1/products/")
        assert resp.status_code in (401, 403)

    def test_products_detail_requires_auth(self, unauthed_client):
        """GET /products/{id} should require auth."""
        resp = unauthed_client.get(f"/api/v1/products/{uuid.uuid4()}")
        assert resp.status_code in (401, 403)

    def test_listings_list_requires_auth(self, unauthed_client):
        """GET /listings should require auth."""
        resp = unauthed_client.get("/api/v1/listings/")
        assert resp.status_code in (401, 403)

    def test_listings_detail_requires_auth(self, unauthed_client):
        """GET /listings/{id} should require auth."""
        resp = unauthed_client.get(f"/api/v1/listings/{uuid.uuid4()}")
        assert resp.status_code in (401, 403)

    def test_listings_update_price_requires_auth(self, unauthed_client):
        """PUT /listings/{id}/price should require auth."""
        resp = unauthed_client.put(
            f"/api/v1/listings/{uuid.uuid4()}/price",
            json={"price": 29.99},
        )
        assert resp.status_code in (401, 403)

    def test_listings_end_requires_auth(self, unauthed_client):
        """POST /listings/{id}/end should require auth."""
        resp = unauthed_client.post(f"/api/v1/listings/{uuid.uuid4()}/end")
        assert resp.status_code in (401, 403)


# ─── Listing Endpoint Tests ──────────────────────────────────


class TestListListings:
    """Tests for GET /listings."""

    def test_list_listings_empty(self, app):
        """Should return empty list when no listings."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[])

            resp = client.get("/api/v1/listings/")

        assert resp.status_code == 200
        data = resp.json()
        assert data["listings"] == []
        assert data["total"] == 0

    def test_list_listings_returns_data(self, app):
        """Should return listing data for authenticated user."""
        application, mock_session = app
        client = TestClient(application)

        listing = _mock_listing()
        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[listing])

            resp = client.get("/api/v1/listings/")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["listings"][0]["title"] == "Test Listing"
        assert data["listings"][0]["price"] == 39.99

    def test_list_listings_with_status_filter(self, app):
        """Should pass status filter to repository."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[])

            resp = client.get("/api/v1/listings/?status=active")

        assert resp.status_code == 200
        mock_repo.find_by_user.assert_called_once()
        call_kwargs = mock_repo.find_by_user.call_args
        assert call_kwargs.kwargs.get("status") == "active" or call_kwargs[1].get("status") == "active"

    def test_list_listings_pagination(self, app):
        """Should pass limit/offset to repository."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[])

            resp = client.get("/api/v1/listings/?limit=10&offset=20")

        assert resp.status_code == 200
        call_kwargs = mock_repo.find_by_user.call_args
        assert call_kwargs.kwargs.get("limit") == 10 or call_kwargs[1].get("limit") == 10


class TestGetListing:
    """Tests for GET /listings/{id}."""

    def test_get_listing_success(self, app):
        """Should return listing details for valid ID."""
        application, mock_session = app
        client = TestClient(application)

        listing = _mock_listing()
        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=listing)

            resp = client.get(f"/api/v1/listings/{listing.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Listing"
        assert data["price"] == 39.99
        assert data["status"] == "active"

    def test_get_listing_not_found(self, app):
        """Should return 404 for nonexistent listing."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=None)

            resp = client.get(f"/api/v1/listings/{uuid.uuid4()}")

        assert resp.status_code == 404

    def test_get_listing_tenant_isolation(self, app):
        """Should return 404 when listing belongs to another user."""
        application, mock_session = app
        client = TestClient(application)

        other_user_id = str(uuid.uuid4())
        listing = _mock_listing(user_id=other_user_id)

        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=listing)

            resp = client.get(f"/api/v1/listings/{listing.id}")

        assert resp.status_code == 404

    def test_get_listing_invalid_id(self, client):
        """Should return 400 for invalid UUID format."""
        resp = client.get("/api/v1/listings/not-a-uuid")
        assert resp.status_code == 400
        assert "Invalid listing ID" in resp.json()["detail"]


class TestUpdateListingPrice:
    """Tests for PUT /listings/{id}/price."""

    def test_update_price_success(self, app):
        """Should update price for authenticated user's listing."""
        application, mock_session = app
        client = TestClient(application)

        listing = _mock_listing()
        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=listing)

            resp = client.put(
                f"/api/v1/listings/{listing.id}/price",
                json={"price": 49.99},
            )

        assert resp.status_code == 200
        assert listing.price == 49.99

    def test_update_price_not_found(self, app):
        """Should return 404 for nonexistent listing."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=None)

            resp = client.put(
                f"/api/v1/listings/{uuid.uuid4()}/price",
                json={"price": 49.99},
            )

        assert resp.status_code == 404

    def test_update_price_tenant_isolation(self, app):
        """Should return 404 when listing belongs to another user."""
        application, mock_session = app
        client = TestClient(application)

        other_user_id = str(uuid.uuid4())
        listing = _mock_listing(user_id=other_user_id)

        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=listing)

            resp = client.put(
                f"/api/v1/listings/{listing.id}/price",
                json={"price": 49.99},
            )

        assert resp.status_code == 404

    def test_update_price_invalid_price(self, client):
        """Should reject zero or negative price."""
        resp = client.put(
            f"/api/v1/listings/{uuid.uuid4()}/price",
            json={"price": 0},
        )
        assert resp.status_code == 422  # Pydantic validation (gt=0)

    def test_update_price_missing_price(self, client):
        """Should reject missing price field."""
        resp = client.put(
            f"/api/v1/listings/{uuid.uuid4()}/price",
            json={},
        )
        assert resp.status_code == 422


class TestEndListing:
    """Tests for POST /listings/{id}/end."""

    def test_end_active_listing(self, app):
        """Should end an active listing."""
        application, mock_session = app
        client = TestClient(application)

        listing = _mock_listing(status="active")
        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=listing)

            resp = client.post(f"/api/v1/listings/{listing.id}/end")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ended"
        assert listing.status == "ended"

    def test_end_draft_listing(self, app):
        """Should end a draft listing."""
        application, mock_session = app
        client = TestClient(application)

        listing = _mock_listing(status="draft")
        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=listing)

            resp = client.post(f"/api/v1/listings/{listing.id}/end")

        assert resp.status_code == 200
        assert listing.status == "ended"

    def test_end_already_ended_listing(self, app):
        """Should return 409 for already ended listing."""
        application, mock_session = app
        client = TestClient(application)

        listing = _mock_listing(status="ended")
        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=listing)

            resp = client.post(f"/api/v1/listings/{listing.id}/end")

        assert resp.status_code == 409
        assert "Cannot end listing" in resp.json()["detail"]

    def test_end_error_listing(self, app):
        """Should return 409 for listing in error status."""
        application, mock_session = app
        client = TestClient(application)

        listing = _mock_listing(status="error")
        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=listing)

            resp = client.post(f"/api/v1/listings/{listing.id}/end")

        assert resp.status_code == 409

    def test_end_listing_not_found(self, app):
        """Should return 404 for nonexistent listing."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=None)

            resp = client.post(f"/api/v1/listings/{uuid.uuid4()}/end")

        assert resp.status_code == 404

    def test_end_listing_tenant_isolation(self, app):
        """Should return 404 when listing belongs to another user."""
        application, mock_session = app
        client = TestClient(application)

        other_user_id = str(uuid.uuid4())
        listing = _mock_listing(user_id=other_user_id, status="active")

        with patch(
            "app.api.v1.listings.ListingRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=listing)

            resp = client.post(f"/api/v1/listings/{listing.id}/end")

        assert resp.status_code == 404


# ─── Product Endpoint Tests ──────────────────────────────────


class TestListProducts:
    """Tests for GET /products."""

    def test_list_products_empty(self, app):
        """Should return empty list when no products."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.products.ProductRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[])

            resp = client.get("/api/v1/products/")

        assert resp.status_code == 200
        data = resp.json()
        assert data["products"] == []
        assert data["total"] == 0

    def test_list_products_returns_data(self, app):
        """Should return product data for authenticated user."""
        application, mock_session = app
        client = TestClient(application)

        product = _mock_product()
        with patch(
            "app.api.v1.products.ProductRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[product])

            resp = client.get("/api/v1/products/")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["products"][0]["title"] == "Test Product"
        assert data["products"][0]["price"] == 25.99

    def test_list_products_marketplace_filter(self, app):
        """Should pass marketplace filter to repository."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.products.ProductRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[])

            resp = client.get("/api/v1/products/?marketplace=amazon")

        assert resp.status_code == 200
        call_kwargs = mock_repo.find_by_user.call_args
        assert call_kwargs.kwargs.get("marketplace") == "amazon" or call_kwargs[1].get("marketplace") == "amazon"

    def test_list_products_pagination(self, app):
        """Should pass limit/offset to repository."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.products.ProductRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[])

            resp = client.get("/api/v1/products/?limit=5&offset=10")

        assert resp.status_code == 200
        call_kwargs = mock_repo.find_by_user.call_args
        assert call_kwargs.kwargs.get("limit") == 5 or call_kwargs[1].get("limit") == 5


class TestGetProduct:
    """Tests for GET /products/{id}."""

    def test_get_product_success(self, app):
        """Should return product details for valid ID."""
        application, mock_session = app
        client = TestClient(application)

        product = _mock_product()
        with patch(
            "app.api.v1.products.ProductRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=product)

            resp = client.get(f"/api/v1/products/{product.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Product"
        assert data["price"] == 25.99
        assert data["source_marketplace"] == "amazon"

    def test_get_product_not_found(self, app):
        """Should return 404 for nonexistent product."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.products.ProductRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=None)

            resp = client.get(f"/api/v1/products/{uuid.uuid4()}")

        assert resp.status_code == 404

    def test_get_product_tenant_isolation(self, app):
        """Should return 404 when product belongs to another user."""
        application, mock_session = app
        client = TestClient(application)

        other_user_id = str(uuid.uuid4())
        product = _mock_product(user_id=other_user_id)

        with patch(
            "app.api.v1.products.ProductRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=product)

            resp = client.get(f"/api/v1/products/{product.id}")

        assert resp.status_code == 404

    def test_get_product_invalid_id(self, client):
        """Should return 400 for invalid UUID format."""
        resp = client.get("/api/v1/products/not-a-uuid")
        assert resp.status_code == 400
        assert "Invalid product ID" in resp.json()["detail"]


# ─── Conversion Endpoint Tests ────────────────────────────────


class TestListConversions:
    """Tests for GET /conversions."""

    def test_list_conversions_empty(self, app):
        """Should return empty list when no conversions."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.conversions.ConversionRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[])

            resp = client.get("/api/v1/conversions/")

        assert resp.status_code == 200
        data = resp.json()
        assert data["conversions"] == []
        assert data["total"] == 0

    def test_list_conversions_returns_data(self, app):
        """Should return conversion data for authenticated user."""
        application, mock_session = app
        client = TestClient(application)

        conversion = _mock_conversion()
        with patch(
            "app.api.v1.conversions.ConversionRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[conversion])

            resp = client.get("/api/v1/conversions/")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["conversions"][0]["status"] == "completed"

    def test_list_conversions_status_filter(self, app):
        """Should pass status filter to repository."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.conversions.ConversionRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[])

            resp = client.get("/api/v1/conversions/?status=completed")

        assert resp.status_code == 200
        call_kwargs = mock_repo.find_by_user.call_args
        assert call_kwargs.kwargs.get("status") == "completed" or call_kwargs[1].get("status") == "completed"

    def test_list_conversions_pagination(self, app):
        """Should pass limit/offset to repository."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.conversions.ConversionRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.find_by_user = AsyncMock(return_value=[])

            resp = client.get("/api/v1/conversions/?limit=10&offset=5")

        assert resp.status_code == 200
        call_kwargs = mock_repo.find_by_user.call_args
        assert call_kwargs.kwargs.get("limit") == 10 or call_kwargs[1].get("limit") == 10


class TestConversionAuthPayload:
    """Tests that conversion endpoints correctly use JWT payload user_id."""

    def test_create_conversion_uses_jwt_user_id(self, app):
        """POST /conversions should pass user['sub'] as user_id to service."""
        application, mock_session = app
        client = TestClient(application)

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"status": "completed", "title": "Test"}

        with patch(
            "app.api.v1.conversions._get_conversion_service"
        ) as mock_get_svc:
            mock_svc = mock_get_svc.return_value
            mock_svc.convert_url = AsyncMock(return_value=mock_result)

            resp = client.post(
                "/api/v1/conversions/",
                json={"url": "https://amazon.com/dp/B09C5RG6KV"},
            )

        assert resp.status_code == 200
        # Verify user_id from JWT was passed to service
        call_kwargs = mock_svc.convert_url.call_args
        assert call_kwargs.kwargs.get("user_id") == TEST_USER_ID or call_kwargs[1].get("user_id") == TEST_USER_ID

    def test_bulk_conversion_uses_jwt_user_id(self, app):
        """POST /conversions/bulk should pass user['sub'] as user_id."""
        application, mock_session = app
        client = TestClient(application)

        mock_progress = MagicMock()
        mock_progress.to_dict.return_value = {
            "total": 1, "completed": 1, "failed": 0, "results": []
        }

        with patch(
            "app.api.v1.conversions._get_conversion_service"
        ) as mock_get_svc:
            mock_svc = mock_get_svc.return_value
            mock_svc.convert_bulk = AsyncMock(return_value=mock_progress)

            resp = client.post(
                "/api/v1/conversions/bulk",
                json={"urls": ["https://amazon.com/dp/B09C5RG6KV"]},
            )

        assert resp.status_code == 200
        call_kwargs = mock_svc.convert_bulk.call_args
        assert call_kwargs.kwargs.get("user_id") == TEST_USER_ID or call_kwargs[1].get("user_id") == TEST_USER_ID

    def test_preview_uses_jwt_user_id(self, app):
        """POST /conversions/preview should pass user['sub'] as user_id."""
        application, mock_session = app
        client = TestClient(application)

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"status": "preview", "title": "Test"}

        with patch(
            "app.api.v1.conversions._get_conversion_service"
        ) as mock_get_svc:
            mock_svc = mock_get_svc.return_value
            mock_svc.preview_conversion = AsyncMock(return_value=mock_result)

            resp = client.post(
                "/api/v1/conversions/preview",
                json={"url": "https://amazon.com/dp/B09C5RG6KV"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_svc.preview_conversion.call_args
        assert call_kwargs.kwargs.get("user_id") == TEST_USER_ID or call_kwargs[1].get("user_id") == TEST_USER_ID


class TestProductScrapeAuth:
    """Tests that product scrape endpoint correctly uses JWT payload."""

    def test_scrape_uses_jwt_user_id(self, app):
        """POST /products/scrape should pass user['sub'] as user_id."""
        application, mock_session = app
        client = TestClient(application)

        mock_result = MagicMock()
        mock_result.is_successful = True
        mock_result.to_dict.return_value = {"status": "success"}

        with patch(
            "app.api.v1.products.ConversionService"
        ) as MockSvc:
            mock_svc = MockSvc.return_value
            mock_svc.preview_conversion = AsyncMock(return_value=mock_result)

            resp = client.post(
                "/api/v1/products/scrape",
                json={"url": "https://amazon.com/dp/B09C5RG6KV"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_svc.preview_conversion.call_args
        assert call_kwargs.kwargs.get("user_id") == TEST_USER_ID or call_kwargs[1].get("user_id") == TEST_USER_ID


# ─── Conversion Error Handling Tests ──────────────────────────


class TestConversionErrorHandling:
    """Tests that conversion endpoints handle errors properly."""

    def test_conversion_error_returns_400(self, app):
        """ConversionError should return 400."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.conversions._get_conversion_service"
        ) as mock_get_svc:
            mock_svc = mock_get_svc.return_value
            mock_svc.convert_url = AsyncMock(
                side_effect=ConversionError("Invalid URL")
            )

            resp = client.post(
                "/api/v1/conversions/",
                json={"url": "https://invalid.com"},
            )

        assert resp.status_code == 400
        assert "Invalid URL" in resp.json()["detail"]

    def test_konvertit_error_returns_500(self, app):
        """KonvertItError should return 500."""
        application, mock_session = app
        client = TestClient(application)

        with patch(
            "app.api.v1.conversions._get_conversion_service"
        ) as mock_get_svc:
            mock_svc = mock_get_svc.return_value
            mock_svc.convert_url = AsyncMock(
                side_effect=KonvertItError("Internal failure")
            )

            resp = client.post(
                "/api/v1/conversions/",
                json={"url": "https://amazon.com/dp/B09C5RG6KV"},
            )

        assert resp.status_code == 500


# ─── Health Check (no auth needed) ────────────────────────────


class TestHealthCheck:
    """Health check should work without authentication."""

    def test_health_no_auth_required(self, unauthed_client):
        """GET /health should not require authentication."""
        resp = unauthed_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "components" in data


# ─── Users Endpoints (already protected, verify consistency) ──


class TestUsersAuthConsistency:
    """Verify users endpoints remain properly protected."""

    def test_users_me_requires_auth(self, unauthed_client):
        """GET /users/me should require auth."""
        resp = unauthed_client.get("/api/v1/users/me")
        assert resp.status_code in (401, 403)

    def test_users_me_update_requires_auth(self, unauthed_client):
        """PUT /users/me should require auth."""
        resp = unauthed_client.put(
            "/api/v1/users/me",
            json={"email": "new@example.com"},
        )
        assert resp.status_code in (401, 403)

    def test_users_usage_requires_auth(self, unauthed_client):
        """GET /users/me/usage should require auth."""
        resp = unauthed_client.get("/api/v1/users/me/usage")
        assert resp.status_code in (401, 403)

    def test_auth_login_no_auth_required(self, unauthed_client):
        """POST /auth/login should NOT require auth (it IS the auth endpoint)."""
        # This should fail with 422 (validation error, not 403)
        resp = unauthed_client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422  # Missing email/password, but no 403

    def test_auth_register_no_auth_required(self, unauthed_client):
        """POST /auth/register should NOT require auth."""
        resp = unauthed_client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422  # Missing email/password, but no 403

    def test_auth_refresh_no_auth_required(self, unauthed_client):
        """POST /auth/refresh should NOT require auth."""
        resp = unauthed_client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 422  # Missing refresh_token, but no 403
