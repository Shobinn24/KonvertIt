"""
KonvertIt FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

import stripe
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import get_settings
from app.core.logging_config import setup_logging
from app.core.sentry_config import init_sentry
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.rate_limiter import close_redis, get_redis
from app.middleware.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    settings = get_settings()
    # Startup
    logger.info(f"Starting {settings.app_name} v{__version__} ({settings.app_env.value})")
    yield
    # Shutdown
    await close_redis()
    logger.info(f"Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""
    settings = get_settings()

    # 1. Configure structured logging (before anything else)
    setup_logging(
        app_env=settings.app_env,
        log_level=settings.log_level,
        log_format=settings.log_format,
    )

    # 2. Initialize Stripe API key once at startup (avoids per-request assignment)
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key

    # 3. Initialize Sentry (before app creation so ASGI integration hooks in)
    init_sentry(
        dsn=settings.sentry_dsn,
        app_env=settings.app_env,
        app_version=__version__,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
    )

    # OpenAPI tag descriptions for Swagger / ReDoc
    openapi_tags = [
        {
            "name": "Authentication",
            "description": "Register, login, refresh tokens, and eBay OAuth connection.",
        },
        {
            "name": "Users",
            "description": "User profile management and usage statistics.",
        },
        {
            "name": "Conversions",
            "description": "Convert Amazon/Walmart product URLs into eBay listing drafts. "
                           "Supports single, bulk, preview, and SSE-streamed operations.",
        },
        {
            "name": "Products",
            "description": "Scraped product data from source marketplaces.",
        },
        {
            "name": "Listings",
            "description": "Manage eBay listings — view, reprice, and end.",
        },
        {
            "name": "Price History",
            "description": "Historical price tracking and statistics for monitored products.",
        },
        {
            "name": "Discovery",
            "description": "Search for products on Amazon and Walmart by keyword.",
        },
        {
            "name": "Billing",
            "description": "Stripe subscription checkout, portal, and status.",
        },
        {
            "name": "WebSocket",
            "description": "Real-time push notifications via WebSocket (price alerts, listing updates).",
        },
        {
            "name": "System",
            "description": "Health checks and operational endpoints.",
        },
    ]

    app = FastAPI(
        title=settings.app_name,
        description=(
            "KonvertIt converts Amazon and Walmart product listings into optimized "
            "eBay listing drafts. The API provides scraping, compliance checking, "
            "title optimization, profit calculation, and direct eBay publishing.\n\n"
            "**Authentication:** All endpoints (except `/health`) require a JWT Bearer token. "
            "Obtain tokens via `POST /api/v1/auth/register` or `POST /api/v1/auth/login`.\n\n"
            "**Rate Limits:** Conversion endpoints are rate-limited per user tier "
            "(free / pro / enterprise). See `X-RateLimit-*` response headers."
        ),
        version=__version__,
        lifespan=lifespan,
        openapi_tags=openapi_tags,
        contact={
            "name": "E-Clarx LLC",
            "email": "support@konvertit.com",
        },
        license_info={
            "name": "Proprietary",
        },
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        redirect_slashes=False,
    )

    # Middleware order: SecurityHeaders → Logging → GZip → CORS (LIFO — CORS outermost)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_minimum_size)
    # CORS origins: dev uses Vite default, prod reads from CORS_ALLOWED_ORIGINS env var
    if settings.is_development:
        cors_origins = ["http://localhost:5173"]
    elif settings.cors_allowed_origins:
        cors_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    else:
        cors_origins = []

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers (triggers database module import)
    from app.api.v1 import auth, billing, conversions, discovery, listings, price_history, products, users, webhooks, ws
    from app.db.database import get_db

    # Enhanced health check with DB and Redis probes
    @app.get("/health", tags=["System"])
    async def health_check(
        db: AsyncSession = Depends(get_db),
        redis: Redis = Depends(get_redis),
    ):
        from app.core.health import get_health_status

        return await get_health_status(
            app_name=settings.app_name,
            app_version=__version__,
            app_env=settings.app_env.value,
            db_session=db,
            redis_client=redis,
        )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(conversions.router, prefix="/api/v1")
    app.include_router(products.router, prefix="/api/v1")
    app.include_router(listings.router, prefix="/api/v1")
    app.include_router(price_history.router, prefix="/api/v1")
    app.include_router(ws.router, prefix="/api/v1")
    app.include_router(discovery.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")

    # Register global exception handlers (after routers)
    from app.middleware.exception_handler import register_exception_handlers

    register_exception_handlers(app)

    return app


app = create_app()
