"""
User management API endpoints.

Provides:
- GET /api/v1/users/me — Current user profile
- PUT /api/v1/users/me — Update profile (email, password)
- GET /api/v1/users/me/usage — Usage stats and tier limits
- PUT /api/v1/users/admin/set-tier — Admin: set a user's tier (requires secret key)
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.db.repositories.conversion_repo import ConversionRepository
from app.db.repositories.listing_repo import ListingRepository
from app.db.repositories.user_repo import UserRepository
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limiter import TIER_RATE_LIMITS
from app.services.user_service import RegistrationError, UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


# ─── Request / Response Schemas ──────────────────────────────


class UserProfileResponse(BaseModel):
    """User profile response."""
    id: str
    email: str
    tier: str
    is_active: bool
    created_at: str | None = None
    last_login: str | None = None


class UpdateProfileRequest(BaseModel):
    """Update profile request — all fields optional."""
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UsageStatsResponse(BaseModel):
    """User usage statistics and tier limits."""
    tier: str
    conversions: dict
    listings: dict
    limits: dict


class SetTierRequest(BaseModel):
    """Admin request to set a user's tier."""
    email: EmailStr
    tier: str = Field(..., pattern="^(free|pro|enterprise)$")


# ─── Endpoints ───────────────────────────────────────────────


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
)
async def get_profile(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the authenticated user's profile information.

    Requires a valid access token in the Authorization header.
    """
    user_repo = UserRepository(db)
    db_user = await user_repo.find_by_email(user["email"])

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserProfileResponse(
        id=str(db_user.id),
        email=db_user.email,
        tier=db_user.tier,
        is_active=db_user.is_active,
        created_at=db_user.created_at.isoformat() if db_user.created_at else None,
        last_login=db_user.last_login.isoformat() if db_user.last_login else None,
    )


@router.put(
    "/me",
    response_model=UserProfileResponse,
    summary="Update current user profile",
)
async def update_profile(
    body: UpdateProfileRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the authenticated user's profile.

    Supports changing email and/or password.
    At least one field must be provided.
    """
    service = UserService(user_repo=UserRepository(db))

    try:
        updated = await service.update_profile(
            user_id=user["sub"],
            email=body.email,
            password=body.password,
        )
    except RegistrationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserProfileResponse(
        id=str(updated.id),
        email=updated.email,
        tier=updated.tier,
        is_active=updated.is_active,
        created_at=updated.created_at.isoformat() if updated.created_at else None,
        last_login=updated.last_login.isoformat() if updated.last_login else None,
    )


@router.get(
    "/me/usage",
    response_model=UsageStatsResponse,
    summary="Get usage stats and tier limits",
)
async def get_usage_stats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the authenticated user's usage statistics and tier limits.

    Returns conversion counts by status, listing counts by status,
    and the user's tier-based limits.
    """
    import uuid

    user_id = uuid.UUID(user["sub"])
    tier = user.get("tier", "free")

    conversion_repo = ConversionRepository(db)
    listing_repo = ListingRepository(db)

    conversion_counts = await conversion_repo.count_by_status(user_id)
    listing_counts = await listing_repo.count_by_status(user_id)

    limits = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS["free"])

    return UsageStatsResponse(
        tier=tier,
        conversions=conversion_counts,
        listings=listing_counts,
        limits=limits,
    )


# ─── Admin Endpoints ────────────────────────────────────────


@router.put(
    "/admin/set-tier",
    response_model=UserProfileResponse,
    summary="Admin: set a user's subscription tier",
)
async def admin_set_tier(
    body: SetTierRequest,
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Set a user's subscription tier (free, pro, enterprise).

    Requires the application secret key in the X-Admin-Key header.
    This is an admin-only endpoint — not exposed in the frontend.
    """
    settings = get_settings()
    if x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key",
        )

    user_repo = UserRepository(db)
    db_user = await user_repo.find_by_email(body.email)

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{body.email}' not found",
        )

    updated = await user_repo.update(db_user.id, tier=body.tier)

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tier",
        )

    logger.info(f"Admin set tier for {body.email}: {body.tier}")

    return UserProfileResponse(
        id=str(updated.id),
        email=updated.email,
        tier=updated.tier,
        is_active=updated.is_active,
        created_at=updated.created_at.isoformat() if updated.created_at else None,
        last_login=updated.last_login.isoformat() if updated.last_login else None,
    )
