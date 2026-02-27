"""
Stripe billing service — manages customers, checkout sessions, and subscriptions.

Encapsulates all Stripe SDK interactions so the API layer stays thin.
"""

import logging
import uuid

import stripe

from app.config import Settings, get_settings
from app.db.models import utc_now
from app.db.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

# Tier ↔ Stripe price mapping (built dynamically from settings)
TIER_TO_LABEL = {"pro": "Hustler", "enterprise": "Enterprise"}


class BillingError(Exception):
    """Billing operation failed."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class BillingService:
    """Manages Stripe customer creation, checkout sessions, and portal sessions."""

    def __init__(
        self,
        user_repo: UserRepository,
        settings: Settings | None = None,
    ):
        self._repo = user_repo
        self._settings = settings or get_settings()

    def _price_id_for_tier(self, tier: str) -> str:
        """Map a tier name to the corresponding Stripe price ID."""
        mapping = {
            "pro": self._settings.stripe_pro_price_id,
            "enterprise": self._settings.stripe_enterprise_price_id,
        }
        price_id = mapping.get(tier)
        if not price_id:
            raise BillingError(f"No Stripe price configured for tier '{tier}'")
        return price_id

    def _tier_for_price_id(self, price_id: str) -> str:
        """Map a Stripe price ID back to a tier name."""
        mapping = {
            self._settings.stripe_pro_price_id: "pro",
            self._settings.stripe_enterprise_price_id: "enterprise",
        }
        return mapping.get(price_id, "free")

    # ─── Customer Management ──────────────────────────────────

    async def get_or_create_customer(
        self,
        user_id: uuid.UUID,
        email: str,
    ) -> str:
        """
        Get existing Stripe customer ID or create a new one.

        Stores stripe_customer_id on the User record for future lookups.
        Returns the Stripe customer ID string.
        """
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise BillingError("User not found")

        if user.stripe_customer_id:
            return user.stripe_customer_id

        # Create Stripe customer
        customer = stripe.Customer.create(
            email=email,
            metadata={"konvertit_user_id": str(user_id)},
        )

        await self._repo.update(user_id, stripe_customer_id=customer.id)
        logger.info(f"Created Stripe customer {customer.id} for user {user_id}")

        return customer.id

    # ─── Checkout Session ─────────────────────────────────────

    async def create_checkout_session(
        self,
        user_id: uuid.UUID,
        email: str,
        tier: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """
        Create a Stripe Checkout Session and return its URL.

        Args:
            user_id: KonvertIt user UUID.
            email: User email (for Stripe customer).
            tier: "pro" or "enterprise".
            success_url: Frontend URL to redirect after successful payment.
            cancel_url: Frontend URL to redirect if user cancels.

        Returns:
            The Stripe-hosted checkout URL.
        """
        price_id = self._price_id_for_tier(tier)
        customer_id = await self.get_or_create_customer(user_id, email)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "konvertit_user_id": str(user_id),
                "tier": tier,
            },
        )

        logger.info(f"Created checkout session {session.id} for user {user_id} ({tier})")
        return session.url

    # ─── Customer Portal ──────────────────────────────────────

    async def create_portal_session(
        self,
        user_id: uuid.UUID,
        return_url: str,
    ) -> str:
        """
        Create a Stripe Customer Portal session and return its URL.

        Allows users to manage their subscription (upgrade, downgrade, cancel).
        """
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise BillingError("User not found")

        if not user.stripe_customer_id:
            raise BillingError("No Stripe customer found — subscribe first")

        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=return_url,
        )

        return session.url

    # ─── Subscription Status ──────────────────────────────────

    async def get_subscription_status(self, user_id: uuid.UUID) -> dict:
        """
        Retrieve the current subscription status.

        Returns:
            Dict with tier, status, current_period_end, cancel_at_period_end.
        """
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise BillingError("User not found")

        # No subscription — free tier
        if not user.stripe_subscription_id:
            return {
                "tier": user.tier,
                "status": "none" if user.tier == "free" else "active",
                "current_period_end": None,
                "cancel_at_period_end": False,
            }

        try:
            subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
            return {
                "tier": user.tier,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }
        except stripe.error.InvalidRequestError:
            # Subscription no longer exists in Stripe
            logger.warning(
                f"Stripe subscription {user.stripe_subscription_id} not found for user {user_id}"
            )
            return {
                "tier": user.tier,
                "status": "canceled",
                "current_period_end": None,
                "cancel_at_period_end": False,
            }
        except stripe.error.StripeError as e:
            # Any other Stripe SDK error (auth, connection, rate-limit, etc.)
            logger.error(
                f"Stripe error retrieving subscription {user.stripe_subscription_id}: {e}"
            )
            raise BillingError(f"Stripe API error: {e}")

    # ─── Webhook Handlers ─────────────────────────────────────

    async def handle_checkout_completed(self, session_data: dict) -> None:
        """Handle checkout.session.completed webhook event."""
        user_id_str = session_data.get("metadata", {}).get("konvertit_user_id")
        if not user_id_str:
            logger.warning("Checkout session missing konvertit_user_id metadata")
            return

        user_id = uuid.UUID(user_id_str)
        user = await self._repo.get_by_id(user_id)
        if user is None:
            logger.warning(f"Checkout completed for unknown user {user_id}")
            return

        subscription_id = session_data.get("subscription")
        customer_id = session_data.get("customer")

        # Idempotency: skip if subscription already set
        if user.stripe_subscription_id == subscription_id:
            return

        # Determine tier from subscription
        tier = session_data.get("metadata", {}).get("tier", "pro")

        await self._repo.update(
            user_id,
            tier=tier,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            tier_updated_at=utc_now(),
        )

        logger.info(f"Checkout completed: user {user_id} → {tier}")

    async def handle_subscription_updated(
        self, subscription_data: dict
    ) -> tuple[str, str, str] | None:
        """Handle customer.subscription.updated webhook event.

        Returns:
            Tuple of (old_tier, new_tier, user_id) if processed, None otherwise.
        """
        customer_id = subscription_data.get("customer")
        if not customer_id:
            return None

        user = await self._repo.find_by_stripe_customer_id(customer_id)
        if user is None:
            logger.warning("Subscription updated for unknown Stripe customer")
            return None

        # Determine new tier from the subscription's price
        items = subscription_data.get("items", {}).get("data", [])
        new_tier = "free"
        for item in items:
            price_id = item.get("price", {}).get("id", "")
            tier = self._tier_for_price_id(price_id)
            if tier != "free":
                new_tier = tier
                break

        old_tier = user.tier
        if new_tier != old_tier:
            await self._repo.update(
                user.id,
                tier=new_tier,
                stripe_subscription_id=subscription_data.get("id"),
                tier_updated_at=utc_now(),
            )
            logger.info(f"Subscription updated: user {user.id} {old_tier} → {new_tier}")

        return old_tier, new_tier, str(user.id)

    async def handle_subscription_deleted(
        self, subscription_data: dict
    ) -> tuple[str, str, str] | None:
        """Handle customer.subscription.deleted webhook event.

        Returns:
            Tuple of (old_tier, new_tier, user_id) if processed, None otherwise.
        """
        customer_id = subscription_data.get("customer")
        if not customer_id:
            return None

        user = await self._repo.find_by_stripe_customer_id(customer_id)
        if user is None:
            logger.warning("Subscription deleted for unknown Stripe customer")
            return None

        old_tier = user.tier
        await self._repo.update(
            user.id,
            tier="free",
            stripe_subscription_id=None,
            tier_updated_at=utc_now(),
        )

        logger.info(f"Subscription deleted: user {user.id} {old_tier} → free")
        return old_tier, "free", str(user.id)

    async def handle_payment_failed(self, invoice_data: dict) -> None:
        """Handle invoice.payment_failed webhook event (log only, no downgrade)."""
        customer_id = invoice_data.get("customer")
        invoice_id = invoice_data.get("id")
        logger.warning(f"Payment failed for Stripe customer (invoice: {invoice_id})")
