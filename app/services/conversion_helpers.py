"""
Shared conversion helpers used by both the conversions API and the
auto-discovery service.

Extracts eBay lister construction, result persistence, and the
ConversionService context manager so they can be reused without
importing from the API layer.
"""

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.converters.ebay_converter import EbayConverter
from app.core.encryption import decrypt, encrypt
from app.core.exceptions import DuplicateListingError
from app.db.mappers import conversion_from_result, listing_from_draft, product_from_scraped
from app.db.repositories.conversion_repo import ConversionRepository
from app.db.repositories.ebay_credential_repo import EbayCredentialRepository
from app.db.repositories.listing_repo import ListingRepository
from app.db.repositories.product_repo import ProductRepository
from app.listers.ebay_auth import EbayAuth
from app.listers.ebay_lister import EbayLister
from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager
from app.services.compliance_service import ComplianceService
from app.services.conversion_service import ConversionResult, ConversionService
from app.services.profit_engine import ProfitEngine

logger = logging.getLogger(__name__)


async def get_ebay_lister_for_user(
    user_id: str, db: AsyncSession
) -> EbayLister | None:
    """Build an EbayLister from a user's stored eBay credentials.

    Refreshes the access token automatically if it is expired or missing.
    Returns None if the user has no eBay credentials.
    """
    try:
        repo = EbayCredentialRepository(db)
        creds = await repo.get_by_user_id(uuid.UUID(user_id))
        if not creds:
            return None

        cred = creds[0]
        settings = get_settings()
        access_token = decrypt(cred.access_token)

        needs_refresh = (
            cred.token_expiry is None
            or datetime.now(UTC) >= cred.token_expiry - timedelta(minutes=5)
        )

        if needs_refresh:
            try:
                ebay_auth = EbayAuth()
                refresh_token = decrypt(cred.refresh_token)
                new_tokens = await ebay_auth.refresh_token(refresh_token)

                access_token = new_tokens.get("access_token", "")
                expires_in = new_tokens.get("expires_in", 7200)
                new_expiry = datetime.now(UTC) + timedelta(seconds=int(expires_in))

                await repo.update_tokens(
                    credential_id=cred.id,
                    access_token=encrypt(access_token),
                    refresh_token=cred.refresh_token,
                    token_expiry=new_expiry,
                )
                await db.commit()
                logger.info(
                    "eBay token refreshed for user %s, expires in %ss",
                    user_id, expires_in,
                )
            except Exception as refresh_err:
                logger.error(
                    "Failed to refresh eBay token for user %s: %s",
                    user_id, refresh_err,
                )

        return EbayLister(
            access_token=access_token,
            base_url=settings.ebay_base_url,
            fulfillment_policy_id=settings.ebay_fulfillment_policy_id,
            payment_policy_id=settings.ebay_payment_policy_id,
            return_policy_id=settings.ebay_return_policy_id,
            default_category_id=settings.ebay_default_category_id,
        )
    except Exception as e:
        logger.warning("Failed to build EbayLister for user %s: %s", user_id, e)
        return None


async def persist_conversion_result(
    result: ConversionResult,
    user_id: str,
    db: AsyncSession,
) -> None:
    """Persist Product, Listing, and Conversion records from a pipeline result.

    Shared between the conversions API endpoint and the auto-discovery service
    so both code paths produce identical DB records.
    """
    if not result.product:
        return

    try:
        uid = uuid.UUID(user_id)

        # 1. Find or create Product
        product_repo = ProductRepository(db)
        product_orm = await product_repo.find_by_source_id(
            user_id=uid,
            source_marketplace=result.product.source_marketplace.value,
            source_product_id=result.product.source_product_id,
        )
        if not product_orm:
            product_orm = product_from_scraped(result.product, uid)
            db.add(product_orm)
            await db.flush()

        # 2. Duplicate check
        listing_repo = ListingRepository(db)
        existing_listing = await listing_repo.has_active_listing_for_product(
            user_id=uid,
            product_id=product_orm.id,
        )
        if existing_listing:
            raise DuplicateListingError(
                product_title=product_orm.title,
                ebay_item_id=existing_listing.ebay_item_id,
                listing_id=str(existing_listing.id),
            )

        # 3. Save Listing if draft and listing result exist
        listing_orm = None
        if result.draft and result.listing:
            listing_orm = listing_from_draft(result.draft, uid, result.listing)
            listing_orm.product_id = product_orm.id
            db.add(listing_orm)
            await db.flush()

        # 4. Save Conversion record
        status = result.status.value
        conversion_orm = conversion_from_result(
            user_id=uid,
            product_id=product_orm.id,
            status=status,
            listing_id=listing_orm.id if listing_orm else None,
            error_message=result.error or None,
        )
        db.add(conversion_orm)
        await db.commit()
        logger.info("Persisted conversion for %s (status=%s)", result.url, status)

    except DuplicateListingError:
        try:
            await db.rollback()
        except Exception:
            pass
        raise
    except Exception as e:
        logger.error(
            "Failed to persist conversion for %s: %s", result.url, e, exc_info=True
        )
        try:
            await db.rollback()
        except Exception:
            pass
        raise


@asynccontextmanager
async def conversion_service_context(
    user_id: str | None = None,
    db: AsyncSession | None = None,
):
    """Async context manager that creates a fully wired ConversionService.

    Starts BrowserManager before yielding and closes it on exit.
    If user_id + db are provided, attaches the user's EbayLister so
    publish=True calls actually create eBay listings.
    """
    browser_manager = BrowserManager()
    try:
        await browser_manager.start()

        ebay_lister = None
        if user_id and db:
            ebay_lister = await get_ebay_lister_for_user(user_id, db)

        service = ConversionService(
            proxy_manager=ProxyManager(),
            browser_manager=browser_manager,
            compliance_service=ComplianceService(),
            profit_engine=ProfitEngine(),
            ebay_converter=EbayConverter(),
            ebay_lister=ebay_lister,
        )
        yield service
    finally:
        await browser_manager.close()
