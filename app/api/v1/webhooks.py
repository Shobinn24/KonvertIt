"""
Webhook endpoints for eBay and Stripe (Phase 4 stub).

Will handle:
- POST /api/v1/webhooks/ebay — eBay notification webhooks
- POST /api/v1/webhooks/stripe — Stripe payment webhooks
"""

from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/ebay")
async def ebay_webhook():
    """Handle eBay notification webhooks."""
    return {"message": "eBay webhooks coming in Phase 4"}


@router.post("/stripe")
async def stripe_webhook():
    """Handle Stripe payment webhooks."""
    return {"message": "Stripe webhooks coming in Phase 5"}
