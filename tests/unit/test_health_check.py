"""Tests for app.core.health — enhanced health check probes."""

from unittest.mock import AsyncMock, MagicMock

from app.core.health import check_database, check_redis, get_health_status


class TestCheckDatabase:
    """Verify database connectivity probe."""

    async def test_returns_up_on_success(self):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        result = await check_database(session)
        assert result["status"] == "up"
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0

    async def test_returns_down_on_failure(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=ConnectionError("connection refused"))
        result = await check_database(session)
        assert result["status"] == "down"
        assert "connection refused" in result["error"]


class TestCheckRedis:
    """Verify Redis connectivity probe."""

    async def test_returns_up_on_success(self):
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)
        result = await check_redis(redis)
        assert result["status"] == "up"
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0

    async def test_returns_down_on_failure(self):
        redis = AsyncMock()
        redis.ping = AsyncMock(side_effect=ConnectionError("redis unavailable"))
        result = await check_redis(redis)
        assert result["status"] == "down"
        assert "redis unavailable" in result["error"]


class TestGetHealthStatus:
    """Verify overall health status aggregation."""

    async def test_healthy_when_all_probes_pass(self):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)

        result = await get_health_status(
            app_name="KonvertIt",
            app_version="0.1.0",
            app_env="development",
            db_session=session,
            redis_client=redis,
        )
        assert result["status"] == "healthy"
        assert result["components"]["database"]["status"] == "up"
        assert result["components"]["redis"]["status"] == "up"

    async def test_degraded_when_db_down(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=ConnectionError("db down"))
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)

        result = await get_health_status(
            app_name="KonvertIt",
            app_version="0.1.0",
            app_env="development",
            db_session=session,
            redis_client=redis,
        )
        assert result["status"] == "degraded"
        assert result["components"]["database"]["status"] == "down"
        assert result["components"]["redis"]["status"] == "up"

    async def test_degraded_when_redis_down(self):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        redis = AsyncMock()
        redis.ping = AsyncMock(side_effect=ConnectionError("redis down"))

        result = await get_health_status(
            app_name="KonvertIt",
            app_version="0.1.0",
            app_env="development",
            db_session=session,
            redis_client=redis,
        )
        assert result["status"] == "degraded"
        assert result["components"]["database"]["status"] == "up"
        assert result["components"]["redis"]["status"] == "down"

    async def test_degraded_when_both_down(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=ConnectionError("db down"))
        redis = AsyncMock()
        redis.ping = AsyncMock(side_effect=ConnectionError("redis down"))

        result = await get_health_status(
            app_name="KonvertIt",
            app_version="0.1.0",
            app_env="development",
            db_session=session,
            redis_client=redis,
        )
        assert result["status"] == "degraded"
        assert result["components"]["database"]["status"] == "down"
        assert result["components"]["redis"]["status"] == "down"

    async def test_healthy_when_no_probes_configured(self):
        result = await get_health_status(
            app_name="KonvertIt",
            app_version="0.1.0",
            app_env="development",
        )
        assert result["status"] == "healthy"
        assert result["components"] == {}

    async def test_includes_metadata(self):
        result = await get_health_status(
            app_name="KonvertIt",
            app_version="0.1.0",
            app_env="production",
        )
        assert result["app"] == "KonvertIt"
        assert result["version"] == "0.1.0"
        assert result["environment"] == "production"
        assert "timestamp" in result

    async def test_latency_tracked_on_success(self):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)

        result = await get_health_status(
            app_name="KonvertIt",
            app_version="0.1.0",
            app_env="development",
            db_session=session,
            redis_client=redis,
        )
        assert isinstance(result["components"]["database"]["latency_ms"], float)
        assert isinstance(result["components"]["redis"]["latency_ms"], float)
