"""
Price history–specific database repository.

Handles append-only price tracking for monitored products,
including time-range queries and price change detection.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PriceHistory
from app.db.repositories.base_repo import BaseRepository


class PriceHistoryRepository(BaseRepository[PriceHistory]):
    """Repository for PriceHistory append-only tracking and analysis queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, PriceHistory)

    async def record_price(
        self,
        product_id: uuid.UUID,
        price: float,
        currency: str = "USD",
    ) -> PriceHistory:
        """
        Append a new price observation for a product.

        Args:
            product_id: The product's primary key.
            price: Observed price value.
            currency: ISO currency code (default: USD).

        Returns:
            Newly created PriceHistory record.
        """
        return await self.create(
            product_id=product_id,
            price=price,
            currency=currency,
        )

    async def get_history(
        self,
        product_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PriceHistory]:
        """
        Get price history for a product, newest first.

        Args:
            product_id: The product's primary key.
            limit: Maximum records to return.
            offset: Pagination offset.

        Returns:
            List of PriceHistory records, newest first.
        """
        stmt = (
            select(PriceHistory)
            .where(PriceHistory.product_id == product_id)
            .order_by(PriceHistory.recorded_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_price(
        self,
        product_id: uuid.UUID,
    ) -> PriceHistory | None:
        """
        Get the most recent price observation for a product.

        Args:
            product_id: The product's primary key.

        Returns:
            Latest PriceHistory record, or None if no history.
        """
        stmt = (
            select(PriceHistory)
            .where(PriceHistory.product_id == product_id)
            .order_by(PriceHistory.recorded_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_price_range(
        self,
        product_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> list[PriceHistory]:
        """
        Get price history within a date range.

        Args:
            product_id: The product's primary key.
            start: Range start (inclusive).
            end: Range end (inclusive).

        Returns:
            List of PriceHistory records within the range, chronological order.
        """
        stmt = (
            select(PriceHistory)
            .where(
                PriceHistory.product_id == product_id,
                PriceHistory.recorded_at >= start,
                PriceHistory.recorded_at <= end,
            )
            .order_by(PriceHistory.recorded_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_price_stats(
        self,
        product_id: uuid.UUID,
    ) -> dict[str, float | None]:
        """
        Get aggregate price statistics for a product.

        Args:
            product_id: The product's primary key.

        Returns:
            Dict with min_price, max_price, avg_price, count.
        """
        stmt = select(
            func.min(PriceHistory.price),
            func.max(PriceHistory.price),
            func.avg(PriceHistory.price),
            func.count(PriceHistory.id),
        ).where(PriceHistory.product_id == product_id)

        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "min_price": float(row[0]) if row[0] is not None else None,
            "max_price": float(row[1]) if row[1] is not None else None,
            "avg_price": round(float(row[2]), 2) if row[2] is not None else None,
            "count": row[3],
        }

    async def count_for_product(
        self,
        product_id: uuid.UUID,
    ) -> int:
        """
        Count total price observations for a product.

        Args:
            product_id: The product's primary key.

        Returns:
            Number of price history records.
        """
        stmt = (
            select(func.count())
            .select_from(PriceHistory)
            .where(PriceHistory.product_id == product_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
