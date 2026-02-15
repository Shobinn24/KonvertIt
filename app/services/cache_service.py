"""
Redis-backed cache service for hot data.

Provides async get/set/delete with JSON serialization, TTL management,
and fail-open behavior (cache misses on Redis errors, never blocks).

Designed for frequently-accessed, rarely-changing data:
- User tier lookups (loaded on every auth check)
- Listing/conversion status counts (dashboard aggregation queries)
- eBay category mappings (static reference data)
"""

import json
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Async Redis cache with JSON serialization and fail-open behavior.

    All operations are safe to call even when Redis is unavailable — errors
    are logged and the caller falls through to the database.
    """

    KEY_PREFIX = "cache:"

    def __init__(self, redis: Redis):
        self.redis = redis
        self._settings = get_settings()

    def _key(self, namespace: str, key: str) -> str:
        """Build a namespaced cache key."""
        return f"{self.KEY_PREFIX}{namespace}:{key}"

    async def get(self, namespace: str, key: str) -> dict | list | None:
        """
        Get a cached value by namespace and key.

        Returns None on cache miss or Redis error (fail-open).
        """
        try:
            raw = await self.redis.get(self._key(namespace, key))
            if raw is None:
                return None
            return json.loads(raw)
        except RedisError:
            logger.warning("cache_get_error", extra={"namespace": namespace, "key": key})
            return None
        except (json.JSONDecodeError, TypeError):
            logger.warning("cache_decode_error", extra={"namespace": namespace, "key": key})
            return None

    async def set(
        self,
        namespace: str,
        key: str,
        value: dict | list,
        ttl: int | None = None,
    ) -> bool:
        """
        Cache a value with optional TTL (seconds).

        Falls back to default TTL from settings if not specified.
        Returns True on success, False on Redis error (fail-open).
        """
        if ttl is None:
            ttl = self._settings.cache_ttl_default
        try:
            raw = json.dumps(value, default=str)
            await self.redis.set(self._key(namespace, key), raw, ex=ttl)
            return True
        except (RedisError, TypeError):
            logger.warning("cache_set_error", extra={"namespace": namespace, "key": key})
            return False

    async def delete(self, namespace: str, key: str) -> bool:
        """
        Delete a cached value.

        Returns True on success, False on Redis error (fail-open).
        """
        try:
            await self.redis.delete(self._key(namespace, key))
            return True
        except RedisError:
            logger.warning("cache_delete_error", extra={"namespace": namespace, "key": key})
            return False

    async def invalidate_namespace(self, namespace: str) -> int:
        """
        Delete all keys under a namespace.

        Uses SCAN to avoid blocking Redis with a single KEYS command.
        Returns the number of keys deleted, or 0 on error.
        """
        pattern = f"{self.KEY_PREFIX}{namespace}:*"
        deleted = 0
        try:
            async for key in self.redis.scan_iter(match=pattern, count=100):
                await self.redis.delete(key)
                deleted += 1
            return deleted
        except RedisError:
            logger.warning("cache_invalidate_error", extra={"namespace": namespace})
            return 0
