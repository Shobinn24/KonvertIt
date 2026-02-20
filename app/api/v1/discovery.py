"""
Product discovery API endpoints.

Provides:
- GET /api/v1/discover/search — Search for products on Amazon or Walmart

Searches are free (do not count against conversion rate limits).
Uses ScraperAPI structured search endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.middleware.auth_middleware import get_current_user
from app.services.discovery_service import DiscoveryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover", tags=["Discovery"])


# ─── Response Models ──────────────────────────────────────────


class DiscoveryProductResponse(BaseModel):
    """A single product from search results."""

    name: str
    price: float
    price_symbol: str = "$"
    image: str = ""
    url: str = ""
    stars: float | None = None
    total_reviews: int | None = None
    is_prime: bool = False
    is_best_seller: bool = False
    is_amazons_choice: bool = False
    seller: str = ""
    marketplace: str


class DiscoverySearchResponse(BaseModel):
    """Paginated search results."""

    products: list[DiscoveryProductResponse]
    page: int
    total_pages: int | None = None
    marketplace: str
    query: str


# ─── Endpoints ────────────────────────────────────────────────


@router.get(
    "/search",
    summary="Search for products",
    response_model=DiscoverySearchResponse,
)
async def search_products(
    response: Response,
    query: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Search keywords",
    ),
    marketplace: str = Query(
        default="amazon",
        pattern="^(amazon|walmart)$",
        description="Marketplace to search",
    ),
    page: int = Query(
        default=1,
        ge=1,
        le=20,
        description="Page number (1-20)",
    ),
    user: dict = Depends(get_current_user),
) -> dict:
    """
    Search for products on Amazon or Walmart by keyword.

    Uses ScraperAPI structured search endpoints. Searches are free and
    do not count against your daily conversion limit.

    Returns normalized results with product name, price, image, URL,
    ratings, and marketplace-specific badges (Prime, Best Seller, etc.).
    """
    try:
        service = DiscoveryService()
        result = await service.search(
            query=query,
            marketplace=marketplace,
            page=page,
        )
        return result.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.error(f"Discovery search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {type(e).__name__}",
        )
