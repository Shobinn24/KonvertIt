"""
Tests for price history API endpoints.

Covers:
- GET /products/{id}/prices — price history list
- GET /products/{id}/prices/stats — aggregate stats
- Auth required (401)
- Tenant isolation (404 for other user's product)
- Invalid product ID (400)
"""

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Product, PriceHistory
from app.main import create_app
from app.middleware.auth_middleware import get_current_user

# ─── Test Constants ────────────────────────────────────────

TEST_USER_ID = str(uuid.uuid4())
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PAYLOAD = {
    "sub": TEST_USER_ID,
    "email": TEST_USER_EMAIL,
    "tier": "free",
    "type": "access",
}


# ─── Helpers ───────────────────────────────────────────────


def _mock_product(user_id: str = TEST_USER_ID) -> MagicMock:
    p = MagicMock(spec=Product)
    p.id = uuid.uuid4()
    p.user_id = uuid.UUID(user_id)
    p.source_marketplace = "amazon"
    p.source_url = "https://www.amazon.com/dp/B09TEST123"
    p.source_product_id = "B09TEST123"
    p.title = "Test Product"
    p.price = 29.99
    p.brand = "TestBrand"
    p.category = "Electronics"
    p.image_urls = []
    return p


def _mock_price_history(product_id: uuid.UUID, price: float = 29.99) -> MagicMock:
    ph = MagicMock(spec=PriceHistory)
    ph.id = uuid.uuid4()
    ph.product_id = product_id
    ph.price = price
    ph.currency = "USD"
    ph.recorded_at = MagicMock()
    ph.recorded_at.isoformat.return_value = "2026-02-12T10:00:00+00:00"
    return ph


# ─── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def app():
    application = create_app()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    application.dependency_overrides[get_current_user] = lambda: TEST_USER_PAYLOAD

    async def mock_get_db():
        yield mock_session

    application.dependency_overrides[get_db] = mock_get_db

    yield application, mock_session
    application.dependency_overrides.clear()


@pytest.fixture
def client(app):
    application, _ = app
    return TestClient(application)


@pytest.fixture
def mock_session(app):
    _, session = app
    return session


@pytest.fixture
def unauthed_client():
    """Client without auth override — for 401 tests."""
    application = create_app()

    mock_session = AsyncMock(spec=AsyncSession)

    async def mock_get_db():
        yield mock_session

    application.dependency_overrides[get_db] = mock_get_db

    client = TestClient(application)
    yield client
    application.dependency_overrides.clear()


# ─── GET /products/{id}/prices Tests ──────────────────────


class TestGetPriceHistory:
    def test_returns_price_history(self, client, mock_session):
        product = _mock_product()
        history = [
            _mock_price_history(product.id, 29.99),
            _mock_price_history(product.id, 27.50),
        ]

        # BaseRepository.get_by_id uses session.get()
        mock_session.get = AsyncMock(return_value=product)
        # PriceHistoryRepository.get_history uses session.execute()
        mock_session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=history))),
        ))

        resp = client.get(f"/api/v1/products/{product.id}/prices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_id"] == str(product.id)
        assert len(data["prices"]) == 2
        assert data["prices"][0]["price"] == 29.99
        assert data["prices"][0]["currency"] == "USD"

    def test_product_not_found(self, client, mock_session):
        fake_id = uuid.uuid4()

        # BaseRepository.get_by_id uses session.get()
        mock_session.get = AsyncMock(return_value=None)

        resp = client.get(f"/api/v1/products/{fake_id}/prices")
        assert resp.status_code == 404

    def test_tenant_isolation(self, client, mock_session):
        """Products belonging to another user return 404."""
        other_user_id = str(uuid.uuid4())
        product = _mock_product(user_id=other_user_id)

        # BaseRepository.get_by_id uses session.get()
        mock_session.get = AsyncMock(return_value=product)

        resp = client.get(f"/api/v1/products/{product.id}/prices")
        assert resp.status_code == 404

    def test_invalid_product_id(self, client):
        resp = client.get("/api/v1/products/not-a-uuid/prices")
        assert resp.status_code == 400

    def test_requires_auth(self, unauthed_client):
        fake_id = uuid.uuid4()
        resp = unauthed_client.get(f"/api/v1/products/{fake_id}/prices")
        assert resp.status_code == 401


# ─── GET /products/{id}/prices/stats Tests ────────────────


class TestGetPriceStats:
    def test_returns_stats(self, client, mock_session):
        product = _mock_product()

        # BaseRepository.get_by_id uses session.get()
        mock_session.get = AsyncMock(return_value=product)
        # PriceHistoryRepository.get_price_stats uses session.execute()
        mock_session.execute = AsyncMock(return_value=MagicMock(
            one=MagicMock(return_value=(19.99, 34.99, 27.49, 5)),
        ))

        resp = client.get(f"/api/v1/products/{product.id}/prices/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_id"] == str(product.id)
        assert data["current_price"] == 29.99
        assert data["min_price"] == 19.99
        assert data["max_price"] == 34.99
        assert data["avg_price"] == 27.49
        assert data["count"] == 5

    def test_stats_product_not_found(self, client, mock_session):
        fake_id = uuid.uuid4()

        # BaseRepository.get_by_id uses session.get()
        mock_session.get = AsyncMock(return_value=None)

        resp = client.get(f"/api/v1/products/{fake_id}/prices/stats")
        assert resp.status_code == 404

    def test_stats_requires_auth(self, unauthed_client):
        fake_id = uuid.uuid4()
        resp = unauthed_client.get(f"/api/v1/products/{fake_id}/prices/stats")
        assert resp.status_code == 401
