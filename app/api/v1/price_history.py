"""
Price history API endpoints.

Provides:
- GET /api/v1/products/{product_id}/prices — Price history for a product
- GET /api/v1/products/{product_id}/prices/stats — Price statistics

All endpoints require JWT authentication (Bearer token).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.price_history_repo import PriceHistoryRepository
from app.db.repositories.product_repo import ProductRepository
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/products", tags=["Price History"])


async def _get_user_product(
    product_id: str,
    user: dict,
    db: AsyncSession,
):
    """Helper: validate product ID and ensure tenant isolation."""
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID format")

    user_id = uuid.UUID(user["sub"])
    repo = ProductRepository(db)
    product = await repo.get_by_id(pid)

    if product is None or product.user_id != user_id:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@router.get("/{product_id}/prices", summary="Get price history")
async def get_price_history(
    product_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """
    Get price history for a product, newest first.

    Returns recorded price observations over time with timestamps.
    Requires a valid access token in the Authorization header.
    """
    product = await _get_user_product(product_id, user, db)

    repo = PriceHistoryRepository(db)
    history = await repo.get_history(
        product_id=product.id,
        limit=limit,
        offset=offset,
    )

    return {
        "product_id": str(product.id),
        "prices": [
            {
                "id": str(h.id),
                "price": h.price,
                "currency": h.currency,
                "recorded_at": h.recorded_at.isoformat() if h.recorded_at else None,
            }
            for h in history
        ],
        "total": len(history),
    }


@router.get("/{product_id}/prices/stats", summary="Get price statistics")
async def get_price_stats(
    product_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregate price statistics for a product.

    Returns min, max, average price and total observation count.
    Requires a valid access token in the Authorization header.
    """
    product = await _get_user_product(product_id, user, db)

    repo = PriceHistoryRepository(db)
    stats = await repo.get_price_stats(product_id=product.id)

    return {
        "product_id": str(product.id),
        "current_price": product.price,
        **stats,
    }
