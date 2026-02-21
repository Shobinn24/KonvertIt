"""
Product discovery service.

Searches Amazon and Walmart via ScraperAPI structured search endpoints
and returns normalized results for frontend display.

Endpoints used:
- Amazon: GET https://api.scraperapi.com/structured/amazon/search
- Walmart: GET https://api.scraperapi.com/structured/walmart/search
"""

import logging
import re
from dataclasses import asdict, dataclass
from urllib.parse import unquote

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

AMAZON_SEARCH_URL = "https://api.scraperapi.com/structured/amazon/search"
WALMART_SEARCH_URL = "https://api.scraperapi.com/structured/walmart/search"

# ASIN regex: matches /dp/ASIN or /gp/product/ASIN (10-char alphanumeric)
_ASIN_PATTERN = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})")


def _extract_asin(url: str) -> str | None:
    """
    Extract an Amazon ASIN from a URL.

    Handles:
    - Clean product URLs: /dp/B0C2C9NHZW
    - Sponsored redirect URLs: /sspa/click?...url=%2Fdp%2FB0C2C9NHZW...
    - URL-encoded variants in query params

    Returns the ASIN string or None if not extractable.
    """
    # First try the raw URL
    match = _ASIN_PATTERN.search(url)
    if match:
        return match.group(1)

    # For /sspa/click and other redirect URLs, URL-decode and search again.
    # These URLs embed the destination product URL in query parameters.
    decoded = unquote(url)
    if decoded != url:
        match = _ASIN_PATTERN.search(decoded)
        if match:
            return match.group(1)

    # Fallback: scan URL segments for a bare 10-char alphanumeric token
    for part in url.split("/"):
        # Strip query string from the segment
        token = part.split("?")[0]
        if re.fullmatch(r"[A-Z0-9]{10}", token):
            return token

    return None


def _normalize_amazon_url(raw_url: str) -> str | None:
    """
    Normalize an Amazon URL to a clean canonical form.

    Converts any Amazon URL (including sponsored redirects) to
    https://www.amazon.com/dp/{ASIN}.

    Returns the canonical URL or None if the URL can't be normalized
    (e.g., ad tracking URLs with no embedded product info).
    """
    asin = _extract_asin(raw_url)
    if asin:
        return f"https://www.amazon.com/dp/{asin}"
    return None


@dataclass
class DiscoveryProduct:
    """Normalized product from a search result."""

    name: str
    price: float
    price_symbol: str
    image: str
    url: str
    stars: float | None
    total_reviews: int | None
    is_prime: bool
    is_best_seller: bool
    is_amazons_choice: bool
    seller: str
    marketplace: str  # "amazon" or "walmart"


@dataclass
class DiscoveryResponse:
    """Normalized search response across marketplaces."""

    products: list[DiscoveryProduct]
    page: int
    total_pages: int | None
    marketplace: str
    query: str

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "products": [asdict(p) for p in self.products],
            "page": self.page,
            "total_pages": self.total_pages,
            "marketplace": self.marketplace,
            "query": self.query,
        }


class DiscoveryService:
    """Searches Amazon/Walmart via ScraperAPI structured search endpoints."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.scraper_api_key

    async def search(
        self,
        query: str,
        marketplace: str = "amazon",
        page: int = 1,
    ) -> DiscoveryResponse:
        """
        Search for products by keyword.

        Args:
            query: Search keywords.
            marketplace: "amazon" or "walmart".
            page: Result page number (1-indexed).

        Returns:
            Normalized DiscoveryResponse with products list.

        Raises:
            ValueError: If marketplace is unsupported or API key missing.
            RuntimeError: If ScraperAPI returns 429.
            httpx.HTTPStatusError: On other HTTP errors.
        """
        if not self._api_key:
            raise ValueError("ScraperAPI key not configured")

        if marketplace == "amazon":
            return await self._search_amazon(query, page)
        elif marketplace == "walmart":
            return await self._search_walmart(query, page)
        else:
            raise ValueError(f"Unsupported marketplace: {marketplace}")

    async def _search_amazon(self, query: str, page: int) -> DiscoveryResponse:
        """Search Amazon via ScraperAPI structured search endpoint."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                AMAZON_SEARCH_URL,
                params={
                    "api_key": self._api_key,
                    "query": query,
                    "page": page,
                    "tld": "com",
                },
            )

        if response.status_code == 429:
            raise RuntimeError("ScraperAPI rate limit exceeded. Try again later.")
        response.raise_for_status()
        data = response.json()

        products: list[DiscoveryProduct] = []
        skipped = 0
        for item in data.get("results", []):
            # Normalize the URL to a clean /dp/{ASIN} form.
            # Sponsored ads return /sspa/click?... or aax-* tracking URLs
            # that the conversion scraper cannot process.
            raw_url = item.get("url", "")
            clean_url = _normalize_amazon_url(raw_url) if raw_url else None
            if not clean_url:
                skipped += 1
                logger.debug(
                    f"Skipping product with un-normalizable URL: {raw_url[:120]}"
                )
                continue

            price = item.get("price")
            if price is None:
                # Try parsing from price_string (e.g. "$29.99")
                price_str = item.get("price_string", "")
                try:
                    price = float(price_str.replace("$", "").replace(",", "").strip())
                except (ValueError, AttributeError):
                    price = 0.0

            products.append(
                DiscoveryProduct(
                    name=item.get("name", ""),
                    price=price,
                    price_symbol=item.get("price_symbol", "$"),
                    image=item.get("image", ""),
                    url=clean_url,
                    stars=item.get("stars"),
                    total_reviews=item.get("total_reviews"),
                    is_prime=bool(item.get("has_prime", False)),
                    is_best_seller=bool(item.get("is_best_seller", False)),
                    is_amazons_choice=bool(item.get("is_amazon_choice", False)),
                    seller="",
                    marketplace="amazon",
                )
            )

        if skipped:
            logger.info(
                f"Amazon search: skipped {skipped} products with "
                f"un-normalizable URLs (sponsored/ad tracking)"
            )

        # Determine total pages from pagination data
        pagination = data.get("pagination", {})
        pages_list = pagination.get("pages", [])
        total_pages = len(pages_list) if pages_list else None

        logger.info(
            f"Amazon search: query={query!r} page={page} results={len(products)}"
        )

        return DiscoveryResponse(
            products=products,
            page=page,
            total_pages=total_pages,
            marketplace="amazon",
            query=query,
        )

    async def _search_walmart(self, query: str, page: int) -> DiscoveryResponse:
        """Search Walmart via ScraperAPI structured search endpoint."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                WALMART_SEARCH_URL,
                params={
                    "api_key": self._api_key,
                    "query": query,
                    "page": page,
                },
            )

        if response.status_code == 429:
            raise RuntimeError("ScraperAPI rate limit exceeded. Try again later.")
        response.raise_for_status()
        data = response.json()

        products: list[DiscoveryProduct] = []
        for item in data.get("items", []):
            rating = item.get("rating") or {}
            price = item.get("price")
            if price is None:
                price = 0.0

            products.append(
                DiscoveryProduct(
                    name=item.get("name", ""),
                    price=float(price),
                    price_symbol="$",
                    image=item.get("image", ""),
                    url=item.get("url", ""),
                    stars=rating.get("average_rating"),
                    total_reviews=rating.get("number_of_reviews"),
                    is_prime=False,
                    is_best_seller=False,
                    is_amazons_choice=False,
                    seller=item.get("seller", ""),
                    marketplace="walmart",
                )
            )

        meta = data.get("meta", {})
        total_pages = meta.get("pages")

        logger.info(
            f"Walmart search: query={query!r} page={page} results={len(products)}"
        )

        return DiscoveryResponse(
            products=products,
            page=meta.get("page", page),
            total_pages=total_pages,
            marketplace="walmart",
            query=query,
        )
