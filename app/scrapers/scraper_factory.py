"""
Factory pattern for creating marketplace-specific scrapers.

Enables polymorphic scraper creation — consumers call
ScraperFactory.create("amazon") without knowing the concrete class.
"""

from app.core.exceptions import KonvertItError
from app.scrapers.base_scraper import BaseScraper
from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager


class UnsupportedMarketplaceError(KonvertItError):
    """Raised when an unrecognized marketplace source is requested."""
    pass


class ScraperFactory:
    """
    Factory that creates the correct scraper based on source marketplace.

    Usage:
        scraper = ScraperFactory.create("amazon", proxy_manager, browser_manager)
        product = await scraper.scrape(url)
    """

    _registry: dict[str, type[BaseScraper]] = {}

    @classmethod
    def register(cls, source_name: str, scraper_class: type[BaseScraper]) -> None:
        """Register a scraper class for a source marketplace."""
        cls._registry[source_name.lower()] = scraper_class

    @classmethod
    def create(
        cls,
        source: str,
        proxy_manager: ProxyManager,
        browser_manager: BrowserManager,
    ) -> BaseScraper:
        """
        Create a scraper instance for the given source marketplace.

        Args:
            source: Marketplace name ("amazon", "walmart", etc.)
            proxy_manager: Shared proxy rotation manager.
            browser_manager: Shared browser pool manager.

        Returns:
            Configured scraper instance.

        Raises:
            UnsupportedMarketplaceError: If the source is not registered.
        """
        source_lower = source.lower()

        if source_lower not in cls._registry:
            available = ", ".join(cls._registry.keys()) or "none"
            raise UnsupportedMarketplaceError(
                f"Unsupported marketplace: '{source}'. Available: {available}"
            )

        scraper_class = cls._registry[source_lower]
        return scraper_class(
            proxy_manager=proxy_manager,
            browser_manager=browser_manager,
        )

    @classmethod
    def available_sources(cls) -> list[str]:
        """List all registered source marketplaces."""
        return list(cls._registry.keys())


# ─── Register scrapers ────────────────────────────────────────

def _register_default_scrapers() -> None:
    """Register all built-in scrapers."""
    from app.scrapers.amazon_scraper import AmazonScraper
    from app.scrapers.walmart_scraper import WalmartScraper

    ScraperFactory.register("amazon", AmazonScraper)
    ScraperFactory.register("walmart", WalmartScraper)


_register_default_scrapers()
