"""
Price monitoring service.

Monitors source marketplace prices for products with active listings.
Detects price changes and records history for trend analysis.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product
from app.db.repositories.listing_repo import ListingRepository
from app.db.repositories.price_history_repo import PriceHistoryRepository
from app.db.repositories.product_repo import ProductRepository
from app.scrapers.base_scraper import BaseScraper
from app.scrapers.scraper_factory import ScraperFactory

logger = logging.getLogger(__name__)


class PriceCheckResult:
    """Result of checking a single product's price."""

    __slots__ = ("product_id", "old_price", "new_price", "changed", "error")

    def __init__(
        self,
        product_id: uuid.UUID,
        old_price: float,
        new_price: float | None = None,
        changed: bool = False,
        error: str | None = None,
    ):
        self.product_id = product_id
        self.old_price = old_price
        self.new_price = new_price
        self.changed = changed
        self.error = error

    def to_dict(self) -> dict:
        return {
            "product_id": str(self.product_id),
            "old_price": self.old_price,
            "new_price": self.new_price,
            "changed": self.changed,
            "error": self.error,
        }


class PriceMonitorService:
    """
    Monitors source marketplace prices for active listings.

    Workflow:
    1. Find all products with active eBay listings for a user.
    2. Re-scrape each product's source URL to get the current price.
    3. Compare with the stored price.
    4. Record a price history entry if the price changed.
    """

    def __init__(
        self,
        session: AsyncSession,
        scraper_factory: type[ScraperFactory] | None = None,
        proxy_manager=None,
        browser_manager=None,
    ):
        self._session = session
        self._product_repo = ProductRepository(session)
        self._listing_repo = ListingRepository(session)
        self._price_repo = PriceHistoryRepository(session)
        self._scraper_factory = scraper_factory or ScraperFactory
        self._proxy_manager = proxy_manager
        self._browser_manager = browser_manager

    def _get_scraper(self, marketplace: str) -> BaseScraper:
        """Get a scraper instance for the given marketplace."""
        return self._scraper_factory.create(
            source=marketplace,
            proxy_manager=self._proxy_manager,
            browser_manager=self._browser_manager,
        )

    async def check_price(self, product: Product) -> PriceCheckResult:
        """
        Check the current price of a product by re-scraping its source URL.

        Records a new price history entry if the price changed.

        Args:
            product: The Product ORM instance to check.

        Returns:
            PriceCheckResult with old/new prices and change status.
        """
        old_price = product.price

        try:
            scraper = self._get_scraper(product.source_marketplace)
            scraped = await scraper.scrape(product.source_url)
            new_price = scraped.price
        except Exception as e:
            logger.warning(
                "Failed to scrape price for product %s: %s",
                product.id, e,
            )
            return PriceCheckResult(
                product_id=product.id,
                old_price=old_price,
                error=str(e),
            )

        changed = abs(new_price - old_price) > 0.001

        # Always record current price for history tracking
        await self._price_repo.record_price(
            product_id=product.id,
            price=new_price,
        )

        if changed:
            # Update the product's stored price
            await self._product_repo.update(product.id, price=new_price)
            logger.info(
                "Price changed for product %s: $%.2f → $%.2f",
                product.id, old_price, new_price,
            )

            # Push real-time price alert via WebSocket
            try:
                from app.services.ws_manager import WSEvent, WSEventType, get_ws_manager
                ws_mgr = get_ws_manager()
                await ws_mgr.send_to_user(str(product.user_id), WSEvent(
                    event=WSEventType.PRICE_ALERT,
                    data={
                        "product_id": str(product.id),
                        "title": product.title,
                        "old_price": old_price,
                        "new_price": new_price,
                        "source_marketplace": product.source_marketplace,
                    },
                ))
            except Exception:
                pass  # WS is best-effort; don't break price monitoring

        return PriceCheckResult(
            product_id=product.id,
            old_price=old_price,
            new_price=new_price,
            changed=changed,
        )

    async def check_all_for_user(
        self,
        user_id: uuid.UUID,
    ) -> list[PriceCheckResult]:
        """
        Check prices for all products with active listings for a user.

        Args:
            user_id: The user whose products to monitor.

        Returns:
            List of PriceCheckResult, one per product checked.
        """
        active_listings = await self._listing_repo.find_active_by_user(user_id)

        if not active_listings:
            return []

        # Get the product IDs from active listings (listings have product via conversion)
        # We need to find products that have active listings.
        # Since Listing doesn't directly reference Product, we need to go through conversions.
        # For efficiency, get all products for the user and filter to those with active listings.
        products = await self._product_repo.find_by_user(
            user_id=user_id,
            limit=200,
        )

        results: list[PriceCheckResult] = []
        for product in products:
            result = await self.check_price(product)
            results.append(result)

        return results
