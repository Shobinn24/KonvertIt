"""
Background scraping and conversion tasks.

Provides async task queue functions for:
- Single product scraping
- Single URL conversion (scrape → convert → price)
- Bulk conversion with progress tracking
"""

import logging

from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager
from app.services.conversion_service import ConversionService

logger = logging.getLogger(__name__)

# Shared infrastructure — initialized on worker startup
_proxy_manager: ProxyManager | None = None
_browser_manager: BrowserManager | None = None


async def _get_conversion_service() -> ConversionService:
    """Get or create the shared ConversionService with initialized infrastructure."""
    global _proxy_manager, _browser_manager

    if _proxy_manager is None:
        _proxy_manager = ProxyManager()

    if _browser_manager is None:
        _browser_manager = BrowserManager()
        await _browser_manager.start()

    return ConversionService(
        proxy_manager=_proxy_manager,
        browser_manager=_browser_manager,
    )


async def scrape_product_task(ctx: dict, url: str, user_id: str) -> dict:
    """
    Background task: scrape a single product URL and return scraped data.

    Args:
        ctx: arq worker context (contains Redis connection).
        url: Product URL to scrape.
        user_id: User who initiated the scrape.

    Returns:
        Dict with scraped product data or error info.
    """
    logger.info(f"[task] Scraping {url} for user {user_id}")

    try:
        service = await _get_conversion_service()
        result = await service.preview_conversion(url=url, user_id=user_id)

        if result.is_successful and result.product:
            return {
                "status": "success",
                "product": {
                    "title": result.product.title,
                    "price": result.product.price,
                    "brand": result.product.brand,
                    "images": result.product.images,
                    "source_product_id": result.product.source_product_id,
                    "source_marketplace": result.product.source_marketplace.value,
                },
            }
        else:
            return {
                "status": "failed",
                "error": result.error,
            }

    except Exception as e:
        logger.error(f"[task] Scrape failed for {url}: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": f"{type(e).__name__}: {e}",
        }


async def convert_product_task(
    ctx: dict,
    url: str,
    user_id: str,
    publish: bool = False,
    sell_price: float | None = None,
) -> dict:
    """
    Background task: convert a single product URL through the full pipeline.

    Args:
        ctx: arq worker context.
        url: Product URL to convert.
        user_id: User who initiated the conversion.
        publish: Whether to publish to eBay.
        sell_price: Optional price override.

    Returns:
        Dict with conversion result.
    """
    logger.info(f"[task] Converting {url} for user {user_id} (publish={publish})")

    try:
        service = await _get_conversion_service()
        result = await service.convert_url(
            url=url,
            user_id=user_id,
            publish=publish,
            sell_price=sell_price,
        )
        return result.to_dict()

    except Exception as e:
        logger.error(f"[task] Conversion failed for {url}: {e}", exc_info=True)
        return {
            "url": url,
            "status": "failed",
            "error": f"{type(e).__name__}: {e}",
        }


async def bulk_convert_task(
    ctx: dict,
    urls: list[str],
    user_id: str,
    publish: bool = False,
    sell_price: float | None = None,
) -> dict:
    """
    Background task: convert multiple product URLs with progress tracking.

    Args:
        ctx: arq worker context.
        urls: List of product URLs to convert.
        user_id: User who initiated the bulk conversion.
        publish: Whether to publish each to eBay.
        sell_price: Optional price override for all items.

    Returns:
        Dict with bulk conversion progress and results.
    """
    logger.info(f"[task] Bulk converting {len(urls)} URLs for user {user_id}")

    try:
        service = await _get_conversion_service()
        progress = await service.convert_bulk(
            urls=urls,
            user_id=user_id,
            publish=publish,
            sell_price=sell_price,
        )
        return progress.to_dict()

    except Exception as e:
        logger.error(f"[task] Bulk conversion failed: {e}", exc_info=True)
        return {
            "total": len(urls),
            "completed": 0,
            "failed": len(urls),
            "error": f"{type(e).__name__}: {e}",
        }


async def startup(ctx: dict) -> None:
    """Worker startup — initialize shared resources."""
    global _proxy_manager, _browser_manager

    logger.info("[worker] Initializing shared resources...")
    _proxy_manager = ProxyManager()
    _browser_manager = BrowserManager()
    await _browser_manager.start()
    logger.info("[worker] Shared resources ready")


async def shutdown(ctx: dict) -> None:
    """Worker shutdown — cleanup shared resources."""
    global _browser_manager

    logger.info("[worker] Cleaning up shared resources...")
    if _browser_manager:
        await _browser_manager.close()
        _browser_manager = None
    logger.info("[worker] Cleanup complete")
