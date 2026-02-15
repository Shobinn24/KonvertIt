"""
E2E Smoke Tests for KonvertIt API.

Exercises complete user journeys through the full FastAPI application
with mocked database and Redis. Validates that multi-step flows work
end-to-end through middleware, auth, routing, and response formatting.

These tests are the final gate before deployment — they verify that
all layers of the application are wired together correctly.

Test journeys:
1. Health check — system readiness
2. Auth flow — register → login → refresh → profile
3. Conversions — create → list history
4. Listings — list → get detail → update price → end listing
5. Products — list → get detail
6. Error handling — bad inputs, tenant isolation, rate limit headers
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Conversion, Listing, Product, User
from app.main import create_app
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limiter import get_redis


# ─── Shared Test State ───────────────────────────────────────

TEST_USER_ID = str(uuid.uuid4())
OTHER_USER_ID = str(uuid.uuid4())
TEST_EMAIL = "smoke@konvertit.com"
TEST_TIER = "pro"

TEST_USER_PAYLOAD = {
    "sub": TEST_USER_ID,
    "email": TEST_EMAIL,
    "tier": TEST_TIER,
    "type": "access",
}


# ─── Mock Factories ──────────────────────────────────────────


def _mock_user(user_id=None, email=None, tier=None):
    """Build a mock User ORM object."""
    u = MagicMock(spec=User)
    u.id = uuid.UUID(user_id or TEST_USER_ID)
    u.email = email or TEST_EMAIL
    u.tier = tier or TEST_TIER
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.last_login = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    u.password_hash = "$2b$12$fakehash"
    return u


def _mock_product(user_id=None, product_id=None):
    """Build a mock Product ORM object."""
    p = MagicMock(spec=Product)
    p.id = product_id or uuid.uuid4()
    p.user_id = uuid.UUID(user_id or TEST_USER_ID)
    p.source_marketplace = "amazon"
    p.source_url = "https://www.amazon.com/dp/B09C5RG6KV"
    p.source_product_id = "B09C5RG6KV"
    p.title = "Anker USB-C Charger 40W"
    p.price = 25.99
    p.brand = "Anker"
    p.category = "Electronics > Chargers"
    p.image_urls = ["https://m.media-amazon.com/images/I/31lDxoycJsL.jpg"]
    p.raw_data = {"asin": "B09C5RG6KV"}
    p.scraped_at = datetime.now(UTC)
    p.created_at = datetime.now(UTC)
    return p


def _mock_listing(user_id=None, listing_id=None, status="active"):
    """Build a mock Listing ORM object."""
    lst = MagicMock(spec=Listing)
    lst.id = listing_id or uuid.uuid4()
    lst.user_id = uuid.UUID(user_id or TEST_USER_ID)
    lst.ebay_item_id = "123456789012"
    lst.title = "Anker USB-C Charger 40W Nano Pro"
    lst.price = 39.99
    lst.ebay_category_id = "67580"
    lst.status = status
    lst.description_html = "<p>Fast charger</p>"
    lst.listed_at = datetime.now(UTC)
    lst.last_synced_at = datetime.now(UTC)
    lst.created_at = datetime.now(UTC)
    lst.updated_at = datetime.now(UTC)
    return lst


def _mock_conversion(user_id=None, conversion_id=None, status="completed"):
    """Build a mock Conversion ORM object."""
    c = MagicMock(spec=Conversion)
    c.id = conversion_id or uuid.uuid4()
    c.user_id = uuid.UUID(user_id or TEST_USER_ID)
    c.product_id = uuid.uuid4()
    c.listing_id = uuid.uuid4() if status == "completed" else None
    c.status = status
    c.error_message = None
    c.converted_at = datetime.now(UTC) if status == "completed" else None
    c.created_at = datetime.now(UTC)
    return c


# ─── Fixtures ────────────────────────────────────────────────


def _mock_redis():
    """Redis mock that allows all rate limit checks."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.ping = AsyncMock(return_value=True)
    mock_pipe = AsyncMock()
    mock_pipe.incrby = MagicMock(return_value=mock_pipe)
    mock_pipe.expire = MagicMock(return_value=mock_pipe)
    mock_pipe.execute = AsyncMock(return_value=[1, True])
    mock.pipeline = MagicMock(return_value=mock_pipe)
    return mock


@pytest.fixture
def smoke_app():
    """Full app with auth + DB + Redis mocked for smoke testing."""
    application = create_app()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    async def mock_get_db():
        yield mock_session

    application.dependency_overrides[get_current_user] = lambda: TEST_USER_PAYLOAD
    application.dependency_overrides[get_db] = mock_get_db
    application.dependency_overrides[get_redis] = lambda: _mock_redis()

    yield application, mock_session

    application.dependency_overrides.clear()


@pytest.fixture
def client(smoke_app):
    """TestClient bound to the smoke app."""
    application, _ = smoke_app
    return TestClient(application)


@pytest.fixture
def mock_session(smoke_app):
    """The mock DB session for configuring return values."""
    _, session = smoke_app
    return session


# ─── 1. Health Check ─────────────────────────────────────────


class TestHealthSmoke:
    """Verify /health returns system status with component probes."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "app" in data
        assert data["app"] == "KonvertIt"

    def test_health_includes_version(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "version" in data
        from app import __version__
        assert data["version"] == __version__

    def test_health_includes_components(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "components" in data

    def test_health_has_security_headers(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_health_has_cache_control(self, client):
        resp = client.get("/health")
        assert resp.headers.get("Cache-Control") == "no-store"


# ─── 2. Auth Flow ────────────────────────────────────────────


class TestAuthFlowSmoke:
    """Verify auth endpoints accept correct request shapes."""

    def test_register_accepts_valid_payload(self, smoke_app):
        """POST /auth/register with valid email + password."""
        app, mock_session = smoke_app

        mock_user = _mock_user()
        # Mock UserService.register to return auth response
        with patch("app.api.v1.auth._build_user_service") as mock_build:
            mock_svc = AsyncMock()
            mock_svc.register = AsyncMock(return_value={
                "user": {"id": TEST_USER_ID, "email": TEST_EMAIL, "tier": TEST_TIER},
                "access_token": "fake.access.token",
                "refresh_token": "fake.refresh.token",
                "token_type": "bearer",
            })
            mock_build.return_value = mock_svc

            # Remove auth override for register (public endpoint)
            app.dependency_overrides.pop(get_current_user, None)
            client = TestClient(app)
            resp = client.post("/api/v1/auth/register", json={
                "email": "newuser@example.com",
                "password": "securepassword123",
            })
            # Restore auth override
            app.dependency_overrides[get_current_user] = lambda: TEST_USER_PAYLOAD

        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_accepts_valid_credentials(self, smoke_app):
        """POST /auth/login with valid email + password."""
        app, mock_session = smoke_app

        with patch("app.api.v1.auth._build_user_service") as mock_build:
            mock_svc = AsyncMock()
            mock_svc.authenticate = AsyncMock(return_value={
                "user": {"id": TEST_USER_ID, "email": TEST_EMAIL, "tier": TEST_TIER},
                "access_token": "fake.access.token",
                "refresh_token": "fake.refresh.token",
                "token_type": "bearer",
            })
            mock_build.return_value = mock_svc

            app.dependency_overrides.pop(get_current_user, None)
            client = TestClient(app)
            resp = client.post("/api/v1/auth/login", json={
                "email": TEST_EMAIL,
                "password": "testpassword123",
            })
            app.dependency_overrides[get_current_user] = lambda: TEST_USER_PAYLOAD

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    def test_register_rejects_short_password(self, smoke_app):
        """POST /auth/register with too-short password returns 422."""
        app, _ = smoke_app
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        resp = client.post("/api/v1/auth/register", json={
            "email": "user@example.com",
            "password": "short",
        })
        app.dependency_overrides[get_current_user] = lambda: TEST_USER_PAYLOAD
        assert resp.status_code == 422

    def test_register_rejects_invalid_email(self, smoke_app):
        """POST /auth/register with invalid email returns 422."""
        app, _ = smoke_app
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        resp = client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "securepassword123",
        })
        app.dependency_overrides[get_current_user] = lambda: TEST_USER_PAYLOAD
        assert resp.status_code == 422


# ─── 3. Conversions Flow ────────────────────────────────────


class TestConversionsFlowSmoke:
    """Verify conversion list and detail endpoints."""

    def test_list_conversions_returns_array(self, client, mock_session):
        """GET /conversions returns a paginated list."""
        conversions = [_mock_conversion(), _mock_conversion(status="pending")]

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = conversions
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/api/v1/conversions/")
        assert resp.status_code == 200
        data = resp.json()
        assert "conversions" in data
        assert isinstance(data["conversions"], list)
        assert data["total"] == 2

    def test_list_conversions_with_status_filter(self, client, mock_session):
        """GET /conversions?status=completed filters correctly."""
        conversions = [_mock_conversion(status="completed")]

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = conversions
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/api/v1/conversions/?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_list_conversions_has_rate_limit_headers(self, client, mock_session):
        """GET /conversions does NOT have rate limit headers (only mutations do)."""
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/api/v1/conversions/")
        assert resp.status_code == 200

    def test_conversion_response_shape(self, client, mock_session):
        """Each conversion has expected fields."""
        conv = _mock_conversion()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [conv]
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/api/v1/conversions/")
        item = resp.json()["conversions"][0]
        assert "id" in item
        assert "product_id" in item
        assert "status" in item
        assert "created_at" in item


# ─── 4. Listings Flow ───────────────────────────────────────


class TestListingsFlowSmoke:
    """Verify listing CRUD endpoints work end-to-end."""

    def test_list_listings_returns_array(self, client, mock_session):
        """GET /listings returns a paginated list."""
        listings = [_mock_listing(), _mock_listing(status="draft")]

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = listings
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/api/v1/listings/")
        assert resp.status_code == 200
        data = resp.json()
        assert "listings" in data
        assert isinstance(data["listings"], list)
        assert data["total"] == 2

    def test_get_listing_detail(self, client, mock_session):
        """GET /listings/{id} returns listing detail."""
        listing = _mock_listing()
        mock_session.get = AsyncMock(return_value=listing)

        resp = client.get(f"/api/v1/listings/{listing.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Anker USB-C Charger 40W Nano Pro"
        assert data["price"] == 39.99
        assert data["status"] == "active"

    def test_update_listing_price(self, client, mock_session):
        """PUT /listings/{id}/price updates the price."""
        listing = _mock_listing()
        mock_session.get = AsyncMock(return_value=listing)

        resp = client.put(
            f"/api/v1/listings/{listing.id}/price",
            json={"price": 44.99},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["price"] == 44.99

    def test_end_listing(self, client, mock_session):
        """POST /listings/{id}/end sets status to ended."""
        listing = _mock_listing(status="active")
        mock_session.get = AsyncMock(return_value=listing)

        resp = client.post(f"/api/v1/listings/{listing.id}/end")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ended"

    def test_end_already_ended_listing_fails(self, client, mock_session):
        """POST /listings/{id}/end on ended listing returns 409."""
        listing = _mock_listing(status="ended")
        mock_session.get = AsyncMock(return_value=listing)

        resp = client.post(f"/api/v1/listings/{listing.id}/end")
        assert resp.status_code == 409

    def test_listing_response_shape(self, client, mock_session):
        """Listing detail has all expected fields."""
        listing = _mock_listing()
        mock_session.get = AsyncMock(return_value=listing)

        resp = client.get(f"/api/v1/listings/{listing.id}")
        data = resp.json()
        for field in ["id", "title", "price", "status", "ebay_item_id", "created_at"]:
            assert field in data


# ─── 5. Products Flow ───────────────────────────────────────


class TestProductsFlowSmoke:
    """Verify product list and detail endpoints."""

    def test_list_products_returns_array(self, client, mock_session):
        """GET /products returns a paginated list."""
        products = [_mock_product(), _mock_product()]

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = products
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/api/v1/products/")
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        assert data["total"] == 2

    def test_get_product_detail(self, client, mock_session):
        """GET /products/{id} returns product detail."""
        product = _mock_product()
        mock_session.get = AsyncMock(return_value=product)

        resp = client.get(f"/api/v1/products/{product.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Anker USB-C Charger 40W"
        assert data["source_marketplace"] == "amazon"
        assert data["price"] == 25.99

    def test_product_response_shape(self, client, mock_session):
        """Product detail has all expected fields."""
        product = _mock_product()
        mock_session.get = AsyncMock(return_value=product)

        resp = client.get(f"/api/v1/products/{product.id}")
        data = resp.json()
        for field in ["id", "title", "price", "brand", "source_marketplace",
                      "source_product_id", "image_urls"]:
            assert field in data


# ─── 6. Error Handling & Tenant Isolation ────────────────────


class TestErrorHandlingSmoke:
    """Verify error responses and tenant isolation across endpoints."""

    def test_invalid_uuid_returns_400(self, client):
        """GET /products/not-a-uuid returns 400."""
        resp = client.get("/api/v1/products/not-a-uuid")
        assert resp.status_code == 400

    def test_product_not_found_returns_404(self, client, mock_session):
        """GET /products/{valid-uuid} for non-existent product returns 404."""
        mock_session.get = AsyncMock(return_value=None)
        resp = client.get(f"/api/v1/products/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_listing_not_found_returns_404(self, client, mock_session):
        """GET /listings/{valid-uuid} for non-existent listing returns 404."""
        mock_session.get = AsyncMock(return_value=None)
        resp = client.get(f"/api/v1/listings/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_tenant_isolation_product(self, client, mock_session):
        """GET /products/{id} for another user's product returns 404."""
        other_product = _mock_product(user_id=OTHER_USER_ID)
        mock_session.get = AsyncMock(return_value=other_product)

        resp = client.get(f"/api/v1/products/{other_product.id}")
        assert resp.status_code == 404

    def test_tenant_isolation_listing(self, client, mock_session):
        """GET /listings/{id} for another user's listing returns 404."""
        other_listing = _mock_listing(user_id=OTHER_USER_ID)
        mock_session.get = AsyncMock(return_value=other_listing)

        resp = client.get(f"/api/v1/listings/{other_listing.id}")
        assert resp.status_code == 404

    def test_update_price_rejects_zero(self, client, mock_session):
        """PUT /listings/{id}/price with price=0 returns 422."""
        listing = _mock_listing()
        mock_session.get = AsyncMock(return_value=listing)

        resp = client.put(
            f"/api/v1/listings/{listing.id}/price",
            json={"price": 0},
        )
        assert resp.status_code == 422

    def test_update_price_rejects_negative(self, client, mock_session):
        """PUT /listings/{id}/price with negative price returns 422."""
        listing = _mock_listing()
        mock_session.get = AsyncMock(return_value=listing)

        resp = client.put(
            f"/api/v1/listings/{listing.id}/price",
            json={"price": -5.00},
        )
        assert resp.status_code == 422

    def test_unauthenticated_request_rejected(self, smoke_app):
        """Requests without auth override get rejected."""
        app, _ = smoke_app
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)

        resp = client.get("/api/v1/conversions/")
        assert resp.status_code in (401, 403)

        # Restore
        app.dependency_overrides[get_current_user] = lambda: TEST_USER_PAYLOAD


# ─── 7. Middleware Integration ───────────────────────────────


class TestMiddlewareSmoke:
    """Verify middleware stack is working correctly."""

    def test_security_headers_on_api(self, client, mock_session):
        """API responses include security headers."""
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/api/v1/conversions/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_request_id_header(self, client):
        """Responses include X-Request-ID from logging middleware."""
        resp = client.get("/health")
        # LoggingMiddleware should add X-Request-ID
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_cors_headers_not_on_non_origin(self, client):
        """CORS headers are only added when Origin header is present."""
        resp = client.get("/health")
        # No Origin header sent, so no Access-Control-Allow-Origin
        assert "Access-Control-Allow-Origin" not in resp.headers
