"""Tests for app.services.cache_service — Redis-backed query cache."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from redis.exceptions import RedisError

from app.services.cache_service import CacheService


def _make_service(redis=None):
    """Create a CacheService with a mock Redis and default settings."""
    if redis is None:
        redis = AsyncMock()
    with patch("app.services.cache_service.get_settings") as mock_settings:
        settings = MagicMock()
        settings.cache_ttl_default = 300
        mock_settings.return_value = settings
        return CacheService(redis)


class TestCacheKey:
    """Verify cache key construction."""

    def test_key_format(self):
        svc = _make_service()
        assert svc._key("user", "abc123") == "cache:user:abc123"

    def test_key_with_uuid(self):
        svc = _make_service()
        key = svc._key("tier", "550e8400-e29b-41d4-a716-446655440000")
        assert key == "cache:tier:550e8400-e29b-41d4-a716-446655440000"


class TestCacheGet:
    """Verify cache get operations."""

    async def test_returns_dict_on_hit(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value='{"tier": "pro"}')
        svc = _make_service(redis)
        result = await svc.get("user", "u1")
        assert result == {"tier": "pro"}
        redis.get.assert_called_once_with("cache:user:u1")

    async def test_returns_list_on_hit(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value='[1, 2, 3]')
        svc = _make_service(redis)
        result = await svc.get("counts", "u1")
        assert result == [1, 2, 3]

    async def test_returns_none_on_miss(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        svc = _make_service(redis)
        result = await svc.get("user", "nonexistent")
        assert result is None

    async def test_returns_none_on_redis_error(self):
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=RedisError("connection lost"))
        svc = _make_service(redis)
        result = await svc.get("user", "u1")
        assert result is None

    async def test_returns_none_on_invalid_json(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="not-json{{{")
        svc = _make_service(redis)
        result = await svc.get("user", "u1")
        assert result is None


class TestCacheSet:
    """Verify cache set operations."""

    async def test_set_with_default_ttl(self):
        redis = AsyncMock()
        redis.set = AsyncMock()
        svc = _make_service(redis)
        ok = await svc.set("user", "u1", {"tier": "pro"})
        assert ok is True
        redis.set.assert_called_once_with(
            "cache:user:u1",
            json.dumps({"tier": "pro"}),
            ex=300,  # default TTL
        )

    async def test_set_with_custom_ttl(self):
        redis = AsyncMock()
        redis.set = AsyncMock()
        svc = _make_service(redis)
        ok = await svc.set("counts", "u1", {"pending": 5}, ttl=60)
        assert ok is True
        redis.set.assert_called_once_with(
            "cache:counts:u1",
            json.dumps({"pending": 5}),
            ex=60,
        )

    async def test_set_returns_false_on_redis_error(self):
        redis = AsyncMock()
        redis.set = AsyncMock(side_effect=RedisError("write failure"))
        svc = _make_service(redis)
        ok = await svc.set("user", "u1", {"tier": "pro"})
        assert ok is False

    async def test_set_serializes_uuid_via_default_str(self):
        import uuid
        redis = AsyncMock()
        redis.set = AsyncMock()
        svc = _make_service(redis)
        uid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        ok = await svc.set("user", "u1", {"id": uid})
        assert ok is True
        # UUID should be serialized as string via json default=str
        call_args = redis.set.call_args
        data = json.loads(call_args[0][1])
        assert data["id"] == "550e8400-e29b-41d4-a716-446655440000"


class TestCacheDelete:
    """Verify cache delete operations."""

    async def test_delete_success(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        svc = _make_service(redis)
        ok = await svc.delete("user", "u1")
        assert ok is True
        redis.delete.assert_called_once_with("cache:user:u1")

    async def test_delete_returns_false_on_error(self):
        redis = AsyncMock()
        redis.delete = AsyncMock(side_effect=RedisError("fail"))
        svc = _make_service(redis)
        ok = await svc.delete("user", "u1")
        assert ok is False


class TestInvalidateNamespace:
    """Verify namespace-wide cache invalidation."""

    async def test_invalidate_deletes_matching_keys(self):
        redis = AsyncMock()

        async def fake_scan_iter(match=None, count=None):
            for key in ["cache:user:u1", "cache:user:u2", "cache:user:u3"]:
                yield key

        redis.scan_iter = fake_scan_iter
        redis.delete = AsyncMock()
        svc = _make_service(redis)
        count = await svc.invalidate_namespace("user")
        assert count == 3
        assert redis.delete.call_count == 3

    async def test_invalidate_returns_zero_on_empty(self):
        redis = AsyncMock()

        async def fake_scan_iter(match=None, count=None):
            return
            yield  # Make it an async generator

        redis.scan_iter = fake_scan_iter
        redis.delete = AsyncMock()
        svc = _make_service(redis)
        count = await svc.invalidate_namespace("empty")
        assert count == 0

    async def test_invalidate_returns_zero_on_error(self):
        redis = AsyncMock()

        async def fake_scan_iter(match=None, count=None):
            raise RedisError("scan failed")
            yield  # Make it an async generator

        redis.scan_iter = fake_scan_iter
        svc = _make_service(redis)
        count = await svc.invalidate_namespace("broken")
        assert count == 0
