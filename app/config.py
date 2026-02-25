"""
KonvertIt application configuration.

Loads settings from environment variables with validation via Pydantic Settings.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ProxyProvider(StrEnum):
    SCRAPERAPI = "scraperapi"
    BRIGHTDATA = "brightdata"
    SMARTPROXY = "smartproxy"
    RAW = "raw"


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Application ──────────────────────────────────────────
    app_name: str = "KonvertIt"
    app_env: AppEnv = AppEnv.DEVELOPMENT
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-me-to-a-random-64-char-string"
    encryption_key: str = "change-me-generate-with-cryptography-fernet"

    # ─── Database ─────────────────────────────────────────────
    # Pool sizing: total connections = workers × (pool_size + max_overflow)
    # With 4 Gunicorn workers: max = 4 × (10 + 20) = 120 connections.
    # Ensure your database max_connections >= this value.
    # Railway / managed Postgres typically allows 20–100 — adjust accordingly
    # or use PgBouncer.
    database_url: str = "postgresql+asyncpg://konvertit:konvertit_dev@localhost:5432/konvertit"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_recycle: int = 1800  # Recycle connections after 30 min
    database_pool_pre_ping: bool = True  # Verify connections before reuse
    database_pool_timeout: int = 30  # Seconds to wait for a pool connection

    # ─── Redis ────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ─── eBay API ─────────────────────────────────────────────
    ebay_app_id: str = ""
    ebay_dev_id: str = ""
    ebay_cert_id: str = ""
    ebay_redirect_uri: str = ""
    ebay_sandbox: bool = True
    ebay_fulfillment_policy_id: str = ""
    ebay_payment_policy_id: str = ""
    ebay_return_policy_id: str = ""

    # ─── Proxy Configuration ─────────────────────────────────
    scraper_api_key: str = ""
    proxy_list: str = ""
    proxy_provider: ProxyProvider = ProxyProvider.SCRAPERAPI

    # ─── Scraping Configuration ──────────────────────────────
    scrape_min_delay: float = 2.0
    scrape_max_delay: float = 4.0
    scrape_max_retries: int = 3
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_seconds: int = 300

    # ─── JWT Authentication ──────────────────────────────────
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ─── Price Monitoring ────────────────────────────────────
    price_monitor_interval_hours: int = 6
    price_monitor_max_products: int = 200

    # ─── WebSocket ─────────────────────────────────────────
    ws_heartbeat_interval: int = 30
    ws_max_connections_free: int = 1
    ws_max_connections_pro: int = 3
    ws_max_connections_enterprise: int = 10

    # ─── Observability ──────────────────────────────────────────
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_profiles_sample_rate: float = 0.1
    log_level: str = "INFO"
    log_format: str = "auto"

    # ─── Performance ────────────────────────────────────────────
    query_slow_threshold_ms: int = 200  # Log queries slower than this
    cache_ttl_default: int = 300  # Default Redis cache TTL in seconds
    gzip_minimum_size: int = 500  # Min response bytes for gzip compression

    # ─── Stripe Billing ────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    stripe_enterprise_price_id: str = ""

    # ─── CORS ────────────────────────────────────────────────
    cors_allowed_origins: str = ""  # Comma-separated origins for production

    # ─── Playwright ───────────────────────────────────────────
    browser_pool_size: int = 3
    headless: bool = True

    @model_validator(mode="after")
    def normalize_database_url(self) -> "Settings":
        """Convert standard PostgreSQL URL to asyncpg format for SQLAlchemy async.

        Railway and other PaaS providers set DATABASE_URL as postgresql://...
        but SQLAlchemy async requires postgresql+asyncpg://...
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            self.database_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            self.database_url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return self

    @model_validator(mode="after")
    def enforce_production_safety(self) -> "Settings":
        """Block application boot if production safety invariants are violated.

        Only fires when APP_ENV=production. Development and test environments
        continue to work with placeholder defaults.
        """
        if self.app_env != AppEnv.PRODUCTION:
            return self

        violations: list[str] = []

        if self.app_debug:
            violations.append("APP_DEBUG must be False in production")

        if len(self.secret_key) < 32 or "change-me" in self.secret_key:
            violations.append(
                "SECRET_KEY must be >= 32 characters and not contain 'change-me'"
            )

        if "change-me" in self.encryption_key:
            violations.append("ENCRYPTION_KEY must not contain 'change-me'")

        if not self.cors_allowed_origins.strip():
            violations.append("CORS_ALLOWED_ORIGINS must be non-empty in production")

        if violations:
            raise ValueError(
                "Production safety check failed:\n  - " + "\n  - ".join(violations)
            )

        return self

    @property
    def is_development(self) -> bool:
        return self.app_env == AppEnv.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION

    @property
    def ebay_base_url(self) -> str:
        if self.ebay_sandbox:
            return "https://api.sandbox.ebay.com"
        return "https://api.ebay.com"

    @property
    def ebay_auth_url(self) -> str:
        if self.ebay_sandbox:
            return "https://auth.sandbox.ebay.com"
        return "https://auth.ebay.com"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings singleton."""
    return Settings()
