"""
Request/response logging middleware.

Logs all API requests with timing, status codes, and client context.
Binds a unique ``request_id`` to structlog's contextvars so that all
loggers invoked during request processing automatically include it.
"""

import logging
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("konvertit.api")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every HTTP request and response.

    Logs include:
    - Request method, path, and query parameters
    - Response status code
    - Request duration in milliseconds
    - Client IP address
    - Unique request_id (also returned as X-Request-ID header)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:8]

        # Bind request context — available to ALL loggers in this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
        )

        start_time = time.monotonic()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = round((time.monotonic() - start_time) * 1000, 1)

        # Skip logging for /health to reduce noise
        if request.url.path != "/health":
            logger.info(
                f"{request.method} {request.url.path} "
                f"→ {response.status_code} "
                f"({duration_ms}ms) "
                f"[{request.client.host if request.client else 'unknown'}]"
            )

        # Add headers
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        response.headers["X-Request-ID"] = request_id

        # Clear context to prevent leaking between requests
        structlog.contextvars.clear_contextvars()

        return response
