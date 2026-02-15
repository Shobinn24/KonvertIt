"""
Abstract base scraper with integrated resilience patterns.

Provides the template method pattern for all marketplace scrapers:
scrape() → _navigate() → _extract() → _validate() → _transform()
"""

import logging
import time
from abc import abstractmethod
from typing import Any

from app.core.exceptions import ScrapingError
from app.core.interfaces import IScrapeable
from app.core.models import ScrapedProduct
from app.core.resilience import CircuitBreaker, retry_with_backoff
from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)


class BaseScraper(IScrapeable):
    """
    Abstract base class for marketplace scrapers.

    Integrates CircuitBreaker, retry_with_backoff, ProxyManager, and BrowserManager
    into a single template method pipeline.

    Subclasses must implement:
        _extract(page_content: str) -> dict   — Parse HTML into raw data dict
        _transform(raw_data: dict) -> ScrapedProduct — Convert raw data to domain model

    Optional overrides:
        _detect_bot_block(page_content: str) -> bool — Check for anti-bot pages
        _get_selectors() -> dict — Return CSS selectors for this marketplace
    """

    # Subclasses set this
    SOURCE_NAME: str = "unknown"

    def __init__(
        self,
        proxy_manager: ProxyManager,
        browser_manager: BrowserManager,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        self._proxy_manager = proxy_manager
        self._browser_manager = browser_manager
        self._circuit_breaker = circuit_breaker or CircuitBreaker(name=self.SOURCE_NAME)

    async def scrape(self, url: str) -> ScrapedProduct:
        """
        Full scraping pipeline: navigate → extract → validate → transform.

        Integrates circuit breaker protection and retries.
        """
        start_time = time.monotonic()
        logger.info(f"[{self.SOURCE_NAME}] Scraping: {url}")

        async with self._circuit_breaker:
            product = await self._scrape_with_retry(url)

        elapsed = time.monotonic() - start_time
        logger.info(
            f"[{self.SOURCE_NAME}] Scraped '{product.title[:50]}...' "
            f"(${product.price}) in {elapsed:.1f}s"
        )
        return product

    @retry_with_backoff(
        max_retries=3,
        base_delay=2.0,
        retryable_exceptions=(ScrapingError,),
    )
    async def _scrape_with_retry(self, url: str) -> ScrapedProduct:
        """Execute the scraping pipeline with retry protection."""
        proxy = await self._proxy_manager.get_proxy()
        page = None

        try:
            page = await self._browser_manager.get_page(proxy=proxy)

            # Navigate to the product page
            content = await self._navigate(page, url)

            # Check for bot detection
            if self._detect_bot_block(content):
                await self._proxy_manager.report_failure(proxy)
                raise ScrapingError(
                    f"Bot detection triggered on {self.SOURCE_NAME}",
                    details={"url": url, "proxy": proxy.address},
                )

            # Extract raw data from HTML
            raw_data = self._extract(content)

            # Transform into domain model
            product = self._transform(raw_data, url)

            # Validate completeness
            if not self.validate(product):
                raise ScrapingError(
                    f"Incomplete product data from {url}",
                    details={"raw_data": raw_data},
                )

            await self._proxy_manager.report_success(proxy)
            return product

        except ScrapingError:
            await self._proxy_manager.report_failure(proxy)
            raise
        except Exception as e:
            await self._proxy_manager.report_failure(proxy)
            raise ScrapingError(
                f"Unexpected error scraping {url}: {e}",
                details={"url": url, "error_type": type(e).__name__},
            ) from e
        finally:
            if page:
                await self._browser_manager.release_page(page)

    async def _navigate(self, page, url: str) -> str:
        """Navigate to the URL and return page content."""
        await self._browser_manager.apply_human_delay()

        # Clean the URL before navigating (strip tracking params, etc.)
        clean_url = self._clean_url(url)

        response = await page.goto(clean_url, wait_until="domcontentloaded", timeout=60000)

        if response and response.status == 404:
            from app.core.exceptions import ProductNotFoundError
            raise ProductNotFoundError(f"Product not found at {url}")

        if response and response.status == 429:
            from app.core.exceptions import RateLimitError
            raise RateLimitError(f"Rate limited by {self.SOURCE_NAME}")

        # Wait for dynamic content to render
        await page.wait_for_timeout(2000)

        return await page.content()

    def validate(self, product: ScrapedProduct) -> bool:
        """Validate that the scraped product has minimum required data."""
        return product.is_complete

    def _clean_url(self, url: str) -> str:
        """
        Clean a product URL by stripping unnecessary tracking parameters.

        Subclasses can override for marketplace-specific URL normalization.
        Default: returns URL as-is.
        """
        return url

    @abstractmethod
    def _extract(self, page_content: str) -> dict[str, Any]:
        """
        Extract raw product data from page HTML.

        Args:
            page_content: Full HTML content of the product page.

        Returns:
            Dict of raw extracted fields (title, price, images, etc.)
        """
        ...

    @abstractmethod
    def _transform(self, raw_data: dict[str, Any], url: str) -> ScrapedProduct:
        """
        Transform raw extracted data into a ScrapedProduct domain model.

        Args:
            raw_data: Dict from _extract().
            url: The original product URL.

        Returns:
            ScrapedProduct with cleaned, normalized data.
        """
        ...

    def _detect_bot_block(self, page_content: str) -> bool:
        """
        Check if the page indicates bot detection.

        Subclasses should override for marketplace-specific detection.
        Default checks for common patterns.
        """
        content_lower = page_content.lower()
        bot_indicators = [
            "captcha",
            "robot",
            "automated access",
            "please verify",
            "access denied",
        ]
        return any(indicator in content_lower for indicator in bot_indicators)
