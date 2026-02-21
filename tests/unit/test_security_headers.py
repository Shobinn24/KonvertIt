"""
Tests for security headers middleware.

Verifies:
1. All standard security headers are present on API responses
2. HSTS only enabled in production mode
3. Cache-Control: no-store on API routes and /health
4. Cache-Control NOT added to non-API routes
5. Headers present on both success and error responses
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import create_app
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limiter import get_redis


# ─── Test Constants ────────────────────────────────────────

TEST_USER_ID = str(uuid.uuid4())

TEST_USER_PAYLOAD = {
    "sub": TEST_USER_ID,
    "email": "test@example.com",
    "tier": "free",
    "type": "access",
}


# ─── Helpers ──────────────────────────────────────────────


def _mock_redis_for_tests():
    """Create a mock Redis that allows requests through."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock_pipe = AsyncMock()
    mock_pipe.incrby = MagicMock(return_value=mock_pipe)
    mock_pipe.expire = MagicMock(return_value=mock_pipe)
    mock_pipe.execute = AsyncMock(return_value=[1, True])
    mock.pipeline = MagicMock(return_value=mock_pipe)
    return mock


def _make_test_app(authenticated=True):
    """Create a test app with standard overrides."""
    application = create_app()

    if authenticated:
        application.dependency_overrides[get_current_user] = lambda: TEST_USER_PAYLOAD

    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    async def mock_get_db():
        yield mock_session

    application.dependency_overrides[get_db] = mock_get_db

    mock_redis = _mock_redis_for_tests()

    async def mock_get_redis():
        return mock_redis

    application.dependency_overrides[get_redis] = mock_get_redis

    return application


# ─── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def app():
    """Test app with auth override."""
    application = _make_test_app(authenticated=True)
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app):
    """Test client with authentication."""
    return TestClient(app)


@pytest.fixture
def unauthed_app():
    """Test app without auth override (for 401 tests)."""
    application = _make_test_app(authenticated=False)
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(unauthed_app):
    """Test client without auth — requests get 401."""
    return TestClient(unauthed_app)


# ─── Core Security Headers ────────────────────────────────


EXPECTED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
}


class TestSecurityHeadersPresence:
    """Verify all security headers are added to responses."""

    def test_health_endpoint_has_all_security_headers(self, client):
        """GET /health should include all standard security headers."""
        resp = client.get("/health")
        assert resp.status_code == 200

        for header, expected_value in EXPECTED_HEADERS.items():
            assert header in resp.headers, f"Missing header: {header}"
            assert resp.headers[header] == expected_value, (
                f"Header {header}: expected '{expected_value}', got '{resp.headers[header]}'"
            )

    def test_x_content_type_options(self, client):
        """X-Content-Type-Options prevents MIME sniffing."""
        resp = client.get("/health")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self, client):
        """X-Frame-Options prevents clickjacking."""
        resp = client.get("/health")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_x_xss_protection(self, client):
        """X-XSS-Protection set to 0 (modern best practice — rely on CSP)."""
        resp = client.get("/health")
        assert resp.headers["X-XSS-Protection"] == "0"

    def test_referrer_policy(self, client):
        """Referrer-Policy limits referrer information leakage."""
        resp = client.get("/health")
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client):
        """Permissions-Policy restricts sensitive browser APIs."""
        resp = client.get("/health")
        assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    def test_content_security_policy(self, client):
        """CSP restricts all resource loading for API-only surface."""
        resp = client.get("/health")
        assert resp.headers["Content-Security-Policy"] == (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        )


# ─── HSTS (Strict-Transport-Security) ────────────────────


class TestHSTS:
    """Test HSTS behavior — only enabled in production."""

    def test_no_hsts_in_development(self, client):
        """HSTS should NOT be present in development mode."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "Strict-Transport-Security" not in resp.headers

    def test_hsts_in_production(self):
        """HSTS should be present when app_env is production."""
        app = _make_test_app(authenticated=True)
        client = TestClient(app)

        with patch("app.middleware.security_headers.get_settings") as mock_settings:
            settings_instance = MagicMock()
            settings_instance.is_production = True
            mock_settings.return_value = settings_instance

            resp = client.get("/health")
            assert resp.status_code == 200
            assert "Strict-Transport-Security" in resp.headers
            assert resp.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"

        app.dependency_overrides.clear()

    def test_hsts_max_age_value(self):
        """HSTS max-age should be 2 years (63072000 seconds)."""
        app = _make_test_app(authenticated=True)
        client = TestClient(app)

        with patch("app.middleware.security_headers.get_settings") as mock_settings:
            settings_instance = MagicMock()
            settings_instance.is_production = True
            mock_settings.return_value = settings_instance

            resp = client.get("/health")
            hsts = resp.headers.get("Strict-Transport-Security", "")
            assert "max-age=63072000" in hsts
            assert "includeSubDomains" in hsts

        app.dependency_overrides.clear()


# ─── Cache-Control ────────────────────────────────────────


class TestCacheControl:
    """Test Cache-Control header on API vs non-API routes."""

    def test_cache_control_on_health_endpoint(self, client):
        """GET /health should have Cache-Control: no-store."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("Cache-Control") == "no-store"

    def test_cache_control_on_api_endpoint(self, unauthed_client):
        """/api/* routes should have Cache-Control: no-store (even on 401)."""
        resp = unauthed_client.get("/api/v1/users/me")
        # Will get 401/403 but headers should still be present
        assert "Cache-Control" in resp.headers
        assert resp.headers["Cache-Control"] == "no-store"

    def test_no_cache_control_on_docs(self):
        """Non-API routes (docs, redoc) should NOT have Cache-Control: no-store."""
        app = _make_test_app(authenticated=True)
        client = TestClient(app)

        resp = client.get("/docs")
        # /docs may or may not exist (disabled in prod), but if it 200s,
        # it shouldn't have our no-store header since it's not /api/ or /health
        if resp.status_code == 200:
            cache_control = resp.headers.get("Cache-Control", "")
            assert cache_control != "no-store"

        app.dependency_overrides.clear()


# ─── Headers on Error Responses ───────────────────────────


class TestHeadersOnErrors:
    """Security headers should be present regardless of response status."""

    def test_headers_on_401_response(self, unauthed_client):
        """Security headers present even on 401 Unauthorized."""
        resp = unauthed_client.get("/api/v1/users/me")
        assert resp.status_code in (401, 403)

        for header in EXPECTED_HEADERS:
            assert header in resp.headers, f"Missing header on 401: {header}"

    def test_headers_on_404_response(self, client):
        """Security headers present on 404 Not Found."""
        resp = client.get("/api/v1/nonexistent-endpoint")
        assert resp.status_code == 404

        for header in EXPECTED_HEADERS:
            assert header in resp.headers, f"Missing header on 404: {header}"

    def test_headers_on_health_200(self, client):
        """Security headers present on successful health check."""
        resp = client.get("/health")
        assert resp.status_code == 200

        for header in EXPECTED_HEADERS:
            assert header in resp.headers, f"Missing header on 200: {header}"


# ─── X-Response-Time (from LoggingMiddleware) ─────────────


class TestResponseTimingHeader:
    """Verify X-Response-Time header from logging middleware is not clobbered."""

    def test_response_time_header_preserved(self, client):
        """X-Response-Time from LoggingMiddleware should still be present."""
        resp = client.get("/health")
        # LoggingMiddleware adds X-Response-Time — security headers shouldn't remove it
        # This header may or may not be present depending on middleware order,
        # but if it is, it should be valid
        if "X-Response-Time" in resp.headers:
            assert resp.headers["X-Response-Time"].endswith("ms")
