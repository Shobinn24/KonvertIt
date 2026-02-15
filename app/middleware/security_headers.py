"""
Security headers middleware.

Adds standard security headers to all HTTP responses to protect
against common web vulnerabilities (clickjacking, MIME sniffing,
cross-site scripting, etc.).

HSTS is only enabled in production to avoid breaking local HTTP dev.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to every HTTP response.

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 0 (modern best practice — rely on CSP)
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: restrict sensitive browser APIs
    - Content-Security-Policy: frame-ancestors 'none'
    - Strict-Transport-Security: only in production (HTTPS required)
    - Cache-Control: no-store for API responses
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Core security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"

        # HSTS — only in production (HTTP in dev would break)
        settings = get_settings()
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )

        # Cache-Control for API responses (not static assets)
        path = request.url.path
        if path.startswith("/api/") or path == "/health":
            response.headers["Cache-Control"] = "no-store"

        return response
