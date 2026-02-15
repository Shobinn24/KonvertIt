"""
Unit tests for EbayLister.

Tests eBay REST Inventory API integration including:
- Listing creation workflow (inventory item → offer → publish)
- Listing updates and price changes
- Error handling (auth failures, API errors)
- Payload building
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import EbayAuthError, ListingError
from app.core.models import (
    ListingDraft,
    ListingResult,
    ListingStatus,
    SourceMarketplace,
    TargetMarketplace,
)
from app.listers.ebay_lister import EbayLister


# ─── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def sample_draft() -> ListingDraft:
    """A sample listing draft for testing."""
    return ListingDraft(
        title="Anker USB C Charger 40W Nano Pro Compact",
        description_html="<p>Fast charger by Anker</p>",
        price=39.99,
        images=[
            "https://example.com/img1.jpg",
            "https://example.com/img2.jpg",
        ],
        category_id="67580",
        condition="New",
        sku="KI-B09C5RG6KV",
        quantity=1,
        target_marketplace=TargetMarketplace.EBAY,
        source_product_id="B09C5RG6KV",
        source_marketplace=SourceMarketplace.AMAZON,
    )


@pytest.fixture
def lister():
    """Create an EbayLister with a test token."""
    return EbayLister(
        access_token="test-token-12345",
        base_url="https://api.sandbox.ebay.com",
    )


@pytest.fixture
def lister_no_token():
    """Create an EbayLister without a token."""
    return EbayLister(access_token="")


# ─── Header Tests ──────────────────────────────────────────


class TestHeaders:
    """Tests for authentication headers."""

    def test_get_headers_with_token(self, lister):
        """Should build correct auth headers."""
        headers = lister._get_headers()
        assert headers["Authorization"] == "Bearer test-token-12345"
        assert headers["Content-Type"] == "application/json"
        assert headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"

    def test_get_headers_no_token_raises(self, lister_no_token):
        """Should raise EbayAuthError when no token configured."""
        with pytest.raises(EbayAuthError, match="No eBay access token"):
            lister_no_token._get_headers()


# ─── Payload Building Tests ───────────────────────────────


class TestPayloadBuilding:
    """Tests for eBay API payload construction."""

    def test_build_inventory_item(self, lister, sample_draft):
        """Should build correct inventory item payload."""
        item = lister._build_inventory_item(sample_draft)

        assert item["condition"] == "NEW"
        assert item["product"]["title"] == sample_draft.title
        assert item["product"]["description"] == sample_draft.description_html
        assert len(item["product"]["imageUrls"]) == 2
        assert item["availability"]["shipToLocationAvailability"]["quantity"] == 1
        assert item["sku"] == "KI-B09C5RG6KV"

    def test_build_offer(self, lister, sample_draft):
        """Should build correct offer payload."""
        offer = lister._build_offer(sample_draft, "KI-B09C5RG6KV")

        assert offer["sku"] == "KI-B09C5RG6KV"
        assert offer["marketplaceId"] == "EBAY_US"
        assert offer["format"] == "FIXED_PRICE"
        assert offer["pricingSummary"]["price"]["value"] == "39.99"
        assert offer["pricingSummary"]["price"]["currency"] == "USD"
        assert offer["categoryId"] == "67580"

    def test_build_offer_no_category(self, lister, sample_draft):
        """Should omit categoryId when not set."""
        sample_draft.category_id = ""
        offer = lister._build_offer(sample_draft, "KI-TEST")
        assert "categoryId" not in offer

    def test_map_condition(self, lister):
        """Should map conditions correctly."""
        assert lister._map_condition("New") == "NEW"
        assert lister._map_condition("like new") == "LIKE_NEW"
        assert lister._map_condition("refurbished") == "SELLER_REFURBISHED"
        assert lister._map_condition("for parts") == "FOR_PARTS_OR_NOT_WORKING"
        assert lister._map_condition("Unknown") == "NEW"  # Default

    def test_inventory_item_limits_images(self, lister, sample_draft):
        """Should limit images to 12."""
        sample_draft.images = [f"https://example.com/img{i}.jpg" for i in range(20)]
        item = lister._build_inventory_item(sample_draft)
        assert len(item["product"]["imageUrls"]) == 12


# ─── Create Listing Tests ────────────────────────────────


class TestCreateListing:
    """Tests for listing creation workflow."""

    @pytest.mark.asyncio
    async def test_create_listing_success(self, lister, sample_draft):
        """Should successfully create a listing through the 3-step workflow."""

        async def mock_request(method, path, json_data=None, expected_status=(200, 201, 204)):
            if method == "PUT" and "inventory_item" in path:
                return None  # 204 No Content
            elif method == "POST" and path.endswith("/offer"):
                return {"offerId": "offer-123"}
            elif method == "POST" and "publish" in path:
                return {"listingId": "987654321"}
            return {}

        with patch.object(lister, "_request", side_effect=mock_request):
            result = await lister.create_listing(sample_draft)

        assert isinstance(result, ListingResult)
        assert result.marketplace_item_id == "987654321"
        assert result.status == ListingStatus.ACTIVE
        assert "ebay.com" in result.url

    @pytest.mark.asyncio
    async def test_create_listing_auth_failure(self, lister, sample_draft):
        """Should propagate auth errors."""
        with patch.object(
            lister, "_request", side_effect=EbayAuthError("Token expired")
        ):
            with pytest.raises(EbayAuthError):
                await lister.create_listing(sample_draft)

    @pytest.mark.asyncio
    async def test_create_listing_api_error(self, lister, sample_draft):
        """Should propagate listing errors."""
        with patch.object(
            lister, "_request", side_effect=ListingError("API rate limit")
        ):
            with pytest.raises(ListingError):
                await lister.create_listing(sample_draft)

    @pytest.mark.asyncio
    async def test_create_listing_generates_sku(self, lister, sample_draft):
        """Should auto-generate SKU from source product ID."""
        sample_draft.sku = ""
        calls = []

        async def mock_request(method, path, json_data=None, expected_status=(200, 201, 204)):
            calls.append((method, path))
            if method == "POST" and path.endswith("/offer"):
                return {"offerId": "offer-123"}
            elif method == "POST" and "publish" in path:
                return {"listingId": "111222333"}
            return None

        with patch.object(lister, "_request", side_effect=mock_request):
            result = await lister.create_listing(sample_draft)

        # Should have used auto-generated SKU
        assert any("KI-B09C5RG6KV" in path for _, path in calls)


# ─── Update Listing Tests ────────────────────────────────


class TestUpdateListing:
    """Tests for listing update workflow."""

    @pytest.mark.asyncio
    async def test_update_listing_success(self, lister, sample_draft):
        """Should update inventory item and offer."""

        async def mock_request(method, path, json_data=None, expected_status=(200, 201, 204)):
            if method == "PUT" and "inventory_item" in path:
                return None
            elif method == "GET" and "offer" in path:
                return {"offers": [{"offerId": "offer-456"}]}
            elif method == "PUT" and "offer" in path:
                return None
            return {}

        with patch.object(lister, "_request", side_effect=mock_request):
            result = await lister.update_listing("987654321", sample_draft)

        assert result.marketplace_item_id == "987654321"
        assert result.status == ListingStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_update_listing_no_offers_found(self, lister, sample_draft):
        """Should raise error when no offers found for SKU."""

        async def mock_request(method, path, json_data=None, expected_status=(200, 201, 204)):
            if method == "PUT" and "inventory_item" in path:
                return None
            elif method == "GET" and "offer" in path:
                return {"offers": []}
            return {}

        with patch.object(lister, "_request", side_effect=mock_request):
            with pytest.raises(ListingError, match="No offers found"):
                await lister.update_listing("987654321", sample_draft)


# ─── End Listing Tests ────────────────────────────────────


class TestEndListing:
    """Tests for ending listings."""

    @pytest.mark.asyncio
    async def test_end_listing_success(self, lister):
        """Should withdraw the offer."""
        with patch.object(lister, "_request", return_value=None):
            result = await lister.end_listing("offer-123", reason="Out of stock")

        assert result is True

    @pytest.mark.asyncio
    async def test_end_listing_auth_failure(self, lister):
        """Should propagate auth errors on end."""
        with patch.object(
            lister, "_request", side_effect=EbayAuthError("Token expired")
        ):
            with pytest.raises(EbayAuthError):
                await lister.end_listing("offer-123")


# ─── Price Update Tests ──────────────────────────────────


class TestUpdatePrice:
    """Tests for quick price updates."""

    @pytest.mark.asyncio
    async def test_update_price_success(self, lister):
        """Should update offer price."""

        async def mock_request(method, path, json_data=None, expected_status=(200, 201, 204)):
            if method == "GET":
                return {
                    "offers": [{
                        "offerId": "offer-789",
                        "pricingSummary": {"price": {"value": "39.99", "currency": "USD"}},
                    }]
                }
            elif method == "PUT":
                return None
            return {}

        with patch.object(lister, "_request", side_effect=mock_request):
            result = await lister.update_price("KI-TEST", 44.99)

        assert result is True

    @pytest.mark.asyncio
    async def test_update_price_no_offers(self, lister):
        """Should raise error when no offers found."""
        with patch.object(
            lister, "_request", return_value={"offers": []}
        ):
            with pytest.raises(ListingError, match="No offers found"):
                await lister.update_price("KI-MISSING", 19.99)


# ─── Request Method Tests ────────────────────────────────


class TestRequestMethod:
    """Tests for the internal _request method."""

    @pytest.mark.asyncio
    async def test_request_401_raises_auth_error(self, lister):
        """Should raise EbayAuthError on 401 response."""
        mock_response = httpx.Response(
            status_code=401,
            text="Unauthorized",
            request=httpx.Request("GET", "https://api.sandbox.ebay.com/test"),
        )

        with patch("httpx.AsyncClient.request", return_value=mock_response):
            with pytest.raises(EbayAuthError, match="expired or invalid"):
                await lister._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_request_unexpected_status_raises_listing_error(self, lister):
        """Should raise ListingError on unexpected status code."""
        mock_response = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", "https://api.sandbox.ebay.com/test"),
        )

        with patch("httpx.AsyncClient.request", return_value=mock_response):
            with pytest.raises(ListingError, match="eBay API error"):
                await lister._request("POST", "/test", expected_status=(200,))

    @pytest.mark.asyncio
    async def test_request_204_returns_none(self, lister):
        """Should return None for 204 No Content."""
        mock_response = httpx.Response(
            status_code=204,
            request=httpx.Request("PUT", "https://api.sandbox.ebay.com/test"),
        )

        with patch("httpx.AsyncClient.request", return_value=mock_response):
            result = await lister._request("PUT", "/test")
            assert result is None

    @pytest.mark.asyncio
    async def test_request_200_returns_json(self, lister):
        """Should return parsed JSON for 200 responses."""
        mock_response = httpx.Response(
            status_code=200,
            json={"offerId": "test-offer"},
            request=httpx.Request("POST", "https://api.sandbox.ebay.com/test"),
        )

        with patch("httpx.AsyncClient.request", return_value=mock_response):
            result = await lister._request("POST", "/test")
            assert result == {"offerId": "test-offer"}

    @pytest.mark.asyncio
    async def test_request_error_with_json_details(self, lister):
        """Should parse error details from JSON response."""
        mock_response = httpx.Response(
            status_code=400,
            json={"errors": [{"message": "Invalid SKU format"}]},
            request=httpx.Request("POST", "https://api.sandbox.ebay.com/test"),
        )

        with patch("httpx.AsyncClient.request", return_value=mock_response):
            with pytest.raises(ListingError, match="Invalid SKU format"):
                await lister._request("POST", "/test", expected_status=(200,))
