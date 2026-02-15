"""
Custom exception hierarchy for KonvertIt.

All application-specific exceptions inherit from KonvertItError,
enabling catch-all handling at the API layer while allowing
fine-grained handling in business logic.
"""


class KonvertItError(Exception):
    """Base exception for all KonvertIt application errors."""

    def __init__(self, message: str = "", details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# ─── Scraping Errors ──────────────────────────────────────────


class ScrapingError(KonvertItError):
    """General error during product scraping."""

    pass


class RateLimitError(ScrapingError):
    """Source marketplace returned a rate limit response (HTTP 429)."""

    pass


class CaptchaDetectedError(ScrapingError):
    """A CAPTCHA challenge was detected on the source page."""

    pass


class ProductNotFoundError(ScrapingError):
    """The requested product does not exist at the source URL (HTTP 404)."""

    pass


class DogPageError(ScrapingError):
    """Amazon returned a minimal 'dog page' indicating bot detection."""

    pass


class ProxyExhaustedError(ScrapingError):
    """All proxies in the pool have been exhausted or are unhealthy."""

    pass


# ─── Conversion Errors ────────────────────────────────────────


class ConversionError(KonvertItError):
    """Error during product data conversion."""

    pass


class ComplianceViolationError(ConversionError):
    """Product violates VeRO or other IP compliance rules."""

    def __init__(self, brand: str, violations: list[str], **kwargs):
        self.brand = brand
        self.violations = violations
        message = f"Compliance violation for brand '{brand}': {', '.join(violations)}"
        super().__init__(message=message, **kwargs)


# ─── Listing Errors ───────────────────────────────────────────


class ListingError(KonvertItError):
    """Error during listing creation or management on target marketplace."""

    pass


class EbayAuthError(ListingError):
    """eBay OAuth authentication error (expired token, invalid credentials, etc.)."""

    pass


# ─── Resilience Errors ────────────────────────────────────────


class CircuitBreakerOpenError(KonvertItError):
    """
    Circuit breaker is in OPEN state — requests are being blocked.

    This indicates the target service has had too many consecutive failures
    and is being temporarily bypassed to prevent cascading failures.
    """

    def __init__(self, source: str, cooldown_remaining: float = 0, **kwargs):
        self.source = source
        self.cooldown_remaining = cooldown_remaining
        message = (
            f"Circuit breaker OPEN for '{source}'. "
            f"Retry in {cooldown_remaining:.0f} seconds."
        )
        super().__init__(message=message, **kwargs)
