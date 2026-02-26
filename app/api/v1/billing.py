"""
Billing API endpoints — Stripe Checkout, Customer Portal, and subscription status.

Provides:
- POST /api/v1/billing/checkout — Create Stripe Checkout Session
- POST /api/v1/billing/portal — Create Stripe Customer Portal session
- GET /api/v1/billing/subscription — Get current subscription status
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.user_repo import UserRepository
from app.middleware.auth_middleware import get_current_user
from app.services.billing_service import BillingError, BillingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


# ─── Request / Response Schemas ──────────────────────────────


class CheckoutRequest(BaseModel):
    """Checkout session request."""
    tier: str = Field(..., pattern="^(pro|enterprise)$")
    success_url: str = Field(..., min_length=1)
    cancel_url: str = Field(..., min_length=1)


class CheckoutResponse(BaseModel):
    """Checkout session response."""
    checkout_url: str


class PortalRequest(BaseModel):
    """Customer portal request."""
    return_url: str = Field(..., min_length=1)


class PortalResponse(BaseModel):
    """Customer portal response."""
    portal_url: str


class SubscriptionResponse(BaseModel):
    """Current subscription status."""
    tier: str
    status: str
    current_period_end: int | None = None
    cancel_at_period_end: bool = False


# ─── Helper ──────────────────────────────────────────────────


def _build_billing_service(db: AsyncSession) -> BillingService:
    """Create a BillingService instance from a DB session."""
    return BillingService(user_repo=UserRepository(db))


# ─── Endpoints ───────────────────────────────────────────────


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Create Stripe Checkout Session",
)
async def create_checkout(
    body: CheckoutRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout Session for the requested plan.

    The frontend should redirect the user to the returned URL.
    After payment, Stripe redirects to the success_url.
    """
    service = _build_billing_service(db)

    try:
        checkout_url = await service.create_checkout_session(
            user_id=uuid.UUID(user["sub"]),
            email=user.get("email", ""),
            tier=body.tier,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
        return CheckoutResponse(checkout_url=checkout_url)
    except BillingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except Exception as e:
        logger.error(f"Checkout session creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create checkout session: {e}",
        )


@router.post(
    "/portal",
    response_model=PortalResponse,
    summary="Create Stripe Customer Portal session",
)
async def create_portal(
    body: PortalRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Customer Portal session for subscription management.

    The user can upgrade, downgrade, cancel, or update payment methods.
    """
    service = _build_billing_service(db)

    try:
        portal_url = await service.create_portal_session(
            user_id=uuid.UUID(user["sub"]),
            return_url=body.return_url,
        )
        return PortalResponse(portal_url=portal_url)
    except BillingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except Exception as e:
        logger.error(f"Portal session creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create portal session",
        )


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Get current subscription status",
)
async def get_subscription(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current user's subscription status.

    Returns tier, status, period end date, and cancellation state.
    """
    service = _build_billing_service(db)

    try:
        result = await service.get_subscription_status(
            user_id=uuid.UUID(user["sub"]),
        )
        return SubscriptionResponse(**result)
    except BillingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
