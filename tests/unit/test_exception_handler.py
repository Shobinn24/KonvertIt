"""Tests for app.middleware.exception_handler — global exception handlers."""

from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.exceptions import (
    CircuitBreakerOpenError,
    ComplianceViolationError,
    ConversionError,
    KonvertItError,
    ListingError,
    ProductNotFoundError,
    ScrapingError,
)
from app.middleware.exception_handler import register_exception_handlers


def _make_app_with_handler(exc_to_raise: Exception) -> FastAPI:
    """Create a minimal FastAPI app that raises the given exception."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test")
    async def test_route():
        raise exc_to_raise

    return app


class TestKonvertItErrorMapping:
    """Verify KonvertItError subclasses map to correct HTTP status codes."""

    def test_product_not_found_returns_404(self):
        app = _make_app_with_handler(ProductNotFoundError("product gone"))
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 404
        assert resp.json()["error_type"] == "ProductNotFoundError"
        assert "product gone" in resp.json()["detail"]

    def test_compliance_violation_returns_422(self):
        app = _make_app_with_handler(ComplianceViolationError(brand="Nike", violations=["VeRO"]))
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 422
        assert resp.json()["error_type"] == "ComplianceViolationError"

    def test_conversion_error_returns_400(self):
        app = _make_app_with_handler(ConversionError("bad data"))
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 400
        assert resp.json()["error_type"] == "ConversionError"

    def test_scraping_error_returns_502(self):
        app = _make_app_with_handler(ScrapingError("timeout"))
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 502
        assert resp.json()["error_type"] == "ScrapingError"

    def test_circuit_breaker_open_returns_503(self):
        app = _make_app_with_handler(
            CircuitBreakerOpenError(source="amazon", cooldown_remaining=120)
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 503
        assert resp.json()["error_type"] == "CircuitBreakerOpenError"

    def test_listing_error_returns_502(self):
        app = _make_app_with_handler(ListingError("eBay API down"))
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 502
        assert resp.json()["error_type"] == "ListingError"

    def test_base_konvertit_error_returns_500(self):
        app = _make_app_with_handler(KonvertItError("unknown"))
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 500
        assert resp.json()["error_type"] == "KonvertItError"


class TestUnhandledException:
    """Verify catch-all handler for unexpected errors."""

    def test_returns_500_with_error_id(self):
        app = _make_app_with_handler(RuntimeError("kaboom"))
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 500
        body = resp.json()
        assert body["detail"] == "Internal server error"
        assert "error_id" in body
        assert len(body["error_id"]) == 8

    @patch("app.middleware.exception_handler.logger")
    def test_logs_unhandled_exception(self, mock_logger):
        app = _make_app_with_handler(RuntimeError("kaboom"))
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/test")
        mock_logger.exception.assert_called_once()
        log_msg = mock_logger.exception.call_args[0][0]
        assert "Unhandled exception" in log_msg
        assert "error_id=" in log_msg

    @patch("app.middleware.exception_handler.logger")
    def test_logs_konvertit_error(self, mock_logger):
        app = _make_app_with_handler(ScrapingError("timeout"))
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/test")
        mock_logger.error.assert_called_once()
        log_msg = mock_logger.error.call_args[0][0]
        assert "ScrapingError" in log_msg


class TestHTTPExceptionPassthrough:
    """Verify HTTPException is handled by FastAPI, not our handler."""

    def test_http_exception_401_passthrough(self):
        app = _make_app_with_handler(HTTPException(status_code=401, detail="unauthorized"))
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "unauthorized"
        # No error_id — FastAPI's built-in handler, not ours
        assert "error_id" not in resp.json()

    def test_http_exception_404_passthrough(self):
        app = _make_app_with_handler(HTTPException(status_code=404, detail="not found"))
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "not found"
