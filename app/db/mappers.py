"""
Pydantic ↔ ORM mapping helpers for KonvertIt.

Converts between pipeline Pydantic models (ScrapedProduct, ListingDraft,
ListingResult) and SQLAlchemy ORM models (Product, Listing, Conversion).

These mappers bridge the domain layer and persistence layer, keeping
both layers decoupled from each other.

Usage:
    from app.db.mappers import product_from_scraped, listing_from_draft

    product_orm = product_from_scraped(scraped, user_id=user.id)
    listing_orm = listing_from_draft(draft, user_id=user.id)
"""

import uuid
from datetime import UTC, datetime

from app.core.models import (
    ListingDraft,
    ListingResult,
    ScrapedProduct,
    SourceMarketplace,
)
from app.db.models import Conversion, Listing, Product


def product_from_scraped(
    scraped: ScrapedProduct,
    user_id: uuid.UUID,
) -> Product:
    """
    Map a ScrapedProduct Pydantic model to a Product ORM model.

    Args:
        scraped: Pipeline-produced scraped product data.
        user_id: Owner user ID for multi-tenant isolation.

    Returns:
        A new (unsaved) Product ORM instance ready for session.add().
    """
    return Product(
        user_id=user_id,
        source_marketplace=scraped.source_marketplace.value,
        source_url=scraped.source_url,
        source_product_id=scraped.source_product_id,
        title=scraped.title,
        price=scraped.price,
        brand=scraped.brand,
        category=scraped.category,
        image_urls=scraped.images,
        raw_data=scraped.raw_data,
        scraped_at=scraped.scraped_at,
    )


def scraped_from_product(product: Product) -> ScrapedProduct:
    """
    Map a Product ORM model back to a ScrapedProduct Pydantic model.

    Handles None values from the database by substituting safe defaults,
    since ORM columns may be nullable while Pydantic fields have defaults.

    Args:
        product: Product ORM instance loaded from database.

    Returns:
        ScrapedProduct Pydantic model.
    """
    return ScrapedProduct(
        title=product.title,
        price=product.price,
        brand=product.brand or "",
        images=product.image_urls if isinstance(product.image_urls, list) else [],
        category=product.category or "",
        source_marketplace=SourceMarketplace(product.source_marketplace),
        source_url=product.source_url,
        source_product_id=product.source_product_id,
        raw_data=product.raw_data if isinstance(product.raw_data, dict) else {},
        scraped_at=product.scraped_at or datetime.now(UTC),
    )


def listing_from_draft(
    draft: ListingDraft,
    user_id: uuid.UUID,
    listing_result: ListingResult | None = None,
) -> Listing:
    """
    Map a ListingDraft + optional ListingResult to a Listing ORM model.

    Args:
        draft: Pipeline-produced listing draft.
        user_id: Owner user ID for multi-tenant isolation.
        listing_result: If provided, includes eBay item ID and status.

    Returns:
        A new (unsaved) Listing ORM instance ready for session.add().
    """
    listing = Listing(
        user_id=user_id,
        title=draft.title,
        description_html=draft.description_html,
        price=draft.price,
        status="draft",
    )

    if listing_result:
        listing.ebay_item_id = listing_result.marketplace_item_id or None
        listing.status = listing_result.status.value
        if listing_result.status.value == "active":
            from datetime import UTC, datetime

            listing.listed_at = datetime.now(UTC)

    return listing


def conversion_from_result(
    user_id: uuid.UUID,
    product_id: uuid.UUID,
    status: str,
    listing_id: uuid.UUID | None = None,
    error_message: str | None = None,
) -> Conversion:
    """
    Create a Conversion ORM record from pipeline result data.

    Args:
        user_id: Owner user ID.
        product_id: FK to the persisted Product.
        status: Conversion status string (pending, processing, completed, failed).
        listing_id: FK to the persisted Listing (if created).
        error_message: Error details for failed conversions.

    Returns:
        A new (unsaved) Conversion ORM instance ready for session.add().
    """
    conversion = Conversion(
        user_id=user_id,
        product_id=product_id,
        listing_id=listing_id,
        status=status,
        error_message=error_message,
    )

    if status == "completed":
        from datetime import UTC, datetime

        conversion.converted_at = datetime.now(UTC)

    return conversion
