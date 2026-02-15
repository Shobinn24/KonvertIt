"""
Conversion pipeline API endpoints.

Provides:
- POST /api/v1/conversions — Convert a product URL to eBay listing draft
- POST /api/v1/conversions/bulk — Bulk convert multiple URLs (JSON response)
- POST /api/v1/conversions/bulk/stream — Bulk convert with SSE progress streaming
- POST /api/v1/conversions/preview — Preview conversion without listing
- GET /api/v1/conversions — List conversion history
- GET /api/v1/conversions/jobs/{job_id} — Get bulk job status
- POST /api/v1/conversions/jobs/{job_id}/cancel — Cancel a running bulk job

All endpoints require JWT authentication (Bearer token).
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.converters.ebay_converter import EbayConverter
from app.core.exceptions import ConversionError, KonvertItError
from app.db.database import get_db
from app.db.repositories.conversion_repo import ConversionRepository
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limiter import (
    RateLimitInfo,
    add_rate_limit_headers,
    check_bulk_conversion_rate_limit,
    check_conversion_rate_limit,
)
from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager
from app.services.compliance_service import ComplianceService
from app.services.conversion_service import ConversionService
from app.services.profit_engine import ProfitEngine
from app.services.sse_manager import SSEProgressManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversions", tags=["Conversions"])

# Module-level SSE manager — shared across requests.
# In production, this would be injected via FastAPI Depends() or app.state.
_sse_manager = SSEProgressManager()


# ─── Request/Response Schemas ──────────────────────────────


class ConvertRequest(BaseModel):
    """Request body for single URL conversion."""
    url: str = Field(..., description="Source marketplace product URL")
    publish: bool = Field(default=False, description="Whether to publish to eBay")
    sell_price: float | None = Field(default=None, ge=0, description="Override selling price")


class BulkConvertRequest(BaseModel):
    """Request body for bulk URL conversion."""
    urls: list[str] = Field(..., min_length=1, max_length=50, description="Product URLs to convert")
    publish: bool = Field(default=False, description="Whether to publish to eBay")
    sell_price: float | None = Field(default=None, ge=0, description="Override selling price")


class PreviewRequest(BaseModel):
    """Request body for conversion preview."""
    url: str = Field(..., description="Source marketplace product URL")


# ─── Helpers ──────────────────────────────────────────────


@asynccontextmanager
async def _conversion_service_context():
    """Create a ConversionService with a properly started BrowserManager.

    Uses async context manager to ensure BrowserManager is started before
    scraping and cleaned up afterward.
    """
    browser_manager = BrowserManager()
    try:
        await browser_manager.start()
        service = ConversionService(
            proxy_manager=ProxyManager(),
            browser_manager=browser_manager,
            compliance_service=ComplianceService(),
            profit_engine=ProfitEngine(),
            ebay_converter=EbayConverter(),
        )
        yield service
    finally:
        await browser_manager.close()


def get_sse_manager() -> SSEProgressManager:
    """Get the shared SSE progress manager.

    Exposed as a function for testability (can be patched in tests).
    """
    return _sse_manager


# ─── Standard Endpoints ──────────────────────────────────


@router.post("/", summary="Convert a product URL")
async def create_conversion(
    request: ConvertRequest,
    response: Response,
    user: dict = Depends(get_current_user),
    rate_info: RateLimitInfo = Depends(check_conversion_rate_limit),
):
    """
    Convert a product URL to an eBay listing draft.

    Runs the full pipeline: scrape → compliance check → convert → price.
    Optionally publishes to eBay if `publish=true` and eBay is connected.

    Requires a valid access token in the Authorization header.
    Subject to daily conversion rate limits based on user tier.
    """
    add_rate_limit_headers(response, rate_info)
    user_id = user["sub"]

    try:
        async with _conversion_service_context() as service:
            result = await service.convert_url(
                url=request.url,
                user_id=user_id,
                publish=request.publish,
                sell_price=request.sell_price,
            )

            # Push real-time notification via WebSocket
            try:
                from app.services.ws_manager import WSEvent, WSEventType, get_ws_manager
                ws_mgr = get_ws_manager()
                await ws_mgr.send_to_user(user_id, WSEvent(
                    event=WSEventType.CONVERSION_COMPLETE,
                    data={
                        "url": request.url,
                        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
                    },
                ))
            except Exception:
                pass  # WS is best-effort

            return result.to_dict()

    except ConversionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KonvertItError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk", summary="Bulk convert multiple URLs")
async def create_bulk_conversion(
    request: BulkConvertRequest,
    response: Response,
    user: dict = Depends(get_current_user),
    rate_info: RateLimitInfo = Depends(check_bulk_conversion_rate_limit),
):
    """
    Bulk convert multiple product URLs (standard JSON response).

    Processes each URL sequentially through the conversion pipeline.
    Returns progress summary with individual results after all complete.

    For real-time progress streaming, use POST /conversions/bulk/stream instead.

    Requires a valid access token in the Authorization header.
    Subject to daily conversion rate limits (each URL counts as 1 conversion).
    """
    add_rate_limit_headers(response, rate_info)
    user_id = user["sub"]

    try:
        async with _conversion_service_context() as service:
            progress = await service.convert_bulk(
                urls=request.urls,
                user_id=user_id,
                publish=request.publish,
                sell_price=request.sell_price,
            )
            return progress.to_dict()

    except KonvertItError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview", summary="Preview a conversion")
async def preview_conversion(
    request: PreviewRequest,
    response: Response,
    user: dict = Depends(get_current_user),
    rate_info: RateLimitInfo = Depends(check_conversion_rate_limit),
):
    """
    Preview a conversion without publishing.

    Runs: scrape → compliance check → convert → price.
    Does NOT create a listing on eBay.

    Requires a valid access token in the Authorization header.
    Subject to daily conversion rate limits based on user tier.
    """
    add_rate_limit_headers(response, rate_info)
    user_id = user["sub"]

    try:
        async with _conversion_service_context() as service:
            result = await service.preview_conversion(
                url=request.url,
                user_id=user_id,
            )
            return result.to_dict()

    except ConversionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KonvertItError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", summary="List conversion history")
async def list_conversions(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """
    List conversion history for the authenticated user.

    Supports filtering by status (pending, processing, completed, failed)
    and pagination via limit/offset.

    Requires a valid access token in the Authorization header.
    """
    user_id = uuid.UUID(user["sub"])
    repo = ConversionRepository(db)
    conversions = await repo.find_by_user(
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return {
        "conversions": [
            {
                "id": str(c.id),
                "product_id": str(c.product_id),
                "listing_id": str(c.listing_id) if c.listing_id else None,
                "status": c.status,
                "error_message": c.error_message,
                "converted_at": c.converted_at.isoformat() if c.converted_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in conversions
        ],
        "total": len(conversions),
    }


# ─── SSE Streaming Endpoints ─────────────────────────────


@router.post("/bulk/stream", summary="Bulk convert with SSE streaming")
async def create_bulk_conversion_stream(
    request: BulkConvertRequest,
    user: dict = Depends(get_current_user),
    rate_info: RateLimitInfo = Depends(check_bulk_conversion_rate_limit),
):
    """
    Bulk convert multiple product URLs with real-time SSE progress streaming.

    Returns a Server-Sent Events stream with the following event types:

    - **job_started** — Job created with total URL count
    - **item_started** — Individual URL conversion starting
    - **item_step** — Pipeline step changed (scraping, compliance, converting, pricing, listing)
    - **item_completed** — Individual URL finished (success or failure)
    - **job_progress** — Aggregate progress after each item (completed, failed, pending, pct)
    - **job_completed** — Entire job finished with final summary
    - **heartbeat** — Keep-alive ping every 15 seconds
    - **error** — Unexpected error in the stream

    Requires a valid access token in the Authorization header.
    Subject to daily conversion rate limits (each URL counts as 1 conversion).
    """
    user_id = user["sub"]
    manager = get_sse_manager()
    job_id = manager.create_job(request.urls)

    async def _run_conversion(jid: str) -> None:
        """Background task that runs the bulk conversion and emits SSE events."""
        try:
            browser_manager = BrowserManager()
            await browser_manager.start()
            service = ConversionService(
                proxy_manager=ProxyManager(),
                browser_manager=browser_manager,
                compliance_service=ComplianceService(),
                profit_engine=ProfitEngine(),
                ebay_converter=EbayConverter(),
            )
            job = manager.get_job(jid)

            await manager.emit_job_started(jid)

            # Build SSE callbacks for ConversionService
            async def on_step(url: str, step: str) -> None:
                """Emit item_step events as the pipeline progresses."""
                # Find the current item index from the URL
                try:
                    idx = job.urls.index(url)
                except ValueError:
                    idx = -1
                await manager.emit_item_step(jid, idx, url, step)

            async def on_item_complete(
                index: int,
                url: str,
                success: bool,
                result_data: dict | None,
                error: str,
            ) -> None:
                """Emit item_completed + job_progress events."""
                await manager.emit_item_completed(
                    jid, index, url, success, result_data, error
                )

            def cancel_check() -> bool:
                """Check if the job has been cancelled."""
                j = manager.get_job(jid)
                return j.is_cancelled if j else True

            # Emit item_started before each URL
            # We do this by wrapping convert_bulk with pre-item notifications
            original_convert = service.convert_url

            async def convert_with_notification(
                url, user_id, publish=False, sell_price=None, on_step=None
            ):
                idx = job.urls.index(url) if url in job.urls else -1
                await manager.emit_item_started(jid, idx, url)
                return await original_convert(
                    url=url,
                    user_id=user_id,
                    publish=publish,
                    sell_price=sell_price,
                    on_step=on_step,
                )

            service.convert_url = convert_with_notification

            await service.convert_bulk(
                urls=request.urls,
                user_id=user_id,
                publish=request.publish,
                sell_price=request.sell_price,
                on_step=on_step,
                on_item_complete=on_item_complete,
                cancel_check=cancel_check,
            )

            await manager.emit_job_completed(jid)

        except Exception as e:
            logger.error(f"[SSE] Bulk conversion error for job {jid}: {e}", exc_info=True)
            await manager.emit_error(jid, f"{type(e).__name__}: {e}")
        finally:
            await browser_manager.close()

    async def event_generator():
        """Async generator that yields SSE events while conversion runs."""
        # Start the conversion in a background task
        task = asyncio.create_task(_run_conversion(job_id))

        try:
            async for event_str in manager.subscribe(job_id):
                yield event_str
        finally:
            # Ensure the task completes even if client disconnects
            if not task.done():
                manager.cancel_job(job_id)
                # Give the task a moment to finish gracefully
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    task.cancel()
            # Cleanup job from memory
            manager.cleanup_job(job_id)

    sse_headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
        "X-Job-ID": job_id,
    }
    add_rate_limit_headers(sse_headers, rate_info)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=sse_headers,
    )


@router.get("/jobs/{job_id}", summary="Get bulk job status")
async def get_job_status(
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Get the current status of a bulk conversion job.

    Returns the job's progress state including completed, failed, and pending counts.

    Requires a valid access token in the Authorization header.
    """
    manager = get_sse_manager()
    job = manager.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found (may have been cleaned up)",
        )

    return job.to_dict()


@router.post("/jobs/{job_id}/cancel", summary="Cancel a bulk job")
async def cancel_job(
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Cancel a running bulk conversion job.

    The job will stop processing new URLs after the current item finishes.
    Already-completed items are not affected.

    Requires a valid access token in the Authorization header.
    """
    manager = get_sse_manager()
    cancelled = manager.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found or already completed",
        )

    return {
        "job_id": job_id,
        "status": "cancelling",
        "message": "Job will stop after current item completes",
    }
