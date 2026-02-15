"""
Conversion-specific database repository.

Handles CRUD and query operations for the Conversion lifecycle model,
including status transitions, user-scoped queries, and product/listing lookups.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversion
from app.db.repositories.base_repo import BaseRepository


class ConversionRepository(BaseRepository[Conversion]):
    """Repository for Conversion CRUD and pipeline state queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Conversion)

    async def find_by_user(
        self,
        user_id: uuid.UUID,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Conversion]:
        """
        Get conversions for a user, optionally filtered by status.

        Args:
            user_id: Owner user ID.
            status: Filter by conversion status (pending, processing, completed, failed).
            limit: Maximum records to return.
            offset: Pagination offset.

        Returns:
            List of Conversion records, newest first.
        """
        stmt = select(Conversion).where(Conversion.user_id == user_id)
        if status:
            stmt = stmt.where(Conversion.status == status)
        stmt = stmt.order_by(Conversion.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_product(
        self,
        product_id: uuid.UUID,
    ) -> list[Conversion]:
        """
        Get all conversions for a specific product.

        Args:
            product_id: The product's primary key.

        Returns:
            List of Conversion records for that product, newest first.
        """
        stmt = (
            select(Conversion)
            .where(Conversion.product_id == product_id)
            .order_by(Conversion.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_pending(
        self,
        limit: int = 50,
    ) -> list[Conversion]:
        """
        Get conversions that are still in-progress (pending or processing).

        Useful for background job retries and stale conversion cleanup.

        Args:
            limit: Maximum records to return.

        Returns:
            List of in-progress Conversion records, oldest first.
        """
        stmt = (
            select(Conversion)
            .where(Conversion.status.in_(["pending", "processing"]))
            .order_by(Conversion.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_status_range(
        self,
        user_id: uuid.UUID,
        statuses: list[str],
        limit: int = 100,
        offset: int = 0,
    ) -> list[Conversion]:
        """
        Find conversions matching any of the given statuses.

        Args:
            user_id: Owner user ID.
            statuses: List of status values to match.
            limit: Maximum records to return.
            offset: Pagination offset.

        Returns:
            List of matching Conversion records.
        """
        stmt = (
            select(Conversion)
            .where(
                Conversion.user_id == user_id,
                Conversion.status.in_(statuses),
            )
            .order_by(Conversion.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        conversion_id: uuid.UUID,
        new_status: str,
        error_message: str | None = None,
    ) -> Conversion | None:
        """
        Update conversion status atomically with optional error message.

        Sets converted_at timestamp when status transitions to 'completed'.

        Args:
            conversion_id: The conversion's primary key.
            new_status: New status value.
            error_message: Error details (for failed conversions).

        Returns:
            Updated Conversion, or None if not found.
        """
        conversion = await self.get_by_id(conversion_id)
        if conversion is None:
            return None

        conversion.status = new_status
        conversion.error_message = error_message

        if new_status == "completed":
            conversion.converted_at = datetime.now(UTC)

        await self.session.flush()
        return conversion

    async def link_listing(
        self,
        conversion_id: uuid.UUID,
        listing_id: uuid.UUID,
    ) -> Conversion | None:
        """
        Link a listing to a conversion after successful eBay publish.

        Args:
            conversion_id: The conversion's primary key.
            listing_id: The listing's primary key.

        Returns:
            Updated Conversion, or None if not found.
        """
        conversion = await self.get_by_id(conversion_id)
        if conversion is None:
            return None

        conversion.listing_id = listing_id
        await self.session.flush()
        return conversion

    async def count_by_status(self, user_id: uuid.UUID) -> dict[str, int]:
        """
        Get count of conversions grouped by status for a user.

        Args:
            user_id: Owner user ID.

        Returns:
            Dict mapping status string to count.
        """
        stmt = (
            select(Conversion.status, func.count())
            .where(Conversion.user_id == user_id)
            .group_by(Conversion.status)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
