"""
Unit tests for BillingService — Stripe customer management, checkout, and webhooks.

Uses an async SQLite in-memory database. Mocks the Stripe SDK.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.models import Base
from app.db.repositories.user_repo import UserRepository
from app.services.billing_service import BillingError, BillingService


# ─── Test Settings ───────────────────────────────────────────


def _test_settings() -> Settings:
    return Settings(
        secret_key="test-secret-key-for-unit-tests-only-64-chars-long-padding-here",
        stripe_secret_key="sk_test_fake",
        stripe_webhook_secret="whsec_test_fake",
        stripe_pro_price_id="price_pro_test",
        stripe_enterprise_price_id="price_enterprise_test",
    )


# ─── Database Fixtures ───────────────────────────────────────


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine):
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def user_repo(db_session):
    return UserRepository(db_session)


@pytest.fixture
def settings():
    return _test_settings()


@pytest.fixture
def service(user_repo, settings):
    return BillingService(user_repo=user_repo, settings=settings)


# ─── Helper ──────────────────────────────────────────────────


async def _create_user(user_repo, email="test@example.com", tier="free", **kwargs):
    """Create a test user and return it."""
    return await user_repo.create(
        email=email,
        password_hash="$2b$12$fakehash",
        tier=tier,
        is_active=True,
        **kwargs,
    )


# ─── Customer Management Tests ───────────────────────────────


class TestGetOrCreateCustomer:
    @pytest.mark.asyncio
    @patch("app.services.billing_service.stripe")
    async def test_creates_new_customer(self, mock_stripe, service, user_repo):
        """Should create a Stripe customer and store the ID."""
        user = await _create_user(user_repo)
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_test_123")

        customer_id = await service.get_or_create_customer(user.id, user.email)

        assert customer_id == "cus_test_123"
        mock_stripe.Customer.create.assert_called_once()

        # Verify stored in DB
        updated_user = await user_repo.get_by_id(user.id)
        assert updated_user.stripe_customer_id == "cus_test_123"

    @pytest.mark.asyncio
    @patch("app.services.billing_service.stripe")
    async def test_returns_existing_customer(self, mock_stripe, service, user_repo):
        """Should return existing customer ID without calling Stripe."""
        user = await _create_user(user_repo, stripe_customer_id="cus_existing_456")

        customer_id = await service.get_or_create_customer(user.id, user.email)

        assert customer_id == "cus_existing_456"
        mock_stripe.Customer.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_for_unknown_user(self, service):
        """Should raise BillingError for non-existent user."""
        with pytest.raises(BillingError, match="User not found"):
            await service.get_or_create_customer(uuid.uuid4(), "ghost@example.com")


# ─── Checkout Session Tests ──────────────────────────────────


class TestCreateCheckoutSession:
    @pytest.mark.asyncio
    @patch("app.services.billing_service.stripe")
    async def test_creates_pro_checkout(self, mock_stripe, service, user_repo):
        """Should create a checkout session for pro tier."""
        user = await _create_user(user_repo)
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_new")
        mock_stripe.checkout.Session.create.return_value = MagicMock(
            id="cs_test", url="https://checkout.stripe.com/test"
        )

        url = await service.create_checkout_session(
            user.id, user.email, "pro",
            "https://app.com/success", "https://app.com/cancel",
        )

        assert url == "https://checkout.stripe.com/test"
        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        assert call_kwargs["mode"] == "subscription"
        assert call_kwargs["line_items"][0]["price"] == "price_pro_test"
        assert call_kwargs["metadata"]["tier"] == "pro"

    @pytest.mark.asyncio
    @patch("app.services.billing_service.stripe")
    async def test_creates_enterprise_checkout(self, mock_stripe, service, user_repo):
        """Should create a checkout session for enterprise tier."""
        user = await _create_user(user_repo)
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_new")
        mock_stripe.checkout.Session.create.return_value = MagicMock(
            id="cs_test", url="https://checkout.stripe.com/ent"
        )

        url = await service.create_checkout_session(
            user.id, user.email, "enterprise",
            "https://app.com/success", "https://app.com/cancel",
        )

        assert url == "https://checkout.stripe.com/ent"
        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        assert call_kwargs["line_items"][0]["price"] == "price_enterprise_test"

    @pytest.mark.asyncio
    async def test_rejects_invalid_tier(self, service, user_repo):
        """Should raise BillingError for unknown tier."""
        user = await _create_user(user_repo)
        with pytest.raises(BillingError, match="No Stripe price configured"):
            await service.create_checkout_session(
                user.id, user.email, "platinum",
                "https://x.com/ok", "https://x.com/cancel",
            )


# ─── Portal Session Tests ────────────────────────────────────


class TestCreatePortalSession:
    @pytest.mark.asyncio
    @patch("app.services.billing_service.stripe")
    async def test_creates_portal(self, mock_stripe, service, user_repo):
        """Should create a portal session for users with Stripe customer."""
        user = await _create_user(user_repo, stripe_customer_id="cus_portal")
        mock_stripe.billing_portal.Session.create.return_value = MagicMock(
            url="https://billing.stripe.com/portal"
        )

        url = await service.create_portal_session(user.id, "https://app.com/settings")

        assert url == "https://billing.stripe.com/portal"
        mock_stripe.billing_portal.Session.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_without_customer(self, service, user_repo):
        """Should raise BillingError for users without Stripe customer."""
        user = await _create_user(user_repo)  # No stripe_customer_id

        with pytest.raises(BillingError, match="No Stripe customer found"):
            await service.create_portal_session(user.id, "https://app.com/settings")


# ─── Webhook Handler Tests ───────────────────────────────────


class TestHandleCheckoutCompleted:
    @pytest.mark.asyncio
    async def test_updates_tier_on_checkout(self, service, user_repo):
        """Should update user tier and Stripe IDs on checkout completion."""
        user = await _create_user(user_repo)

        session_data = {
            "metadata": {"konvertit_user_id": str(user.id), "tier": "pro"},
            "subscription": "sub_test_123",
            "customer": "cus_test_456",
        }

        await service.handle_checkout_completed(session_data)

        updated = await user_repo.get_by_id(user.id)
        assert updated.tier == "pro"
        assert updated.stripe_subscription_id == "sub_test_123"
        assert updated.stripe_customer_id == "cus_test_456"
        assert updated.tier_updated_at is not None

    @pytest.mark.asyncio
    async def test_idempotent_checkout(self, service, user_repo):
        """Should skip if subscription ID already matches (idempotent)."""
        user = await _create_user(
            user_repo,
            tier="pro",
            stripe_subscription_id="sub_test_123",
            stripe_customer_id="cus_test_456",
        )

        session_data = {
            "metadata": {"konvertit_user_id": str(user.id), "tier": "pro"},
            "subscription": "sub_test_123",
            "customer": "cus_test_456",
        }

        await service.handle_checkout_completed(session_data)

        updated = await user_repo.get_by_id(user.id)
        assert updated.tier == "pro"  # Unchanged


class TestHandleSubscriptionUpdated:
    @pytest.mark.asyncio
    async def test_upgrades_tier(self, service, user_repo, settings):
        """Should update tier when subscription changes (upgrade)."""
        user = await _create_user(
            user_repo,
            tier="pro",
            stripe_customer_id="cus_upgrade",
            stripe_subscription_id="sub_old",
        )

        subscription_data = {
            "id": "sub_new",
            "customer": "cus_upgrade",
            "items": {
                "data": [
                    {"price": {"id": settings.stripe_enterprise_price_id}},
                ],
            },
        }

        result = await service.handle_subscription_updated(subscription_data)
        old_tier, new_tier, user_id = result

        assert old_tier == "pro"
        assert new_tier == "enterprise"

        updated = await user_repo.get_by_id(user.id)
        assert updated.tier == "enterprise"
        assert updated.tier_updated_at is not None


class TestHandleSubscriptionDeleted:
    @pytest.mark.asyncio
    async def test_downgrades_to_free(self, service, user_repo):
        """Should downgrade user to free on subscription deletion."""
        user = await _create_user(
            user_repo,
            tier="pro",
            stripe_customer_id="cus_cancel",
            stripe_subscription_id="sub_cancel",
        )

        subscription_data = {
            "id": "sub_cancel",
            "customer": "cus_cancel",
        }

        result = await service.handle_subscription_deleted(subscription_data)
        old_tier, new_tier, user_id = result

        assert old_tier == "pro"
        assert new_tier == "free"

        updated = await user_repo.get_by_id(user.id)
        assert updated.tier == "free"
        assert updated.stripe_subscription_id is None
        assert updated.tier_updated_at is not None


# ─── Tier Mapping Tests ──────────────────────────────────────


class TestTierMapping:
    def test_price_id_for_pro(self, service):
        assert service._price_id_for_tier("pro") == "price_pro_test"

    def test_price_id_for_enterprise(self, service):
        assert service._price_id_for_tier("enterprise") == "price_enterprise_test"

    def test_price_id_invalid_raises(self, service):
        with pytest.raises(BillingError):
            service._price_id_for_tier("platinum")

    def test_tier_for_price_id_pro(self, service):
        assert service._tier_for_price_id("price_pro_test") == "pro"

    def test_tier_for_price_id_enterprise(self, service):
        assert service._tier_for_price_id("price_enterprise_test") == "enterprise"

    def test_tier_for_unknown_price_returns_free(self, service):
        assert service._tier_for_price_id("price_unknown") == "free"
