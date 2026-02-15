"""
Price monitoring background tasks.

Scheduled task that checks current marketplace prices for all products
with active listings and records price history.
"""

import logging

from app.db.database import async_session_factory
from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager
from app.services.price_monitor_service import PriceMonitorService

logger = logging.getLogger(__name__)

# Shared infrastructure — initialized on first use
_proxy_manager: ProxyManager | None = None
_browser_manager: BrowserManager | None = None


async def _get_infrastructure():
    """Get or create shared scraping infrastructure."""
    global _proxy_manager, _browser_manager

    if _proxy_manager is None:
        _proxy_manager = ProxyManager()

    if _browser_manager is None:
        _browser_manager = BrowserManager()
        await _browser_manager.start()

    return _proxy_manager, _browser_manager


async def monitor_prices_task(ctx: dict) -> dict:
    """
    Scheduled task: check prices for all products with active listings.

    Iterates through all users who have active listings and checks
    source marketplace prices for changes.

    Returns:
        Summary dict with total products checked and changes detected.
    """
    logger.info("[monitor] Starting price monitoring sweep")

    proxy_mgr, browser_mgr = await _get_infrastructure()

    total_checked = 0
    total_changed = 0
    total_errors = 0

    async with async_session_factory() as session:
        # Get all users with active listings by querying distinct user_ids
        from sqlalchemy import distinct, select

        from app.db.models import Listing

        stmt = (
            select(distinct(Listing.user_id))
            .where(Listing.status == "active")
        )
        result = await session.execute(stmt)
        user_ids = [row[0] for row in result.all()]

        logger.info("[monitor] Found %d users with active listings", len(user_ids))

        for user_id in user_ids:
            try:
                service = PriceMonitorService(
                    session=session,
                    proxy_manager=proxy_mgr,
                    browser_manager=browser_mgr,
                )
                results = await service.check_all_for_user(user_id)

                for r in results:
                    total_checked += 1
                    if r.changed:
                        total_changed += 1
                    if r.error:
                        total_errors += 1

                await session.commit()

            except Exception as e:
                logger.error(
                    "[monitor] Error checking prices for user %s: %s",
                    user_id, e,
                )
                await session.rollback()
                total_errors += 1

    summary = {
        "total_checked": total_checked,
        "total_changed": total_changed,
        "total_errors": total_errors,
        "users_processed": len(user_ids),
    }
    logger.info("[monitor] Price monitoring complete: %s", summary)
    return summary
