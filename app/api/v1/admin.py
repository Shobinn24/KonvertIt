"""
Admin API endpoints.

Provides:
- GET /api/v1/admin/users — List all users with stats
- GET /api/v1/admin/users/:id — Get a single user's details
- GET /api/v1/admin/errors — Recent error logs
- GET /api/v1/admin/stats — System-wide statistics

All endpoints require the X-Admin-Key header matching SECRET_KEY.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.db.models import Conversion, Listing, Product, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ─── Auth: Admin Key Dependency ────────────────────────────


async def require_admin_key(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
) -> None:
    """Validate the admin key from the X-Admin-Key header."""
    settings = get_settings()
    if x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key",
        )


# ─── Response Schemas ───────────────────────────────────────


class AdminUserSummary(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    tier: str
    is_active: bool
    email_verified: bool
    created_at: str | None
    last_login: str | None
    conversion_count: int = 0
    listing_count: int = 0


class AdminUserDetail(AdminUserSummary):
    city: str
    state: str
    country: str
    postal_code: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    recent_errors: list[dict]


class AdminUsersResponse(BaseModel):
    users: list[AdminUserSummary]
    total: int
    page: int
    page_size: int


class AdminErrorEntry(BaseModel):
    id: str
    user_id: str
    user_email: str
    error_message: str
    status: str
    source_url: str
    created_at: str | None


class AdminErrorsResponse(BaseModel):
    errors: list[AdminErrorEntry]
    total: int
    page: int
    page_size: int


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    verified_users: int
    users_by_tier: dict[str, int]
    total_conversions: int
    conversions_today: int
    failed_conversions: int
    total_listings: int
    active_listings: int
    new_users_today: int
    new_users_this_week: int


# ─── Endpoints ──────────────────────────────────────────────


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="System-wide statistics",
    dependencies=[Depends(require_admin_key)],
)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get high-level system statistics for the admin dashboard."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # User counts
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (
        await db.execute(select(func.count(User.id)).where(User.is_active.is_(True)))
    ).scalar_one()
    verified_users = (
        await db.execute(select(func.count(User.id)).where(User.email_verified.is_(True)))
    ).scalar_one()

    # Users by tier
    tier_rows = (
        await db.execute(select(User.tier, func.count(User.id)).group_by(User.tier))
    ).all()
    users_by_tier = {row[0]: row[1] for row in tier_rows}

    # Conversion counts
    total_conversions = (await db.execute(select(func.count(Conversion.id)))).scalar_one()
    conversions_today = (
        await db.execute(
            select(func.count(Conversion.id)).where(Conversion.created_at >= today_start)
        )
    ).scalar_one()
    failed_conversions = (
        await db.execute(
            select(func.count(Conversion.id)).where(Conversion.status == "failed")
        )
    ).scalar_one()

    # Listing counts
    total_listings = (await db.execute(select(func.count(Listing.id)))).scalar_one()
    active_listings = (
        await db.execute(
            select(func.count(Listing.id)).where(Listing.status == "active")
        )
    ).scalar_one()

    # New user counts
    new_users_today = (
        await db.execute(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )
    ).scalar_one()
    new_users_this_week = (
        await db.execute(
            select(func.count(User.id)).where(User.created_at >= week_start)
        )
    ).scalar_one()

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        verified_users=verified_users,
        users_by_tier=users_by_tier,
        total_conversions=total_conversions,
        conversions_today=conversions_today,
        failed_conversions=failed_conversions,
        total_listings=total_listings,
        active_listings=active_listings,
        new_users_today=new_users_today,
        new_users_this_week=new_users_this_week,
    )


@router.get(
    "/users",
    response_model=AdminUsersResponse,
    summary="List all users",
    dependencies=[Depends(require_admin_key)],
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = Query("", description="Search by email or name"),
    tier: str = Query("", description="Filter by tier"),
    db: AsyncSession = Depends(get_db),
):
    """List all users with conversion/listing counts, with search and filter."""
    # Base query
    base = select(User)
    count_base = select(func.count(User.id))

    # Apply filters
    if search:
        search_pattern = f"%{search.lower()}%"
        search_filter = (
            User.email.ilike(search_pattern)
            | User.first_name.ilike(search_pattern)
            | User.last_name.ilike(search_pattern)
        )
        base = base.where(search_filter)
        count_base = count_base.where(search_filter)
    if tier:
        base = base.where(User.tier == tier)
        count_base = count_base.where(User.tier == tier)

    # Total count
    total = (await db.execute(count_base)).scalar_one()

    # Paginated users
    offset = (page - 1) * page_size
    users = (
        await db.execute(
            base.order_by(User.created_at.desc()).limit(page_size).offset(offset)
        )
    ).scalars().all()

    # Get conversion/listing counts per user in batch
    user_ids = [u.id for u in users]

    conversion_counts: dict[uuid.UUID, int] = {}
    listing_counts: dict[uuid.UUID, int] = {}

    if user_ids:
        conv_rows = (
            await db.execute(
                select(Conversion.user_id, func.count(Conversion.id))
                .where(Conversion.user_id.in_(user_ids))
                .group_by(Conversion.user_id)
            )
        ).all()
        conversion_counts = {row[0]: row[1] for row in conv_rows}

        list_rows = (
            await db.execute(
                select(Listing.user_id, func.count(Listing.id))
                .where(Listing.user_id.in_(user_ids))
                .group_by(Listing.user_id)
            )
        ).all()
        listing_counts = {row[0]: row[1] for row in list_rows}

    user_summaries = [
        AdminUserSummary(
            id=str(u.id),
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            tier=u.tier,
            is_active=u.is_active,
            email_verified=u.email_verified,
            created_at=u.created_at.isoformat() if u.created_at else None,
            last_login=u.last_login.isoformat() if u.last_login else None,
            conversion_count=conversion_counts.get(u.id, 0),
            listing_count=listing_counts.get(u.id, 0),
        )
        for u in users
    ]

    return AdminUsersResponse(
        users=user_summaries,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetail,
    summary="Get user details",
    dependencies=[Depends(require_admin_key)],
)
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed info for a single user, including recent errors."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Counts
    conv_count = (
        await db.execute(
            select(func.count(Conversion.id)).where(Conversion.user_id == uid)
        )
    ).scalar_one()
    list_count = (
        await db.execute(
            select(func.count(Listing.id)).where(Listing.user_id == uid)
        )
    ).scalar_one()

    # Recent failed conversions (errors)
    failed = (
        await db.execute(
            select(Conversion)
            .join(Product, Conversion.product_id == Product.id)
            .where(Conversion.user_id == uid, Conversion.status == "failed")
            .order_by(Conversion.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    # Fetch associated products for URLs
    product_ids = [f.product_id for f in failed]
    products_map: dict[uuid.UUID, Product] = {}
    if product_ids:
        products = (
            await db.execute(select(Product).where(Product.id.in_(product_ids)))
        ).scalars().all()
        products_map = {p.id: p for p in products}

    recent_errors = [
        {
            "id": str(c.id),
            "error_message": c.error_message or "Unknown error",
            "status": c.status,
            "source_url": products_map[c.product_id].source_url if c.product_id in products_map else "",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in failed
    ]

    return AdminUserDetail(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        tier=user.tier,
        is_active=user.is_active,
        email_verified=user.email_verified,
        city=user.city,
        state=user.state,
        country=user.country,
        postal_code=user.postal_code,
        stripe_customer_id=user.stripe_customer_id,
        stripe_subscription_id=user.stripe_subscription_id,
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_login=user.last_login.isoformat() if user.last_login else None,
        conversion_count=conv_count,
        listing_count=list_count,
        recent_errors=recent_errors,
    )


@router.get(
    "/errors",
    response_model=AdminErrorsResponse,
    summary="Recent conversion errors",
    dependencies=[Depends(require_admin_key)],
)
async def list_errors(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user_id: str = Query("", description="Filter by user ID"),
    db: AsyncSession = Depends(get_db),
):
    """List failed conversions across all users for troubleshooting."""
    base = (
        select(Conversion, User.email, Product.source_url)
        .join(User, Conversion.user_id == User.id)
        .join(Product, Conversion.product_id == Product.id)
        .where(Conversion.status == "failed")
    )
    count_base = select(func.count(Conversion.id)).where(Conversion.status == "failed")

    if user_id:
        try:
            uid = uuid.UUID(user_id)
            base = base.where(Conversion.user_id == uid)
            count_base = count_base.where(Conversion.user_id == uid)
        except ValueError:
            pass

    total = (await db.execute(count_base)).scalar_one()
    offset = (page - 1) * page_size

    rows = (
        await db.execute(
            base.order_by(Conversion.created_at.desc()).limit(page_size).offset(offset)
        )
    ).all()

    errors = [
        AdminErrorEntry(
            id=str(conv.id),
            user_id=str(conv.user_id),
            user_email=email,
            error_message=conv.error_message or "Unknown error",
            status=conv.status,
            source_url=source_url,
            created_at=conv.created_at.isoformat() if conv.created_at else None,
        )
        for conv, email, source_url in rows
    ]

    return AdminErrorsResponse(
        errors=errors,
        total=total,
        page=page,
        page_size=page_size,
    )
