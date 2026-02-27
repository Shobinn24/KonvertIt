"""
Walmart product page scraper.

When ScraperAPI is configured, uses their Structured Data endpoint
(/structured/walmart/product) for reliable JSON responses — no HTML
parsing or anti-bot handling needed. Falls back to Playwright +
BeautifulSoup for other proxy providers or direct connections.
"""

import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.exceptions import CaptchaDetectedError, ProductNotFoundError, ScrapingError
from app.core.models import ScrapedProduct, SourceMarketplace
from app.core.resilience import retry_with_backoff
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Walmart product ID patterns
WALMART_ID_PATTERN = re.compile(r"/ip/(?:[^/]+/)?(\d+)")
WALMART_ID_FALLBACK = re.compile(r"/(\d{8,13})(?:\?|$)")

# Price patterns (for Playwright fallback)
PRICE_PATTERN = re.compile(r"\$?([\d,]+\.?\d*)")

# ScraperAPI structured endpoint for Walmart products
SCRAPERAPI_STRUCTURED_URL = "https://api.scraperapi.com/structured/walmart/product"


class WalmartScraper(BaseScraper):
    """
    Scraper for Walmart product pages.

    Primary strategy: ScraperAPI Structured Data endpoint (returns JSON).
    Fallback strategy: Playwright + CSS selector-based HTML parsing.

    Handles:
    - ScraperAPI Structured endpoint (preferred — JSON, no bot issues)
    - Playwright fallback for non-ScraperAPI proxy providers
    - Product ID extraction from URL
    """

    SOURCE_NAME = "walmart"

    # ─── ScraperAPI Structured Endpoint ──────────────────────────

    def _get_scraperapi_key(self) -> str | None:
        """Get ScraperAPI key from the proxy manager's config."""
        for proxy in self._proxy_manager._proxies:
            if proxy.provider == "scraperapi" and proxy.is_active:
                addr = proxy.address
                if "api_key=" in addr:
                    key_start = addr.index("api_key=") + len("api_key=")
                    key_end = addr.index("&", key_start) if "&" in addr[key_start:] else len(addr)
                    return addr[key_start:key_end]
        return None

    @retry_with_backoff(
        max_retries=2,
        base_delay=2.0,
        retryable_exceptions=(ScrapingError,),
    )
    async def _scrape_with_retry(self, url: str) -> ScrapedProduct:
        """Execute scraping with ScraperAPI structured endpoint or Playwright fallback.

        Uses ScraperAPI's /structured/walmart/product endpoint which returns
        clean JSON and handles anti-bot (PerimeterX) internally. No custom
        HTML parsing or ultra_premium needed.
        """
        api_key = self._get_scraperapi_key()
        product_id = self._extract_product_id(url)

        if api_key and product_id:
            return await self._scrape_structured(api_key, product_id, url)

        # Fallback to Playwright-based scraping (parent implementation)
        return await super()._scrape_with_retry(url)

    async def _scrape_structured(self, api_key: str, product_id: str, url: str) -> ScrapedProduct:
        """Scrape using ScraperAPI's structured Walmart Product endpoint.

        Returns structured JSON directly — no browser, HTML parsing, or
        anti-bot params needed. ScraperAPI handles PerimeterX internally.
        """
        proxy = await self._proxy_manager.get_proxy()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    SCRAPERAPI_STRUCTURED_URL,
                    params={
                        "api_key": api_key,
                        "product_id": product_id,
                        "country_code": "us",
                        "tld": "com",
                    },
                )

            if response.status_code == 404:
                raise ProductNotFoundError(
                    f"Walmart product not found: {product_id}. "
                    "The product may have been removed or the URL may be incorrect."
                )

            if response.status_code == 429:
                raise ScrapingError(
                    "ScraperAPI rate limit exceeded",
                    details={"status": 429, "url": url},
                )

            if response.status_code != 200:
                raise ScrapingError(
                    f"ScraperAPI structured endpoint returned {response.status_code} for Walmart",
                    details={"status": response.status_code, "body": response.text[:500]},
                )

            data = response.json()
            raw_data = self._extract_from_structured(data)
            product = self._transform(raw_data, url)

            if not self.validate(product):
                raise ScrapingError(
                    f"Incomplete product data from structured API for {url}",
                    details={"raw_data": raw_data},
                )

            await self._proxy_manager.report_success(proxy)
            logger.info(f"[walmart] Structured API success for product {product_id}")
            return product

        except ScrapingError:
            await self._proxy_manager.report_failure(proxy)
            raise
        except ProductNotFoundError:
            raise
        except Exception as e:
            await self._proxy_manager.report_failure(proxy)
            raise ScrapingError(
                f"Structured API error for {url}: {e}",
                details={"url": url, "error_type": type(e).__name__},
            ) from e

    def _extract_from_structured(self, data: dict) -> dict[str, Any]:
        """Extract raw product fields from ScraperAPI structured JSON response.

        ScraperAPI Walmart Product endpoint returns:
        - product_name, product_description, brand, image
        - offers: [{url, availability, available_delivery_method, item_condition}]
        """
        # Extract price from product_name or offers (ScraperAPI may include
        # price in various places depending on the product)
        price = 0.0
        pricing_str = data.get("pricing", data.get("price", ""))
        if pricing_str:
            match = PRICE_PATTERN.search(str(pricing_str))
            if match:
                try:
                    price = float(match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # If no top-level price, check offers
        if price == 0.0:
            offers = data.get("offers", [])
            if isinstance(offers, list):
                for offer in offers:
                    offer_price = offer.get("price", "")
                    if offer_price:
                        match = PRICE_PATTERN.search(str(offer_price))
                        if match:
                            try:
                                price = float(match.group(1).replace(",", ""))
                                if price > 0:
                                    break
                            except ValueError:
                                continue

        # Extract images — can be string or list
        raw_image = data.get("image", data.get("images", []))
        if isinstance(raw_image, str):
            images = [self._to_large_image(raw_image)] if raw_image else []
        elif isinstance(raw_image, list):
            images = [self._to_large_image(img) for img in raw_image if img][:12]
        else:
            images = []

        # Extract availability from offers
        availability = ""
        offers = data.get("offers", [])
        if isinstance(offers, list) and offers:
            availability = offers[0].get("availability", "")
            # Clean up schema.org-style values like "https://schema.org/InStock"
            if "/" in availability:
                availability = availability.rsplit("/", 1)[-1]

        # Build description
        description = data.get("product_description", data.get("description", ""))
        if isinstance(description, list):
            description = " | ".join(description)

        # Clean HTML from description
        if description and "<" in description:
            desc_soup = BeautifulSoup(description, "lxml")
            description = desc_soup.get_text(separator=" ", strip=True)

        return {
            "title": data.get("product_name", data.get("name", "")),
            "price": price,
            "brand": data.get("brand", ""),
            "images": images,
            "description": description,
            "category": data.get("category", data.get("product_category", "")),
            "availability": availability,
            "structured_api": True,
        }

    # ─── CSS Selectors (Playwright fallback) ────────────────────

    SELECTORS = {
        "title": [
            "h1[itemprop='name']",
            "#main-title",
            "h1.prod-ProductTitle",
            "[data-testid='product-title']",
            "h1",
        ],
        "price": [
            "[itemprop='price']",
            "[data-testid='price-wrap'] .f2",
            "span.price-group",
            ".price-characteristic",
            "[data-automation-id='product-price'] .f2",
        ],
        "brand": [
            "a[itemprop='brand']",
            "[data-testid='product-brand']",
            ".prod-brandName a",
            "span.brand",
        ],
        "images": [
            "[data-testid='hero-image'] img",
            ".prod-HeroImage img",
            "img.prod-hero-image",
            "[data-testid='media-thumbnail'] img",
        ],
        "description": [
            "[data-testid='product-description']",
            ".about-desc .about-product-description",
            ".prod-ProductDescription",
            "#product-description-section",
        ],
        "category": [
            "[data-testid='breadcrumb'] a",
            ".breadcrumb a",
            "nav.breadcrumb a",
        ],
    }

    # ─── Playwright Fallback Extraction ─────────────────────────

    def _extract(self, page_content: str) -> dict[str, Any]:
        """Extract raw product data from Walmart page HTML (Playwright fallback)."""
        soup = BeautifulSoup(page_content, "lxml")

        return {
            "title": self._select_text(soup, self.SELECTORS["title"]),
            "price": self._extract_price_html(soup),
            "brand": self._select_text(soup, self.SELECTORS["brand"]),
            "images": self._extract_images_html(soup),
            "description": self._select_text(soup, self.SELECTORS["description"]),
            "category": self._extract_category_html(soup),
            "availability": "",
            "source": "html",
        }

    def _select_text(self, soup: BeautifulSoup, selectors: list[str]) -> str:
        """Try multiple CSS selectors, return first non-empty text."""
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text:
                    return text
        return ""

    def _extract_price_html(self, soup: BeautifulSoup) -> float:
        """Extract price from HTML selectors."""
        for selector in self.SELECTORS["price"]:
            elements = soup.select(selector)
            for element in elements:
                content = element.get("content", "")
                if content:
                    try:
                        price = float(content)
                        if price > 0:
                            return price
                    except ValueError:
                        pass

                text = element.get_text(strip=True)
                match = PRICE_PATTERN.search(text)
                if match:
                    price_str = match.group(1).replace(",", "")
                    try:
                        price = float(price_str)
                        if price > 0:
                            return price
                    except ValueError:
                        continue
        return 0.0

    def _extract_images_html(self, soup: BeautifulSoup) -> list[str]:
        """Extract image URLs from HTML."""
        images = []
        seen = set()

        for selector in self.SELECTORS["images"]:
            elements = soup.select(selector)
            for element in elements:
                url = element.get("src", element.get("data-src", ""))
                if url and url not in seen and url.startswith("http"):
                    images.append(self._to_large_image(url))
                    seen.add(url)

        return images[:12]

    def _extract_category_html(self, soup: BeautifulSoup) -> str:
        """Extract category from breadcrumb links."""
        for selector in self.SELECTORS["category"]:
            elements = soup.select(selector)
            if elements:
                categories = [a.get_text(strip=True) for a in elements if a.get_text(strip=True)]
                if categories:
                    return " > ".join(categories)
        return ""

    # ─── Transform & Validate ──────────────────────────────────

    def _transform(self, raw_data: dict[str, Any], url: str) -> ScrapedProduct:
        """Transform raw extracted data into a ScrapedProduct."""
        product_id = self._extract_product_id(url)

        return ScrapedProduct(
            title=raw_data.get("title", ""),
            price=raw_data.get("price", 0.0),
            brand=raw_data.get("brand", ""),
            images=raw_data.get("images", []),
            description=raw_data.get("description", ""),
            category=raw_data.get("category", ""),
            availability=raw_data.get("availability", ""),
            source_marketplace=SourceMarketplace.WALMART,
            source_url=url,
            source_product_id=product_id,
            raw_data=raw_data,
        )

    def _extract_product_id(self, url: str) -> str:
        """Extract Walmart product ID from URL."""
        # Pattern: /ip/product-name/123456789 or /ip/123456789
        match = WALMART_ID_PATTERN.search(url)
        if match:
            return match.group(1)

        # Fallback: look for long numeric sequence
        match = WALMART_ID_FALLBACK.search(url)
        if match:
            return match.group(1)

        # Last resort: split URL and find numeric part
        parts = url.rstrip("/").split("/")
        for part in reversed(parts):
            part = part.split("?")[0]
            if part.isdigit() and len(part) >= 8:
                return part

        return ""

    def _clean_url(self, url: str) -> str:
        """Normalize Walmart URL to minimal form."""
        product_id = self._extract_product_id(url)
        if product_id:
            clean = f"https://www.walmart.com/ip/{product_id}"
            logger.debug(f"Cleaned Walmart URL: {url[:80]}... → {clean}")
            return clean
        return url

    def _to_large_image(self, url: str) -> str:
        """Convert Walmart image URL to large version."""
        if not url or not url.startswith("http"):
            return url
        # Remove query params
        url = re.sub(r"\?.*$", "", url)
        if "walmartimages.com" in url:
            # Remove size constraints to get the large version
            url = re.sub(r"_\d+x\d+", "", url)
        return url

    # ─── Bot Detection (Playwright fallback) ───────────────────

    def _detect_bot_block(self, page_content: str) -> bool:
        """
        Detect Walmart-specific bot blocking patterns.

        Only used for Playwright fallback path — structured endpoint
        handles anti-bot internally.
        """
        content_lower = page_content.lower()

        # CAPTCHA detection (PerimeterX)
        captcha_indicators = [
            "captcha",
            "perimeterx",
            "px-captcha",
            "press & hold",
            "human verification",
        ]
        if any(indicator in content_lower for indicator in captcha_indicators):
            raise CaptchaDetectedError(
                "Walmart CAPTCHA detected (PerimeterX)",
                details={"content_length": len(page_content)},
            )

        # Access denied
        blocked_indicators = [
            "access denied",
            "blocked",
            "robot or automated",
            "unusual traffic",
        ]
        if any(indicator in content_lower for indicator in blocked_indicators):
            logger.warning("Walmart bot detection triggered")
            return True

        # Suspiciously short page
        if len(page_content) < 5000:
            logger.warning(
                f"Walmart returned unusually short page ({len(page_content)} bytes). "
                "Possible bot detection."
            )
            return True

        return False
