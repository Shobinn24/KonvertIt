"""
Listing-specific database repository.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Listing
from app.db.repositories.base_repo import BaseRepository


class ListingRepository(BaseRepository[Listing]):
    """Repository for Listing CRUD and queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Listing)

    async def find_by_user(
        self,
        user_id: uuid.UUID,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Listing]:
        """Get listings for a user, optionally filtered by status."""
        stmt = select(Listing).where(Listing.user_id == user_id)
        if status:
            stmt = stmt.where(Listing.status == status)
        stmt = stmt.order_by(Listing.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_ebay_id(self, ebay_item_id: str) -> Listing | None:
        """Find a listing by its eBay marketplace item ID."""
        stmt = select(Listing).where(Listing.ebay_item_id == ebay_item_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_active_by_user(self, user_id: uuid.UUID) -> list[Listing]:
        """Get all active listings for a user."""
        return await self.find_by_user(user_id, status="active")

    async def count_by_status(self, user_id: uuid.UUID) -> dict[str, int]:
        """Get count of listings grouped by status for a user."""
        from sqlalchemy import func

        stmt = (
            select(Listing.status, func.count())
            .where(Listing.user_id == user_id)
            .group_by(Listing.status)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
