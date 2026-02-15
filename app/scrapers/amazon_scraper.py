"""
Amazon product page scraper.

Extracts product data from Amazon product pages (amazon.com/dp/{ASIN})
using BeautifulSoup with Playwright for JavaScript-rendered content.
"""

import logging
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.core.exceptions import CaptchaDetectedError, DogPageError
from app.core.models import ScrapedProduct, SourceMarketplace
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# ASIN regex pattern: 10-character alphanumeric
ASIN_PATTERN = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})")

# Price patterns
PRICE_PATTERN = re.compile(r"\$?([\d,]+\.?\d*)")


class AmazonScraper(BaseScraper):
    """
    Scraper for Amazon product pages.

    Handles:
    - Multiple price formats (whole, deal, range)
    - Dog page detection (minimal HTML bot block)
    - CAPTCHA detection
    - High-resolution image URL conversion
    - ASIN extraction from URL or page content
    """

    SOURCE_NAME = "amazon"

    # ─── CSS Selectors ────────────────────────────────────────

    SELECTORS = {
        "title": [
            "#productTitle",
            "span#title",
            "#title_feature_div span",
            "h1#title span",
        ],
        "price": [
            ".a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            ".a-price-whole",
            "#corePrice_feature_div .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-offscreen",
            "span.a-color-price",
        ],
        "brand": [
            "#bylineInfo",
            "a#brand",
            "#brand",
            "tr.po-brand td.a-span9 span",
        ],
        "images": [
            "#imgTagWrapperId img",
            "#landingImage",
            "#imgBlkFront",
            ".imgTagWrapper img",
        ],
        "description": [
            "#feature-bullets",
            "#productDescription",
            "#aplus_feature_div",
        ],
        "category": [
            "#wayfinding-breadcrumbs_feature_div",
            ".a-breadcrumb",
        ],
        "availability": [
            "#availability span",
            "#availability",
        ],
    }

    # ─── Extraction ───────────────────────────────────────────

    def _extract(self, page_content: str) -> dict[str, Any]:
        """Extract raw product data from Amazon page HTML."""
        soup = BeautifulSoup(page_content, "lxml")

        return {
            "title": self._extract_title(soup),
            "price": self._extract_price(soup),
            "brand": self._extract_brand(soup),
            "images": self._extract_images(soup),
            "description": self._extract_description(soup),
            "category": self._extract_category(soup),
            "availability": self._extract_availability(soup),
            "page_length": len(page_content),
        }

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract product title."""
        for selector in self.SELECTORS["title"]:
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                return element.get_text(strip=True)
        return ""

    def _extract_price(self, soup: BeautifulSoup) -> float:
        """
        Extract product price, handling multiple Amazon price formats.

        Handles: whole price, deal price, range prices (takes lowest),
        and various Amazon price block structures.
        """
        for selector in self.SELECTORS["price"]:
            elements = soup.select(selector)
            for element in elements:
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

    def _extract_brand(self, soup: BeautifulSoup) -> str:
        """Extract brand name."""
        for selector in self.SELECTORS["brand"]:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                # Clean common prefixes
                for prefix in ["Visit the ", "Brand: ", "by "]:
                    if text.startswith(prefix):
                        text = text[len(prefix):]
                # Remove " Store" suffix
                if text.endswith(" Store"):
                    text = text[:-6]
                if text:
                    return text.strip()
        return ""

    def _extract_images(self, soup: BeautifulSoup) -> list[str]:
        """
        Extract product image URLs, converting to high-resolution versions.

        Amazon image URLs contain size parameters that can be modified
        to get full-resolution images.
        """
        images = []
        seen = set()

        for selector in self.SELECTORS["images"]:
            elements = soup.select(selector)
            for element in elements:
                # Try data-old-hires first (high-res), then src
                url = (
                    element.get("data-old-hires")
                    or element.get("data-a-dynamic-image", "")
                    or element.get("src", "")
                )

                if not url or url in seen:
                    continue

                # Handle data-a-dynamic-image (JSON-like dict of URLs)
                if url.startswith("{"):
                    import json
                    try:
                        url_dict = json.loads(url)
                        # Get the highest resolution URL
                        for img_url in url_dict:
                            clean = self._to_high_res(img_url)
                            if clean and clean not in seen:
                                images.append(clean)
                                seen.add(clean)
                    except json.JSONDecodeError:
                        pass
                    continue

                # Skip 1x1 pixel tracking images
                if "1x1" in url or "pixel" in url:
                    continue

                clean = self._to_high_res(url)
                if clean and clean not in seen:
                    images.append(clean)
                    seen.add(clean)

        return images[:12]  # eBay allows max 12 images

    def _to_high_res(self, url: str) -> str:
        """
        Convert Amazon image URL to high-resolution version.

        Amazon URLs like: ...._SX300_.jpg can be changed to ...._SL1500_.jpg
        """
        if not url or not url.startswith("http"):
            return ""
        # Remove size parameters to get original resolution
        url = re.sub(r"\._[A-Z]{2}\d+_\.", "._SL1500_.", url)
        return url

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract product description from bullet points or description block."""
        for selector in self.SELECTORS["description"]:
            element = soup.select_one(selector)
            if element:
                # For feature bullets, join all list items
                bullets = element.select("li span.a-list-item")
                if bullets:
                    points = [b.get_text(strip=True) for b in bullets if b.get_text(strip=True)]
                    if points:
                        return " | ".join(points)

                text = element.get_text(strip=True)
                if text and len(text) > 10:
                    return text
        return ""

    def _extract_category(self, soup: BeautifulSoup) -> str:
        """Extract product category from breadcrumb navigation."""
        for selector in self.SELECTORS["category"]:
            element = soup.select_one(selector)
            if element:
                links = element.select("a")
                if links:
                    categories = [a.get_text(strip=True) for a in links if a.get_text(strip=True)]
                    return " > ".join(categories)
        return ""

    def _extract_availability(self, soup: BeautifulSoup) -> str:
        """Extract availability status."""
        for selector in self.SELECTORS["availability"]:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text:
                    return text
        return ""

    # ─── Transform & Validate ─────────────────────────────────

    def _transform(self, raw_data: dict[str, Any], url: str) -> ScrapedProduct:
        """Transform raw extracted data into a ScrapedProduct."""
        asin = self._extract_asin(url)

        return ScrapedProduct(
            title=raw_data.get("title", ""),
            price=raw_data.get("price", 0.0),
            brand=raw_data.get("brand", ""),
            images=raw_data.get("images", []),
            description=raw_data.get("description", ""),
            category=raw_data.get("category", ""),
            availability=raw_data.get("availability", ""),
            source_marketplace=SourceMarketplace.AMAZON,
            source_url=url,
            source_product_id=asin,
            raw_data=raw_data,
        )

    def _extract_asin(self, url: str) -> str:
        """Extract ASIN from Amazon product URL."""
        match = ASIN_PATTERN.search(url)
        if match:
            return match.group(1)
        # Fallback: try to find 10-char alphanumeric in URL
        parts = url.split("/")
        for part in parts:
            if re.match(r"^[A-Z0-9]{10}$", part):
                return part
        return ""

    # ─── URL Cleaning ─────────────────────────────────────────

    def _clean_url(self, url: str) -> str:
        """
        Normalize Amazon URL to minimal canonical form.

        Strips tracking parameters (ref, pd_rd_*, pf_rd_*, content-id, etc.)
        and reduces to https://www.amazon.com/dp/{ASIN} format.
        This avoids timeouts from overly long URLs and reduces fingerprinting.
        """
        asin = self._extract_asin(url)
        if asin:
            # Reconstruct clean canonical URL
            parsed = urlparse(url)
            host = parsed.netloc or "www.amazon.com"
            clean = f"https://{host}/dp/{asin}"
            logger.debug(f"Cleaned Amazon URL: {url[:80]}... → {clean}")
            return clean
        # Fallback: return original if ASIN not found
        return url

    # ─── Bot Detection ────────────────────────────────────────

    def _detect_bot_block(self, page_content: str) -> bool:
        """
        Detect Amazon-specific bot blocking patterns.

        Amazon uses:
        1. 'Dog pages' — minimal HTML with an image of a dog
        2. CAPTCHA challenges
        3. Extremely short pages (< 10KB usually means blocked)
        """
        content_lower = page_content.lower()

        # CAPTCHA detection
        if "captcha" in content_lower or "enter the characters" in content_lower:
            raise CaptchaDetectedError(
                "Amazon CAPTCHA detected",
                details={"content_length": len(page_content)},
            )

        # Dog page detection (Amazon's cute but frustrating bot block)
        dog_indicators = [
            "sorry, we just need to make sure you're not a robot",
            "to discuss automated access",
            "api-services-support@amazon.com",
        ]
        if any(indicator in content_lower for indicator in dog_indicators):
            raise DogPageError(
                "Amazon dog page detected (bot block)",
                details={"content_length": len(page_content)},
            )

        # Suspiciously short page (likely blocked)
        if len(page_content) < 10000:
            logger.warning(
                f"Amazon returned unusually short page ({len(page_content)} bytes). "
                "Possible bot detection."
            )
            return True

        return False
