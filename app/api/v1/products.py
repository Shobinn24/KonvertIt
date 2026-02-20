"""
Product API endpoints.

Provides:
- POST /api/v1/products/scrape — Scrape a product from URL
- GET /api/v1/products — List user's scraped products
- GET /api/v1/products/{id} — Get product details

All endpoints require JWT authentication (Bearer token).
"""

import uuid

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import KonvertItError, ScrapingError
from app.db.database import get_db
from app.db.repositories.product_repo import ProductRepository
from app.middleware.auth_middleware import get_current_user
from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager
from app.services.conversion_service import ConversionService

router = APIRouter(prefix="/products", tags=["Products"])


# ─── Request/Response Schemas ──────────────────────────────


class ScrapeRequest(BaseModel):
    """Request body for product scraping."""
    url: str = Field(..., description="Source marketplace product URL to scrape")


class ProductResponse(BaseModel):
    """Product detail response."""
    id: str
    source_marketplace: str
    source_url: str
    source_product_id: str
    title: str
    price: float
    brand: str
    category: str
    image_urls: list
    scraped_at: str | None = None
    created_at: str | None = None


# ─── Endpoints ─────────────────────────────────────────────


@router.post("/scrape", summary="Scrape a product from URL")
async def scrape_product(
    request: ScrapeRequest,
    user: dict = Depends(get_current_user),
):
    """
    Scrape a product from a source marketplace URL.

    Returns the scraped product data including title, price, brand,
    images, description, and compliance status.

    Requires a valid access token in the Authorization header.
    """
    user_id = user["sub"]

    try:
        service = ConversionService(
            proxy_manager=ProxyManager(),
            browser_manager=BrowserManager(),
        )
        result = await service.preview_conversion(
            url=request.url,
            user_id=user_id,
        )

        if result.is_successful:
            return result.to_dict()
        else:
            raise HTTPException(
                status_code=422,
                detail=result.error or "Failed to scrape product",
            )

    except ScrapingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except KonvertItError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", summary="List scraped products")
async def list_products(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    marketplace: str | None = Query(default=None, description="Filter by source marketplace"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """
    List scraped products for the authenticated user.

    Supports filtering by source marketplace (amazon, walmart)
    and pagination via limit/offset.

    Requires a valid access token in the Authorization header.
    """
    user_id = uuid.UUID(user["sub"])
    repo = ProductRepository(db)
    products = await repo.find_by_user(
        user_id=user_id,
        marketplace=marketplace,
        limit=limit,
        offset=offset,
    )

    return {
        "products": [
            {
                "id": str(p.id),
                "source_marketplace": p.source_marketplace,
                "source_url": p.source_url,
                "source_product_id": p.source_product_id,
                "title": p.title,
                "price": p.price,
                "brand": p.brand,
                "category": p.category,
                "image_urls": p.image_urls,
                "scraped_at": p.scraped_at.isoformat() if p.scraped_at else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in products
        ],
        "total": len(products),
    }


@router.get("/{product_id}", summary="Get product details")
async def get_product(
    product_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get product details by ID.

    Only returns products belonging to the authenticated user (tenant isolation).

    Requires a valid access token in the Authorization header.
    """
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID format")

    user_id = uuid.UUID(user["sub"])
    repo = ProductRepository(db)
    product = await repo.get_by_id(pid)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # Tenant isolation: ensure product belongs to the authenticated user
    if product.user_id != user_id:
        raise HTTPException(status_code=404, detail="Product not found")

    return ProductResponse(
        id=str(product.id),
        source_marketplace=product.source_marketplace,
        source_url=product.source_url,
        source_product_id=product.source_product_id,
        title=product.title,
        price=product.price,
        brand=product.brand,
        category=product.category,
        image_urls=product.image_urls,
        scraped_at=product.scraped_at.isoformat() if product.scraped_at else None,
        created_at=product.created_at.isoformat() if product.created_at else None,
    )
