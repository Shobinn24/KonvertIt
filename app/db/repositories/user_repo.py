"""
User-specific database repository.
"""

import uuid
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User CRUD and authentication queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def find_by_email(self, email: str) -> User | None:
        """Find a user by email address (case-insensitive)."""
        stmt = select(User).where(User.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check if an email is already registered."""
        user = await self.find_by_email(email)
        return user is not None

    async def find_active_users(
        self,
        tier: str | None = None,
        limit: int = 100,
    ) -> list[User]:
        """Get active users, optionally filtered by subscription tier."""
        stmt = select(User).where(User.is_active.is_(True))
        if tier:
            stmt = stmt.where(User.tier == tier)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_stripe_customer_id(self, stripe_customer_id: str) -> User | None:
        """Find a user by their Stripe customer ID."""
        stmt = select(User).where(User.stripe_customer_id == stripe_customer_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        """Update the last_login timestamp for a user."""
        from datetime import datetime

        user = await self.get_by_id(user_id)
        if user:
            user.last_login = datetime.now(UTC)
            await self.session.flush()
