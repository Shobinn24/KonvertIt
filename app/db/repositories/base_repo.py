"""
Generic async CRUD repository base class.

Provides reusable data access methods that all entity-specific
repositories inherit from.
"""

import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with common CRUD operations.

    Subclasses specify the model class and add entity-specific queries.
    All queries that return user-owned data must be scoped by user_id.
    """

    def __init__(self, session: AsyncSession, model: type[ModelType]):
        self.session = session
        self.model = model

    async def get_by_id(self, record_id: uuid.UUID) -> ModelType | None:
        """Get a single record by primary key."""
        return await self.session.get(self.model, record_id)

    async def get_all(
        self,
        user_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelType]:
        """
        Get all records, optionally filtered by user_id for tenant isolation.

        Args:
            user_id: If provided, only return records owned by this user.
            limit: Maximum number of records to return.
            offset: Number of records to skip.
        """
        stmt = select(self.model)
        if user_id is not None and hasattr(self.model, "user_id"):
            stmt = stmt.where(self.model.user_id == user_id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelType:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, record_id: uuid.UUID, **kwargs) -> ModelType | None:
        """Update an existing record by ID."""
        instance = await self.get_by_id(record_id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete(self, record_id: uuid.UUID) -> bool:
        """Delete a record by ID. Returns True if deleted, False if not found."""
        instance = await self.get_by_id(record_id)
        if instance is None:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def count(self, user_id: uuid.UUID | None = None) -> int:
        """Count records, optionally filtered by user_id."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        if user_id is not None and hasattr(self.model, "user_id"):
            stmt = stmt.where(self.model.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
