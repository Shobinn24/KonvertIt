"""
Auto-discovery configuration and run history repository.

Provides data access for AutoDiscoveryConfig (per-user settings) and
AutoDiscoveryRun (execution audit trail) models.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AutoDiscoveryConfig, AutoDiscoveryRun


class AutoDiscoveryRepository:
    """Repository for auto-discovery config and run history queries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Config queries ────────────────────────────────────────────

    async def get_config(self, user_id: uuid.UUID) -> AutoDiscoveryConfig | None:
        """Get the auto-discovery config for a user (one per user)."""
        stmt = select(AutoDiscoveryConfig).where(
            AutoDiscoveryConfig.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_config(
        self, user_id: uuid.UUID, **kwargs
    ) -> AutoDiscoveryConfig:
        """
        Create or update the auto-discovery config for a user.

        Any keyword arguments are set as column values on the config row.
        Returns the persisted config instance.
        """
        config = await self.get_config(user_id)
        if config is None:
            config = AutoDiscoveryConfig(user_id=user_id, **kwargs)
            self.session.add(config)
        else:
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        await self.session.flush()
        return config

    async def get_enabled_configs(self) -> list[AutoDiscoveryConfig]:
        """Get all configs where auto-discovery is enabled (for scheduler)."""
        stmt = (
            select(AutoDiscoveryConfig)
            .where(AutoDiscoveryConfig.enabled.is_(True))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── Run history queries ───────────────────────────────────────

    async def save_run(self, run: AutoDiscoveryRun) -> AutoDiscoveryRun:
        """Persist a completed auto-discovery run record."""
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_runs(
        self, user_id: uuid.UUID, limit: int = 20
    ) -> list[AutoDiscoveryRun]:
        """Get recent auto-discovery runs for a user, newest first."""
        limit = min(limit, 100)
        stmt = (
            select(AutoDiscoveryRun)
            .where(AutoDiscoveryRun.user_id == user_id)
            .order_by(AutoDiscoveryRun.run_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── Daily count management ────────────────────────────────────

    async def reset_daily_count(self, user_id: uuid.UUID) -> None:
        """Reset the items_found_today counter on the user's config to zero."""
        stmt = (
            update(AutoDiscoveryConfig)
            .where(AutoDiscoveryConfig.user_id == user_id)
            .values(items_found_today=0)
        )
        await self.session.execute(stmt)
        await self.session.flush()
