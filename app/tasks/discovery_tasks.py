"""
Auto-discovery background tasks.

Scheduled task that runs auto-discovery for all users with the feature
enabled, finding profitable products to convert and list.
"""

import logging

from app.db.database import async_session_factory
from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager

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


async def auto_discover_task(ctx: dict) -> dict:
    """
    Scheduled task: run auto-discovery for all enabled users.

    Iterates through all users who have auto-discovery enabled and
    searches for profitable products to convert and list.

    Returns:
        Summary dict with total users processed, products found, and errors.
    """
    logger.info("[auto-discover] Starting auto-discovery sweep")

    proxy_mgr, browser_mgr = await _get_infrastructure()

    total_users = 0
    total_evaluated = 0
    total_converted = 0
    total_errors = 0

    async with async_session_factory() as session:
        from app.db.repositories.auto_discovery_repo import AutoDiscoveryRepository
        from app.services.auto_discovery_service import AutoDiscoveryService

        repo = AutoDiscoveryRepository(session)
        configs = await repo.get_enabled_configs()

        logger.info(
            "[auto-discover] Found %d users with auto-discovery enabled",
            len(configs),
        )

        for config in configs:
            total_users += 1
            try:
                service = AutoDiscoveryService(
                    session=session,
                    proxy_manager=proxy_mgr,
                    browser_manager=browser_mgr,
                )
                result = await service.run_for_user(config.user_id)

                total_evaluated += result.get("products_evaluated", 0)
                total_converted += result.get("products_converted", 0)
                total_errors += result.get("errors", 0)

                await session.commit()

            except Exception as e:
                logger.error(
                    "[auto-discover] Error running auto-discovery for user %s: %s",
                    config.user_id, e,
                )
                await session.rollback()
                total_errors += 1

    summary = {
        "users_processed": total_users,
        "total_evaluated": total_evaluated,
        "total_converted": total_converted,
        "total_errors": total_errors,
    }
    logger.info("[auto-discover] Auto-discovery complete: %s", summary)
    return summary
