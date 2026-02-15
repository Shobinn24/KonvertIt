"""
Global exception handlers for the FastAPI application.

Catches:
1. KonvertItError subclasses — maps to appropriate HTTP status codes.
2. Unhandled Exception — 500 Internal Server Error with a unique
   ``error_id`` for customer-support correlation.

HTTPException is NOT handled here — FastAPI's built-in handler deals
with those, and Sentry's ``before_send`` filter drops 4xx events.
"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    CircuitBreakerOpenError,
    ComplianceViolationError,
    ConversionError,
    KonvertItError,
    ListingError,
    ProductNotFoundError,
    ScrapingError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers on the FastAPI app.

    Called from ``create_app()`` after all middleware and routers
    are registered.
    """

    @app.exception_handler(KonvertItError)
    async def handle_konvertit_error(request: Request, exc: KonvertItError) -> JSONResponse:
        """Map KonvertItError subclasses to HTTP status codes."""
        status_code = _get_status_code(exc)
        logger.error(
            f"{type(exc).__name__}: {exc.message}",
            exc_info=exc,
            extra={"error_type": type(exc).__name__, "path": request.url.path},
        )
        return JSONResponse(
            status_code=status_code,
            content={"detail": exc.message, "error_type": type(exc).__name__},
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unhandled exceptions: log, return 500 with error_id."""
        error_id = uuid.uuid4().hex[:8]
        logger.exception(
            f"Unhandled exception (error_id={error_id})",
            extra={"error_id": error_id, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_id": error_id,
            },
        )


def _get_status_code(exc: KonvertItError) -> int:
    """Map exception type to HTTP status code."""
    if isinstance(exc, ProductNotFoundError):
        return 404
    if isinstance(exc, ComplianceViolationError):
        return 422
    if isinstance(exc, ConversionError):
        return 400
    if isinstance(exc, ScrapingError):
        return 502
    if isinstance(exc, CircuitBreakerOpenError):
        return 503
    if isinstance(exc, ListingError):
        return 502
    # Base KonvertItError fallback
    return 500
