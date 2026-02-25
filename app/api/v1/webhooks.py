"""
Webhook endpoints for eBay and Stripe.

Handles:
- POST /api/v1/webhooks/ebay — eBay notification webhooks (stub)
- POST /api/v1/webhooks/stripe — Stripe payment webhooks

Security:
- Stripe webhook signature verified before any processing
- Event IDs tracked in-memory for idempotency (replay protection)
- No payload or token data is logged
"""

import logging
from collections import OrderedDict

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.db.repositories.user_repo import UserRepository
from app.services.billing_service import BillingService
from app.services.ws_manager import WSEvent, WSEventType, get_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# In-memory idempotency cache for processed Stripe event IDs.
# Uses OrderedDict as an LRU — evicts oldest entries beyond _MAX_SEEN.
_MAX_SEEN_EVENTS = 10_000
_seen_event_ids: OrderedDict[str, None] = OrderedDict()

HANDLED_STRIPE_EVENTS = frozenset({
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
})


def _mark_event_seen(event_id: str) -> bool:
    """Record an event ID. Returns True if already seen (duplicate)."""
    if event_id in _seen_event_ids:
        _seen_event_ids.move_to_end(event_id)
        return True
    _seen_event_ids[event_id] = None
    while len(_seen_event_ids) > _MAX_SEEN_EVENTS:
        _seen_event_ids.popitem(last=False)
    return False


@router.post("/ebay")
async def ebay_webhook():
    """Handle eBay notification webhooks."""
    return {"message": "eBay webhooks coming soon"}


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Stripe payment webhooks.

    Verifies the webhook signature and routes events to the appropriate handler.
    Duplicate events (same event ID) are acknowledged but not re-processed.

    Supported events:
    - checkout.session.completed
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_failed
    """
    settings = get_settings()

    # Read raw body for signature verification
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature") or request.headers.get("stripe-signature", "")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("Stripe webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        )

    # Idempotency: skip duplicate events
    event_id = event.get("id", "")
    if _mark_event_seen(event_id):
        logger.info(f"Skipping duplicate Stripe event {event_id}")
        return {"received": True}

    # Route event to handler
    event_type = event["type"]
    event_data = event["data"]["object"]

    if event_type not in HANDLED_STRIPE_EVENTS:
        logger.debug(f"Ignoring unhandled Stripe event type: {event_type}")
        return {"received": True}

    service = BillingService(user_repo=UserRepository(db))
    ws_mgr = get_ws_manager()

    if event_type == "checkout.session.completed":
        await service.handle_checkout_completed(event_data)

        # Send WS notification for tier change
        user_id = event_data.get("metadata", {}).get("konvertit_user_id")
        new_tier = event_data.get("metadata", {}).get("tier", "pro")
        if user_id:
            await ws_mgr.send_to_user(
                user_id,
                WSEvent(
                    event=WSEventType.TIER_CHANGED,
                    data={"new_tier": new_tier, "old_tier": "free"},
                ),
            )

    elif event_type == "customer.subscription.updated":
        result = await service.handle_subscription_updated(event_data)
        if result:
            old_tier, new_tier, user_id = result
            if old_tier != new_tier:
                await ws_mgr.send_to_user(
                    user_id,
                    WSEvent(
                        event=WSEventType.TIER_CHANGED,
                        data={"new_tier": new_tier, "old_tier": old_tier},
                    ),
                )

    elif event_type == "customer.subscription.deleted":
        result = await service.handle_subscription_deleted(event_data)
        if result:
            old_tier, new_tier, user_id = result
            await ws_mgr.send_to_user(
                user_id,
                WSEvent(
                    event=WSEventType.TIER_CHANGED,
                    data={"new_tier": "free", "old_tier": old_tier},
                ),
            )

    elif event_type == "invoice.payment_failed":
        await service.handle_payment_failed(event_data)

    logger.info(f"Processed Stripe event {event_id} ({event_type})")
    return {"received": True}
