"""
Playwright headless browser pool manager.

Provides configured browser contexts with anti-detection measures
for scraping Amazon and Walmart product pages.
"""

import asyncio
import logging
import random

from app.config import get_settings
from app.scrapers.proxy_manager import DIRECT_PROXY, Proxy

logger = logging.getLogger(__name__)

# Common user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

# Common viewport sizes
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]


class BrowserManager:
    """
    Manages a pool of Playwright browser contexts with stealth configuration.

    Each context is configured with:
    - Randomized user agent
    - Randomized viewport size
    - Proxy support (if provided)
    - Anti-fingerprinting measures
    - Configurable request delays for respectful scraping

    Usage:
        async with BrowserManager() as manager:
            page = await manager.get_page(proxy=some_proxy)
            await page.goto(url)
            content = await page.content()
            await page.close()
    """

    def __init__(self, pool_size: int | None = None, headless: bool | None = None):
        settings = get_settings()
        self._pool_size = pool_size or settings.browser_pool_size
        self._headless = headless if headless is not None else settings.headless
        self._min_delay = settings.scrape_min_delay
        self._max_delay = settings.scrape_max_delay
        self._browser = None
        self._playwright = None
        self._semaphore = asyncio.Semaphore(self._pool_size)

    async def __aenter__(self) -> "BrowserManager":
        """Launch the browser on context entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close the browser on context exit."""
        await self.close()

    async def start(self) -> None:
        """Launch the Playwright browser."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        logger.info(
            f"Browser launched (headless={self._headless}, pool_size={self._pool_size})"
        )

    async def close(self) -> None:
        """Close the browser and Playwright instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser closed")

    def _get_random_user_agent(self) -> str:
        """Select a random user agent string."""
        return random.choice(USER_AGENTS)

    def _get_random_viewport(self) -> dict:
        """Select a random viewport size."""
        return random.choice(VIEWPORTS)

    async def get_page(self, proxy: Proxy | None = None):
        """
        Create a new browser page with stealth configuration.

        Args:
            proxy: Optional proxy to route this page's traffic through.
                   If None or DIRECT, no proxy is used.

        Returns:
            A configured Playwright Page ready for navigation.

        Note:
            The caller is responsible for closing the page when done.
        """
        if self._browser is None:
            raise RuntimeError("BrowserManager not started. Use 'async with' or call start().")

        await self._semaphore.acquire()

        user_agent = self._get_random_user_agent()
        viewport = self._get_random_viewport()

        context_kwargs = {
            "user_agent": user_agent,
            "viewport": viewport,
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "java_script_enabled": True,
            "ignore_https_errors": True,
        }

        # Configure proxy if provided
        if proxy and proxy is not DIRECT_PROXY and proxy.address != "DIRECT":
            context_kwargs["proxy"] = {"server": proxy.address}

        context = await self._browser.new_context(**context_kwargs)

        # Anti-detection: remove webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = {runtime: {}};
        """)

        page = await context.new_page()

        # Set extra headers to look more like a real browser
        await page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })

        logger.debug(
            f"Created page with UA={user_agent[:50]}..., "
            f"viewport={viewport['width']}x{viewport['height']}, "
            f"proxy={'yes' if proxy and proxy is not DIRECT_PROXY else 'direct'}"
        )

        return page

    async def release_page(self, page) -> None:
        """
        Release a page back to the pool.

        Closes the page's browser context and releases the semaphore slot.
        """
        try:
            context = page.context
            await page.close()
            await context.close()
        except Exception as e:
            logger.warning(f"Error closing page/context: {e}")
        finally:
            self._semaphore.release()

    async def apply_human_delay(self) -> None:
        """
        Apply a random delay to simulate human browsing behavior.

        Uses the configured min/max delay from settings.
        """
        delay = random.uniform(self._min_delay, self._max_delay)
        await asyncio.sleep(delay)
