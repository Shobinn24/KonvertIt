"""
Product-specific database repository.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product
from app.db.repositories.base_repo import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Repository for Product CRUD and queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Product)

    async def find_by_source_id(
        self,
        user_id: uuid.UUID,
        source_marketplace: str,
        source_product_id: str,
    ) -> Product | None:
        """
        Find a product by source marketplace and product ID for a specific user.

        This is the deduplication check — prevents re-scraping the same product.
        """
        stmt = (
            select(Product)
            .where(
                Product.user_id == user_id,
                Product.source_marketplace == source_marketplace,
                Product.source_product_id == source_product_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_user(
        self,
        user_id: uuid.UUID,
        marketplace: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Product]:
        """Get products for a user, optionally filtered by source marketplace."""
        stmt = select(Product).where(Product.user_id == user_id)
        if marketplace:
            stmt = stmt.where(Product.source_marketplace == marketplace)
        stmt = stmt.order_by(Product.scraped_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_brand(
        self,
        user_id: uuid.UUID,
        brand: str,
    ) -> list[Product]:
        """Find all products by brand name for a user."""
        stmt = (
            select(Product)
            .where(Product.user_id == user_id, Product.brand == brand)
            .order_by(Product.scraped_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
