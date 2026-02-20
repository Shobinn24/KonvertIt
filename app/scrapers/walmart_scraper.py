"""
Walmart product page scraper.

Walmart uses Next.js with __NEXT_DATA__ JSON embedded in page source,
making data extraction more reliable than HTML parsing. Falls back to
HTML selectors when __NEXT_DATA__ is unavailable.

When ScraperAPI is configured, fetches page HTML via httpx (no Playwright
needed) and parses it with the existing extraction pipeline.
"""

import json
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from app.core.exceptions import CaptchaDetectedError, ScrapingError
from app.core.models import ScrapedProduct, SourceMarketplace
from app.core.resilience import retry_with_backoff
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Walmart product ID patterns
WALMART_ID_PATTERN = re.compile(r"/ip/(?:[^/]+/)?(\d+)")
WALMART_ID_FALLBACK = re.compile(r"/(\d{8,13})(?:\?|$)")


class WalmartScraper(BaseScraper):
    """
    Scraper for Walmart product pages.

    Primary strategy: Extract __NEXT_DATA__ JSON from page source.
    Fallback strategy: CSS selector-based HTML parsing.

    Handles:
    - __NEXT_DATA__ JSON extraction (preferred — structured, reliable)
    - HTML fallback for pages without __NEXT_DATA__
    - Bot detection (CAPTCHA, access denied)
    - Product ID extraction from URL
    - Price extraction from multiple data paths
    """

    SOURCE_NAME = "walmart"

    # ─── ScraperAPI httpx-based Scraping ─────────────────────────

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
        max_retries=3,
        base_delay=2.0,
        retryable_exceptions=(ScrapingError,),
    )
    async def _scrape_with_retry(self, url: str) -> ScrapedProduct:
        """Execute scraping with ScraperAPI httpx or Playwright fallback.

        ScraperAPI's Walmart structured endpoint requires ultra_premium,
        so we fetch the raw HTML via their regular API and parse it ourselves
        using the existing __NEXT_DATA__ / HTML extraction pipeline.
        """
        api_key = self._get_scraperapi_key()

        if api_key:
            return await self._scrape_via_scraperapi(api_key, url)

        # Fallback to Playwright-based scraping (parent implementation)
        return await super()._scrape_with_retry(url)

    async def _scrape_via_scraperapi(self, api_key: str, url: str) -> ScrapedProduct:
        """Fetch Walmart page HTML via ScraperAPI httpx, then parse it."""
        proxy = await self._proxy_manager.get_proxy()
        clean_url = self._clean_url(url)

        try:
            scraperapi_url = (
                f"https://api.scraperapi.com"
                f"?api_key={api_key}"
                f"&render=true"
                f"&country_code=us"
                f"&url={quote(clean_url, safe='')}"
            )

            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.get(scraperapi_url)

            if response.status_code == 404:
                from app.core.exceptions import ProductNotFoundError
                raise ProductNotFoundError(f"Product not found at {url}")

            if response.status_code == 429:
                raise ScrapingError(
                    "ScraperAPI rate limit exceeded",
                    details={"status": 429, "url": url},
                )

            if response.status_code != 200:
                raise ScrapingError(
                    f"ScraperAPI returned {response.status_code}",
                    details={"status": response.status_code, "body": response.text[:500]},
                )

            page_content = response.text

            # Check for bot detection
            if self._detect_bot_block(page_content):
                await self._proxy_manager.report_failure(proxy)
                raise ScrapingError(
                    "Bot detection triggered on walmart",
                    details={"url": url, "content_length": len(page_content)},
                )

            # Use existing extraction pipeline
            raw_data = self._extract(page_content)
            product = self._transform(raw_data, url)

            if not self.validate(product):
                raise ScrapingError(
                    f"Incomplete product data from {url}",
                    details={"raw_data": raw_data},
                )

            await self._proxy_manager.report_success(proxy)
            logger.info(f"[walmart] ScraperAPI httpx success for {url}")
            return product

        except ScrapingError:
            await self._proxy_manager.report_failure(proxy)
            raise
        except Exception as e:
            await self._proxy_manager.report_failure(proxy)
            raise ScrapingError(
                f"ScraperAPI error for {url}: {e}",
                details={"url": url, "error_type": type(e).__name__},
            ) from e

    def _clean_url(self, url: str) -> str:
        """Normalize Walmart URL to minimal form."""
        product_id = self._extract_product_id(url)
        if product_id:
            clean = f"https://www.walmart.com/ip/{product_id}"
            logger.debug(f"Cleaned Walmart URL: {url[:80]}... → {clean}")
            return clean
        return url

    # ─── CSS Selectors (fallback) ──────────────────────────────

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

    # ─── Extraction ────────────────────────────────────────────

    def _extract(self, page_content: str) -> dict[str, Any]:
        """
        Extract raw product data, preferring __NEXT_DATA__ JSON over HTML.
        """
        # Try __NEXT_DATA__ first (most reliable)
        next_data = self._extract_next_data(page_content)
        if next_data:
            product_data = self._parse_next_data(next_data)
            if product_data and product_data.get("title"):
                logger.debug("Extracted product data from __NEXT_DATA__")
                return product_data

        # Fallback to HTML parsing
        logger.debug("__NEXT_DATA__ unavailable, falling back to HTML parsing")
        return self._extract_from_html(page_content)

    def _extract_next_data(self, page_content: str) -> dict | None:
        """Extract the __NEXT_DATA__ JSON object from page source."""
        soup = BeautifulSoup(page_content, "lxml")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

        if not script_tag or not script_tag.string:
            return None

        try:
            return json.loads(script_tag.string)
        except json.JSONDecodeError:
            logger.warning("Failed to parse __NEXT_DATA__ JSON")
            return None

    def _parse_next_data(self, data: dict) -> dict[str, Any]:
        """
        Navigate the __NEXT_DATA__ JSON structure to extract product fields.

        Walmart's __NEXT_DATA__ nests product info under:
        props.pageProps.initialData.data.product (or similar paths)
        """
        product = self._find_product_in_next_data(data)
        if not product:
            return {}

        # Extract price from various possible paths
        price = self._extract_price_from_next_data(product)

        # Extract images
        images = self._extract_images_from_next_data(product)

        # Extract description
        description = ""
        short_desc = product.get("shortDescription", "")
        long_desc = product.get("detailedDescription", "")
        if short_desc:
            description = short_desc
        elif long_desc:
            description = long_desc

        # Clean HTML from description
        if "<" in description:
            desc_soup = BeautifulSoup(description, "lxml")
            description = desc_soup.get_text(separator=" ", strip=True)

        # Extract category from breadcrumb/taxonomy
        category = self._extract_category_from_next_data(product)

        return {
            "title": product.get("name", ""),
            "price": price,
            "brand": product.get("brand", ""),
            "images": images,
            "description": description,
            "category": category,
            "availability": self._extract_availability_from_next_data(product),
            "source": "next_data",
        }

    def _find_product_in_next_data(self, data: dict) -> dict | None:
        """Navigate nested __NEXT_DATA__ to find the product object."""
        # Common paths in Walmart's Next.js data structure
        paths = [
            ["props", "pageProps", "initialData", "data", "product"],
            ["props", "pageProps", "initialData", "data", "contentLayout",
             "modules", 0, "configs", "product"],
            ["props", "pageProps", "product"],
            ["props", "pageProps", "initialData", "product"],
        ]

        for path in paths:
            result = data
            try:
                for key in path:
                    if isinstance(result, dict):
                        result = result[key]
                    elif isinstance(result, list) and isinstance(key, int):
                        result = result[key]
                    else:
                        result = None
                        break
                if result and isinstance(result, dict) and result.get("name"):
                    return result
            except (KeyError, IndexError, TypeError):
                continue

        # Deep search: look for any dict with "name" and "priceInfo"
        return self._deep_find_product(data)

    def _deep_find_product(self, obj: Any, depth: int = 0) -> dict | None:
        """Recursively search for a product-like object in nested data."""
        if depth > 8:
            return None

        if isinstance(obj, dict):
            # A product typically has "name" and some price field
            if "name" in obj and ("priceInfo" in obj or "price" in obj or "offerPrice" in obj):
                return obj
            for value in obj.values():
                result = self._deep_find_product(value, depth + 1)
                if result:
                    return result

        elif isinstance(obj, list):
            for item in obj[:10]:  # Limit list traversal
                result = self._deep_find_product(item, depth + 1)
                if result:
                    return result

        return None

    def _extract_price_from_next_data(self, product: dict) -> float:
        """Extract price from various __NEXT_DATA__ structures."""
        # Path 1: priceInfo.currentPrice.price
        price_info = product.get("priceInfo", {})
        if isinstance(price_info, dict):
            current = price_info.get("currentPrice", {})
            if isinstance(current, dict):
                price = current.get("price", 0)
                if price and float(price) > 0:
                    return float(price)
            # priceInfo.priceRange
            price_range = price_info.get("priceRange", {})
            if isinstance(price_range, dict):
                min_price = price_range.get("minPrice", 0)
                if min_price and float(min_price) > 0:
                    return float(min_price)

        # Path 2: direct price field
        price = product.get("price", product.get("offerPrice", 0))
        if price:
            try:
                return float(price)
            except (ValueError, TypeError):
                pass

        # Path 3: buyBoxPrice or selectedVariantPrice
        for key in ("buyBoxPrice", "selectedVariantPrice", "wasPrice"):
            val = product.get(key, {})
            if isinstance(val, dict):
                p = val.get("price", val.get("amount", 0))
                if p and float(p) > 0:
                    return float(p)
            elif val:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass

        return 0.0

    def _extract_images_from_next_data(self, product: dict) -> list[str]:
        """Extract image URLs from __NEXT_DATA__ product object."""
        images = []
        seen = set()

        # Path 1: imageInfo.allImages
        image_info = product.get("imageInfo", {})
        if isinstance(image_info, dict):
            all_images = image_info.get("allImages", [])
            for img in all_images:
                if isinstance(img, dict):
                    url = img.get("url", "")
                elif isinstance(img, str):
                    url = img
                else:
                    continue
                if url and url not in seen:
                    images.append(self._to_large_image(url))
                    seen.add(url)

        # Path 2: images array
        if not images:
            for img in product.get("images", product.get("imageUrls", [])):
                url = img if isinstance(img, str) else img.get("url", "")
                if url and url not in seen:
                    images.append(self._to_large_image(url))
                    seen.add(url)

        # Path 3: primaryImage
        if not images:
            primary = product.get("primaryImage", product.get("thumbnailUrl", ""))
            if primary:
                images.append(self._to_large_image(primary))

        return images[:12]

    def _to_large_image(self, url: str) -> str:
        """Convert Walmart image URL to large version."""
        if not url or not url.startswith("http"):
            return url
        # Walmart images: replace size params with large version
        url = re.sub(r"\?.*$", "", url)  # Remove query params
        if "walmartimages.com" in url:
            # Ensure we get the large version
            url = re.sub(r"_\d+x\d+", "", url)
        return url

    def _extract_category_from_next_data(self, product: dict) -> str:
        """Extract category path from __NEXT_DATA__."""
        # Path 1: category.path
        categories = product.get("category", {})
        if isinstance(categories, dict):
            path = categories.get("path", [])
            if isinstance(path, list):
                names = [c.get("name", "") for c in path if isinstance(c, dict)]
                if names:
                    return " > ".join(n for n in names if n)

        # Path 2: breadcrumb
        breadcrumb = product.get("breadcrumb", product.get("taxonomyPath", []))
        if isinstance(breadcrumb, list):
            names = []
            for item in breadcrumb:
                if isinstance(item, dict):
                    names.append(item.get("name", item.get("text", "")))
                elif isinstance(item, str):
                    names.append(item)
            if names:
                return " > ".join(n for n in names if n)

        # Path 3: categoryPath string
        cat_path = product.get("categoryPath", "")
        if cat_path:
            return cat_path

        return ""

    def _extract_availability_from_next_data(self, product: dict) -> str:
        """Extract availability status from __NEXT_DATA__."""
        avail = product.get("availabilityStatus", "")
        if avail:
            return avail

        offer = product.get("offerType", "")
        if offer:
            return f"Available ({offer})"

        in_stock = product.get("inStock", product.get("isInStock", None))
        if in_stock is True:
            return "In Stock"
        elif in_stock is False:
            return "Out of Stock"

        return ""

    # ─── HTML Fallback ─────────────────────────────────────────

    def _extract_from_html(self, page_content: str) -> dict[str, Any]:
        """Fallback: extract product data from HTML using CSS selectors."""
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
        price_pattern = re.compile(r"\$?([\d,]+\.?\d*)")

        for selector in self.SELECTORS["price"]:
            elements = soup.select(selector)
            for element in elements:
                # Check content attribute first (for meta/itemprop)
                content = element.get("content", "")
                if content:
                    try:
                        price = float(content)
                        if price > 0:
                            return price
                    except ValueError:
                        pass

                text = element.get_text(strip=True)
                match = price_pattern.search(text)
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

    # ─── Bot Detection ─────────────────────────────────────────

    def _detect_bot_block(self, page_content: str) -> bool:
        """
        Detect Walmart-specific bot blocking patterns.

        Walmart uses:
        1. CAPTCHA challenges (PerimeterX)
        2. Access denied pages
        3. Rate limiting redirects
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
