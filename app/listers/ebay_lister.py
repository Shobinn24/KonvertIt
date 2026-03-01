"""
eBay listing creation and management via the eBay REST Inventory API.

Implements the Sell APIs workflow:
1. Create/update inventory item (PUT /sell/inventory/v1/inventory_item/{sku})
2. Create offer (POST /sell/inventory/v1/offer)
3. Publish offer (POST /sell/inventory/v1/offer/{offerId}/publish)

Supports listing creation, updates, price changes, and ending listings.
"""

import logging
from datetime import UTC, datetime

import httpx

from app.core.exceptions import EbayAuthError, ListingError
from app.core.interfaces import IListable
from app.core.models import ListingDraft, ListingResult, ListingStatus

logger = logging.getLogger(__name__)

# eBay Sell Inventory API base paths
INVENTORY_API = "/sell/inventory/v1"
MARKETPLACE_ID = "EBAY_US"


class EbayLister(IListable):
    """
    Creates and manages eBay listings via the official eBay REST Inventory API.

    Workflow:
    1. Create inventory item with product details
    2. Create an offer linking the item to a marketplace
    3. Publish the offer to make it live

    Requires a valid user OAuth token from EbayAuth.
    """

    def __init__(
        self,
        access_token: str = "",
        base_url: str = "https://api.ebay.com",
        marketplace_id: str = MARKETPLACE_ID,
        fulfillment_policy_id: str = "",
        payment_policy_id: str = "",
        return_policy_id: str = "",
    ):
        self._access_token = access_token
        self._base_url = base_url
        self._marketplace_id = marketplace_id
        self._fulfillment_policy_id = fulfillment_policy_id
        self._payment_policy_id = payment_policy_id
        self._return_policy_id = return_policy_id

    def _get_headers(self) -> dict[str, str]:
        """Build authorization and content headers."""
        if not self._access_token:
            raise EbayAuthError("No eBay access token configured")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Content-Language": "en-US",
            "Accept": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
        }

    async def _request(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
        expected_status: tuple[int, ...] = (200, 201, 204),
    ) -> dict | None:
        """Make an authenticated request to the eBay API."""
        url = f"{self._base_url}{path}"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
            )

        if response.status_code == 401:
            raise EbayAuthError(
                "eBay access token expired or invalid",
                details={"status": 401, "response": response.text},
            )

        if response.status_code not in expected_status:
            error_detail = response.text
            try:
                error_json = response.json()
                errors = error_json.get("errors", [])
                if errors:
                    error_detail = "; ".join(
                        e.get("message", str(e)) for e in errors
                    )
            except Exception:
                pass

            raise ListingError(
                f"eBay API error ({response.status_code}): {error_detail}",
                details={
                    "status": response.status_code,
                    "path": path,
                    "method": method,
                },
            )

        if response.status_code == 204:
            return None
        return response.json()

    def _build_inventory_item(self, draft: ListingDraft) -> dict:
        """Build the eBay inventory item payload from a listing draft."""
        item = {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": draft.quantity,
                },
            },
            "condition": self._map_condition(draft.condition),
            "product": {
                "title": draft.title,
                "description": draft.description_html,
                "imageUrls": draft.images[:12],
            },
        }

        if draft.sku:
            item["sku"] = draft.sku

        return item

    def _build_offer(self, draft: ListingDraft, sku: str) -> dict:
        """Build the eBay offer payload."""
        offer = {
            "sku": sku,
            "marketplaceId": self._marketplace_id,
            "format": "FIXED_PRICE",
            "listingDescription": draft.description_html,
            "pricingSummary": {
                "price": {
                    "value": f"{draft.price:.2f}",
                    "currency": draft.currency,
                },
            },
            "quantityLimitPerBuyer": 5,
            "listingPolicies": {
                "fulfillmentPolicyId": self._fulfillment_policy_id,
                "paymentPolicyId": self._payment_policy_id,
                "returnPolicyId": self._return_policy_id,
            },
        }

        if draft.category_id:
            offer["categoryId"] = draft.category_id

        return offer

    def _map_condition(self, condition: str) -> str:
        """Map our condition string to eBay's condition enum."""
        condition_map = {
            "new": "NEW",
            "like new": "LIKE_NEW",
            "very good": "VERY_GOOD",
            "good": "GOOD",
            "acceptable": "ACCEPTABLE",
            "refurbished": "SELLER_REFURBISHED",
            "for parts": "FOR_PARTS_OR_NOT_WORKING",
        }
        return condition_map.get(condition.lower(), "NEW")

    async def create_listing(self, draft: ListingDraft) -> ListingResult:
        """
        Create a new eBay listing from a draft.

        Follows the eBay Inventory API workflow:
        1. Create/update inventory item
        2. Create offer
        3. Publish offer

        Args:
            draft: The listing draft to publish.

        Returns:
            ListingResult with eBay item ID and status.
        """
        sku = draft.sku or f"KI-{draft.source_product_id}"
        logger.info(f"Creating eBay listing for SKU: {sku}")

        try:
            # Step 1: Create or update inventory item
            inventory_payload = self._build_inventory_item(draft)
            await self._request(
                "PUT",
                f"{INVENTORY_API}/inventory_item/{sku}",
                json_data=inventory_payload,
                expected_status=(200, 201, 204),
            )
            logger.info(f"Inventory item created/updated: {sku}")

            # Step 2: Create offer
            offer_payload = self._build_offer(draft, sku)
            offer_response = await self._request(
                "POST",
                f"{INVENTORY_API}/offer",
                json_data=offer_payload,
                expected_status=(200, 201),
            )
            offer_id = offer_response.get("offerId", "") if offer_response else ""
            logger.info(f"Offer created: {offer_id}")

            # Step 3: Publish offer
            publish_response = await self._request(
                "POST",
                f"{INVENTORY_API}/offer/{offer_id}/publish",
                expected_status=(200,),
            )
            listing_id = publish_response.get("listingId", "") if publish_response else ""
            logger.info(f"Listing published: {listing_id}")

            return ListingResult(
                marketplace_item_id=listing_id,
                status=ListingStatus.ACTIVE,
                url=f"https://www.ebay.com/itm/{listing_id}" if listing_id else "",
                created_at=datetime.now(UTC),
            )

        except EbayAuthError:
            raise
        except ListingError:
            raise
        except Exception as e:
            raise ListingError(
                f"Failed to create eBay listing: {e}",
                details={"sku": sku, "error_type": type(e).__name__},
            ) from e

    async def update_listing(self, listing_id: str, draft: ListingDraft) -> ListingResult:
        """
        Update an existing eBay listing.

        Updates the inventory item and revises the offer price/details.
        """
        sku = draft.sku or f"KI-{draft.source_product_id}"
        logger.info(f"Updating eBay listing {listing_id} (SKU: {sku})")

        try:
            # Update inventory item
            inventory_payload = self._build_inventory_item(draft)
            await self._request(
                "PUT",
                f"{INVENTORY_API}/inventory_item/{sku}",
                json_data=inventory_payload,
                expected_status=(200, 201, 204),
            )

            # Get existing offers for this SKU to find the offer ID
            offers_response = await self._request(
                "GET",
                f"{INVENTORY_API}/offer?sku={sku}",
                expected_status=(200,),
            )

            offers = offers_response.get("offers", []) if offers_response else []
            if not offers:
                raise ListingError(
                    f"No offers found for SKU {sku}",
                    details={"listing_id": listing_id, "sku": sku},
                )

            offer_id = offers[0].get("offerId", "")
            offer_payload = self._build_offer(draft, sku)
            await self._request(
                "PUT",
                f"{INVENTORY_API}/offer/{offer_id}",
                json_data=offer_payload,
                expected_status=(200, 204),
            )

            logger.info(f"Listing {listing_id} updated successfully")

            return ListingResult(
                marketplace_item_id=listing_id,
                status=ListingStatus.ACTIVE,
                url=f"https://www.ebay.com/itm/{listing_id}",
                created_at=datetime.now(UTC),
            )

        except (EbayAuthError, ListingError):
            raise
        except Exception as e:
            raise ListingError(
                f"Failed to update eBay listing {listing_id}: {e}",
                details={"listing_id": listing_id, "error_type": type(e).__name__},
            ) from e

    async def end_listing(self, listing_id: str, reason: str = "") -> bool:
        """
        End an eBay listing by withdrawing its offer.
        """
        logger.info(f"Ending eBay listing {listing_id} (reason: {reason or 'none'})")

        try:
            await self._request(
                "POST",
                f"{INVENTORY_API}/offer/{listing_id}/withdraw",
                expected_status=(200, 204),
            )
            logger.info(f"Listing {listing_id} ended successfully")
            return True

        except (EbayAuthError, ListingError):
            raise
        except Exception as e:
            raise ListingError(
                f"Failed to end eBay listing {listing_id}: {e}",
                details={"listing_id": listing_id, "error_type": type(e).__name__},
            ) from e

    async def update_price(self, sku: str, new_price: float, currency: str = "USD") -> bool:
        """Quick price update for an existing listing."""
        logger.info(f"Updating price for SKU {sku}: ${new_price:.2f}")

        try:
            offers_response = await self._request(
                "GET",
                f"{INVENTORY_API}/offer?sku={sku}",
                expected_status=(200,),
            )

            offers = offers_response.get("offers", []) if offers_response else []
            if not offers:
                raise ListingError(f"No offers found for SKU {sku}")

            offer_id = offers[0].get("offerId", "")
            offer = offers[0]

            offer["pricingSummary"] = {
                "price": {
                    "value": f"{new_price:.2f}",
                    "currency": currency,
                },
            }

            await self._request(
                "PUT",
                f"{INVENTORY_API}/offer/{offer_id}",
                json_data=offer,
                expected_status=(200, 204),
            )

            logger.info(f"Price updated for SKU {sku}: ${new_price:.2f}")
            return True

        except (EbayAuthError, ListingError):
            raise
        except Exception as e:
            raise ListingError(
                f"Failed to update price for SKU {sku}: {e}",
                details={"sku": sku, "error_type": type(e).__name__},
            ) from e
