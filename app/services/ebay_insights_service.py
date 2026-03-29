"""
eBay Marketplace Insights service.

Wraps the eBay Marketplace Insights API (v1 beta) to retrieve sold-item
data from the last 90 days.  Used by the auto-discovery flow to surface
trending products and validate demand before listing.

API endpoint:
    GET https://api.ebay.com/buy/marketplace_insights/v1_beta/item_sales/search

Authentication:
    Client Credentials grant (application-level, no user token required).
    Scope: https://api.ebay.com/oauth/api_scope/buy.marketplace.insights

Note:
    This API is marked "limited access" by eBay and may return 403 for
    applications that have not been granted access.  All public methods
    degrade gracefully in that scenario.
"""

import base64
import logging
import time
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────
INSIGHTS_API = "/buy/marketplace_insights/v1_beta/item_sales/search"
INSIGHTS_SCOPE = "https://api.ebay.com/oauth/api_scope/buy.marketplace.insights"

# Token is refreshed this many seconds before actual expiry to avoid
# clock-skew edge cases.
_TOKEN_REFRESH_MARGIN = 60


@dataclass
class SoldItemInsight:
    """A single sold-item record returned by the Marketplace Insights API."""

    title: str
    sold_price: float
    total_sold: int
    category_id: str
    image: str
    last_sold_date: str
    ebay_item_id: str


class EbayInsightsService:
    """
    Retrieves sold-item market data from eBay's Marketplace Insights API.

    Uses a client-credentials OAuth token (application-level) so no
    individual seller authorisation is required.

    Usage::

        svc = EbayInsightsService()
        if await svc.is_available():
            items = await svc.search_sold_items("vintage camera")
    """

    def __init__(self, settings=None):
        settings = settings or get_settings()
        self._app_id: str = settings.ebay_app_id
        self._cert_id: str = settings.ebay_cert_id
        self._base_url: str = settings.ebay_base_url

        # Cached client-credentials token
        self._token: str | None = None
        self._token_expiry: float = 0.0

    # ── OAuth (client credentials) ──────────────────────────────────────

    async def _get_client_token(self) -> str:
        """
        Obtain an OAuth client-credentials token for the Insights API.

        The token is cached in memory and re-used until it is close to
        expiry.  A new token is requested automatically when needed.

        Returns:
            A valid Bearer access token string.

        Raises:
            httpx.HTTPStatusError: If the token request fails.
        """
        if self._token and time.monotonic() < self._token_expiry:
            return self._token

        credentials = f"{self._app_id}:{self._cert_id}"
        encoded = base64.b64encode(credentials.encode()).decode()

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self._base_url}/identity/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope": INSIGHTS_SCOPE,
                },
            )

        if response.status_code != 200:
            logger.error(
                "Client-credentials token request failed: %s %s",
                response.status_code,
                response.text[:300],
            )
            response.raise_for_status()

        data = response.json()
        self._token = data["access_token"]
        expires_in = int(data.get("expires_in", 7200))
        self._token_expiry = time.monotonic() + expires_in - _TOKEN_REFRESH_MARGIN
        logger.info("Obtained Insights client token (expires_in=%ds)", expires_in)
        return self._token

    # ── Internal request helper ─────────────────────────────────────────

    async def _request(
        self,
        params: dict,
    ) -> dict | None:
        """
        Execute a GET against the Marketplace Insights search endpoint.

        Args:
            params: Query-string parameters to forward to the API.

        Returns:
            Parsed JSON response dict, or ``None`` if the API returned
            a 403 (limited-access) or another non-success status.
        """
        token = await self._get_client_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}{INSIGHTS_API}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                },
                params=params,
            )

        if response.status_code == 403:
            logger.warning(
                "Marketplace Insights API returned 403 — limited access. "
                "Ensure the application has been granted the buy.marketplace.insights scope."
            )
            return None

        if response.status_code != 200:
            logger.error(
                "Insights API error: %s %s",
                response.status_code,
                response.text[:300],
            )
            return None

        return response.json()

    # ── Response parsing ────────────────────────────────────────────────

    @staticmethod
    def _parse_items(data: dict | None) -> list[SoldItemInsight]:
        """
        Parse the Insights API response into a list of SoldItemInsight.

        Args:
            data: Raw JSON response from the API, or ``None``.

        Returns:
            A list of ``SoldItemInsight`` objects.  Returns an empty list
            when the API response is empty or unavailable.
        """
        if not data:
            return []

        items: list[SoldItemInsight] = []
        for record in data.get("itemSales", []):
            try:
                price_info = record.get("lastSoldPrice", {})
                image_info = record.get("image", {})
                category_ids = record.get("categoryId", "")

                items.append(
                    SoldItemInsight(
                        title=record.get("title", ""),
                        sold_price=float(price_info.get("value", 0)),
                        total_sold=int(record.get("totalSoldQuantity", 0)),
                        category_id=str(category_ids),
                        image=image_info.get("imageUrl", ""),
                        last_sold_date=record.get("lastSoldDate", ""),
                        ebay_item_id=record.get("epid", ""),
                    )
                )
            except (KeyError, ValueError, TypeError):
                logger.debug("Skipping unparseable Insights record: %s", record)
                continue

        return items

    # ── Public API ──────────────────────────────────────────────────────

    async def search_sold_items(
        self,
        query: str,
        category_ids: list[str] | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 50,
    ) -> list[SoldItemInsight]:
        """
        Search eBay sold items from the last 90 days.

        Args:
            query:        Keywords to search for (e.g. "vintage camera").
            category_ids: Optional list of eBay category IDs to narrow results.
            min_price:    Optional minimum sold price (USD) filter.
            max_price:    Optional maximum sold price (USD) filter.
            limit:        Maximum number of results to return (1-200).

        Returns:
            A list of ``SoldItemInsight`` objects sorted by most-recently
            sold.  Returns an empty list if the API is unavailable.
        """
        params: dict[str, str | int] = {
            "q": query,
            "limit": min(limit, 200),
        }

        if category_ids:
            params["category_ids"] = ",".join(category_ids)

        # Build filter string
        filters: list[str] = []
        if min_price is not None or max_price is not None:
            low = f"{min_price:.2f}" if min_price is not None else ""
            high = f"{max_price:.2f}" if max_price is not None else ""
            filters.append(f"price:[{low}..{high}]")
            filters.append("priceCurrency:USD")

        if filters:
            params["filter"] = ",".join(filters)

        params["sort"] = "-lastSoldDate"

        logger.info(
            "Searching sold items: q=%r categories=%s limit=%s",
            query,
            category_ids,
            limit,
        )
        data = await self._request(params)
        return self._parse_items(data)

    async def get_trending_in_category(
        self,
        category_id: str,
        limit: int = 20,
    ) -> list[SoldItemInsight]:
        """
        Get trending sold items in a specific eBay category.

        Results are sorted by total sold quantity (highest first) to
        surface the most in-demand products.

        Args:
            category_id: The eBay leaf or parent category ID.
            limit:       Maximum number of results to return (1-200).

        Returns:
            A list of ``SoldItemInsight`` objects sorted by popularity.
            Returns an empty list if the API is unavailable.
        """
        params: dict[str, str | int] = {
            "category_ids": category_id,
            "limit": min(limit, 200),
            "sort": "-totalSoldQuantity",
        }

        logger.info("Fetching trending items for category=%s limit=%s", category_id, limit)
        data = await self._request(params)
        return self._parse_items(data)

    async def is_available(self) -> bool:
        """
        Check whether the Marketplace Insights API is accessible.

        Makes a lightweight probe request.  Returns ``False`` if the API
        responds with 403 (limited access) or any other error.

        Returns:
            ``True`` if the API is reachable and returns data, ``False``
            otherwise.
        """
        try:
            data = await self._request({"q": "test", "limit": 1})
            return data is not None
        except Exception:
            logger.warning("Insights API availability check failed", exc_info=True)
            return False
