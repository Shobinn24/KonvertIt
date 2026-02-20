"""
eBay listing management API endpoints.

Provides:
- GET /api/v1/listings — List eBay listings
- GET /api/v1/listings/{id} — Get listing details
- PUT /api/v1/listings/{id}/price — Update listing price
- POST /api/v1/listings/{id}/end — End (delist) a listing

All endpoints require JWT authentication (Bearer token).
"""

import uuid

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.listing_repo import ListingRepository
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/listings", tags=["Listings"])


# ─── Request / Response Schemas ──────────────────────────────


class ListingResponse(BaseModel):
    """Listing detail response."""
    id: str
    ebay_item_id: str | None = None
    title: str
    price: float
    ebay_category_id: str | None = None
    status: str
    listed_at: str | None = None
    last_synced_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UpdatePriceRequest(BaseModel):
    """Update listing price request."""
    price: float = Field(..., gt=0, description="New listing price")


# ─── Endpoints ───────────────────────────────────────────────


@router.get("", summary="List eBay listings")
async def list_listings(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    listing_status: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (draft, active, ended, error)",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """
    List eBay listings for the authenticated user.

    Supports filtering by status (draft, active, ended, error)
    and pagination via limit/offset.

    Requires a valid access token in the Authorization header.
    """
    user_id = uuid.UUID(user["sub"])
    repo = ListingRepository(db)
    listings = await repo.find_by_user(
        user_id=user_id,
        status=listing_status,
        limit=limit,
        offset=offset,
    )

    return {
        "listings": [
            {
                "id": str(lst.id),
                "ebay_item_id": lst.ebay_item_id,
                "title": lst.title,
                "price": lst.price,
                "ebay_category_id": lst.ebay_category_id,
                "status": lst.status,
                "listed_at": lst.listed_at.isoformat() if lst.listed_at else None,
                "last_synced_at": lst.last_synced_at.isoformat() if lst.last_synced_at else None,
                "created_at": lst.created_at.isoformat() if lst.created_at else None,
                "updated_at": lst.updated_at.isoformat() if lst.updated_at else None,
            }
            for lst in listings
        ],
        "total": len(listings),
    }


@router.get("/{listing_id}", summary="Get listing details")
async def get_listing(
    listing_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get listing details by ID.

    Only returns listings belonging to the authenticated user (tenant isolation).

    Requires a valid access token in the Authorization header.
    """
    try:
        lid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing ID format")

    user_id = uuid.UUID(user["sub"])
    repo = ListingRepository(db)
    listing = await repo.get_by_id(lid)

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Tenant isolation
    if listing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Listing not found")

    return ListingResponse(
        id=str(listing.id),
        ebay_item_id=listing.ebay_item_id,
        title=listing.title,
        price=listing.price,
        ebay_category_id=listing.ebay_category_id,
        status=listing.status,
        listed_at=listing.listed_at.isoformat() if listing.listed_at else None,
        last_synced_at=listing.last_synced_at.isoformat() if listing.last_synced_at else None,
        created_at=listing.created_at.isoformat() if listing.created_at else None,
        updated_at=listing.updated_at.isoformat() if listing.updated_at else None,
    )


@router.put("/{listing_id}/price", summary="Update listing price")
async def update_listing_price(
    listing_id: str,
    body: UpdatePriceRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the price of a listing.

    Only updates listings belonging to the authenticated user.

    Requires a valid access token in the Authorization header.
    """
    try:
        lid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing ID format")

    user_id = uuid.UUID(user["sub"])
    repo = ListingRepository(db)
    listing = await repo.get_by_id(lid)

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.price = body.price
    await db.flush()
    await db.commit()

    # Push real-time notification via WebSocket
    try:
        from app.services.ws_manager import WSEvent, WSEventType, get_ws_manager
        ws_mgr = get_ws_manager()
        await ws_mgr.send_to_user(user["sub"], WSEvent(
            event=WSEventType.LISTING_UPDATED,
            data={
                "listing_id": str(listing.id),
                "title": listing.title,
                "action": "price_updated",
                "new_price": listing.price,
            },
        ))
    except Exception:
        pass  # WS is best-effort

    return ListingResponse(
        id=str(listing.id),
        ebay_item_id=listing.ebay_item_id,
        title=listing.title,
        price=listing.price,
        ebay_category_id=listing.ebay_category_id,
        status=listing.status,
        listed_at=listing.listed_at.isoformat() if listing.listed_at else None,
        last_synced_at=listing.last_synced_at.isoformat() if listing.last_synced_at else None,
        created_at=listing.created_at.isoformat() if listing.created_at else None,
        updated_at=listing.updated_at.isoformat() if listing.updated_at else None,
    )


@router.post("/{listing_id}/end", summary="End a listing")
async def end_listing(
    listing_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    End (delist) a listing by setting its status to 'ended'.

    Only ends listings belonging to the authenticated user.
    The listing must be in 'active' or 'draft' status.

    Requires a valid access token in the Authorization header.
    """
    try:
        lid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing ID format")

    user_id = uuid.UUID(user["sub"])
    repo = ListingRepository(db)
    listing = await repo.get_by_id(lid)

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.status not in ("active", "draft"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot end listing with status '{listing.status}'",
        )

    listing.status = "ended"
    await db.flush()
    await db.commit()

    # Push real-time notification via WebSocket
    try:
        from app.services.ws_manager import WSEvent, WSEventType, get_ws_manager
        ws_mgr = get_ws_manager()
        await ws_mgr.send_to_user(user["sub"], WSEvent(
            event=WSEventType.LISTING_UPDATED,
            data={
                "listing_id": str(listing.id),
                "title": listing.title,
                "action": "ended",
            },
        ))
    except Exception:
        pass  # WS is best-effort

    return {
        "id": str(listing.id),
        "status": "ended",
        "message": "Listing ended successfully",
    }
