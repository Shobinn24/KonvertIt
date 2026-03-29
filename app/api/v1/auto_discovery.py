"""
Auto-discovery API endpoints.

Provides:
- GET  /api/v1/auto-discover/config  — Get user's auto-discovery configuration
- PUT  /api/v1/auto-discover/config  — Create or update auto-discovery configuration
- POST /api/v1/auto-discover/run     — Trigger a manual auto-discovery run
- GET  /api/v1/auto-discover/history — Get past auto-discovery run results

All endpoints require JWT authentication (Bearer token).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.auto_discovery_repo import AutoDiscoveryRepository
from app.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-discover", tags=["Auto-Discovery"])


# ─── Request / Response Models ───────────────────────────────


class AutoDiscoveryConfigUpdate(BaseModel):
    """Fields that can be updated on a user's auto-discovery config."""

    enabled: bool | None = None
    auto_publish: bool | None = None
    min_margin_pct: float | None = Field(None, ge=0.05, le=0.80)
    max_daily_items: int | None = Field(None, ge=1, le=50)
    marketplaces: list[str] | None = None


class AutoDiscoveryConfigResponse(BaseModel):
    """Auto-discovery configuration returned to the client."""

    enabled: bool
    auto_publish: bool
    min_margin_pct: float
    max_daily_items: int
    marketplaces: list[str]
    last_run_at: str | None = None
    items_found_today: int = 0


class AutoDiscoveryRunResponse(BaseModel):
    """A single auto-discovery run record."""

    id: str
    data_source: str
    queries_searched: list[str]
    products_evaluated: int
    products_converted: int
    products_skipped_duplicate: int
    products_skipped_compliance: int
    products_skipped_margin: int
    errors: int
    run_at: str


class AutoDiscoveryHistoryResponse(BaseModel):
    """Paginated list of auto-discovery run records."""

    runs: list[AutoDiscoveryRunResponse]
    total: int


class AutoDiscoveryRunTriggerResponse(BaseModel):
    """Response after triggering a manual auto-discovery run."""

    status: str
    products_evaluated: int = 0
    products_converted: int = 0
    errors: int = 0


# ─── Endpoints ───────────────────────────────────────────────


@router.get(
    "/config",
    summary="Get auto-discovery config",
    response_model=AutoDiscoveryConfigResponse,
)
async def get_config(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the current user's auto-discovery configuration.

    If no configuration exists yet, returns defaults.
    """
    user_id = uuid.UUID(user["sub"])
    repo = AutoDiscoveryRepository(db)
    config = await repo.get_config(user_id)

    if config is None:
        return {
            "enabled": False,
            "auto_publish": False,
            "min_margin_pct": 0.20,
            "max_daily_items": 10,
            "marketplaces": ["amazon"],
            "last_run_at": None,
            "items_found_today": 0,
        }

    return {
        "enabled": config.enabled,
        "auto_publish": config.auto_publish,
        "min_margin_pct": config.min_margin_pct,
        "max_daily_items": config.max_daily_items,
        "marketplaces": config.marketplaces,
        "last_run_at": config.last_run_at.isoformat() if config.last_run_at else None,
        "items_found_today": config.items_found_today,
    }


@router.put(
    "/config",
    summary="Update auto-discovery config",
    response_model=AutoDiscoveryConfigResponse,
)
async def update_config(
    body: AutoDiscoveryConfigUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or update the user's auto-discovery configuration.

    Only fields included in the request body are changed; omitted fields
    keep their current (or default) values.
    """
    user_id = uuid.UUID(user["sub"])
    repo = AutoDiscoveryRepository(db)

    # Filter out None values so we only update provided fields
    updates = {k: v for k, v in body.model_dump().items() if v is not None}

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    config = await repo.upsert_config(user_id, **updates)
    await db.commit()

    return {
        "enabled": config.enabled,
        "auto_publish": config.auto_publish,
        "min_margin_pct": config.min_margin_pct,
        "max_daily_items": config.max_daily_items,
        "marketplaces": config.marketplaces,
        "last_run_at": config.last_run_at.isoformat() if config.last_run_at else None,
        "items_found_today": config.items_found_today,
    }


@router.post(
    "/run",
    summary="Trigger manual auto-discovery run",
    response_model=AutoDiscoveryRunTriggerResponse,
)
async def trigger_run(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger an auto-discovery run for the current user.

    Useful for testing configuration before enabling scheduled runs.
    Uses the user's saved config (or defaults if none exists).
    """
    from app.scrapers.browser_manager import BrowserManager
    from app.scrapers.proxy_manager import ProxyManager
    from app.services.auto_discovery_service import AutoDiscoveryService

    user_id = uuid.UUID(user["sub"])
    repo = AutoDiscoveryRepository(db)

    config = await repo.get_config(user_id)
    if config is None:
        # Create a default config so the run has something to work with
        config = await repo.upsert_config(user_id)
        await db.commit()

    try:
        proxy_manager = ProxyManager()
        browser_manager = BrowserManager()
        await browser_manager.start()

        try:
            service = AutoDiscoveryService(
                session=db,
                proxy_manager=proxy_manager,
                browser_manager=browser_manager,
            )
            result = await service.run_for_user(user_id)
            await db.commit()

            return {
                "status": "completed",
                "products_evaluated": result.get("products_evaluated", 0),
                "products_converted": result.get("products_converted", 0),
                "errors": result.get("errors", 0),
            }
        finally:
            await browser_manager.stop()

    except Exception as e:
        logger.error(
            "Auto-discovery manual run failed for user %s: %s",
            user_id, e, exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Auto-discovery run failed: {type(e).__name__}",
        ) from e


@router.get(
    "/history",
    summary="Get auto-discovery run history",
    response_model=AutoDiscoveryHistoryResponse,
)
async def get_history(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
) -> dict:
    """Return past auto-discovery run records for the current user.

    Results are ordered newest-first and support pagination via the
    ``limit`` query parameter (max 100).
    """
    user_id = uuid.UUID(user["sub"])
    repo = AutoDiscoveryRepository(db)
    runs = await repo.get_runs(user_id, limit=limit)

    return {
        "runs": [
            {
                "id": str(run.id),
                "data_source": run.data_source,
                "queries_searched": run.queries_searched or [],
                "products_evaluated": run.products_evaluated,
                "products_converted": run.products_converted,
                "products_skipped_duplicate": run.products_skipped_duplicate,
                "products_skipped_compliance": run.products_skipped_compliance,
                "products_skipped_margin": run.products_skipped_margin,
                "errors": run.errors,
                "run_at": run.run_at.isoformat(),
            }
            for run in runs
        ],
        "total": len(runs),
    }
