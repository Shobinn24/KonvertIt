"""
Enhanced health check with dependency probes.

Checks:
- Application: always up if responding
- Database: execute ``SELECT 1`` via async session
- Redis: execute ``PING`` via async client

Returns 200 with ``"healthy"`` or ``"degraded"`` status — never 503.
Load balancers check for 200; the body indicates component health.
"""

import asyncio
import logging
import time
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def check_database(session: AsyncSession) -> dict:
    """
    Probe database connectivity.

    Returns:
        ``{"status": "up", "latency_ms": float}`` or
        ``{"status": "down", "error": str}``
    """
    try:
        start = time.monotonic()
        await session.execute(text("SELECT 1"))
        latency = round((time.monotonic() - start) * 1000, 1)
        return {"status": "up", "latency_ms": latency}
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return {"status": "down", "error": str(e)}


async def check_redis(redis: Redis) -> dict:
    """
    Probe Redis connectivity.

    Returns:
        ``{"status": "up", "latency_ms": float}`` or
        ``{"status": "down", "error": str}``
    """
    try:
        start = time.monotonic()
        await redis.ping()
        latency = round((time.monotonic() - start) * 1000, 1)
        return {"status": "up", "latency_ms": latency}
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return {"status": "down", "error": str(e)}


async def get_health_status(
    app_name: str,
    app_version: str,
    app_env: str,
    db_session: AsyncSession | None = None,
    redis_client: Redis | None = None,
) -> dict:
    """
    Build complete health status response.

    Runs DB and Redis probes concurrently. Overall status is
    ``"healthy"`` if all configured probes pass, ``"degraded"``
    if any fail.
    """
    components: dict[str, dict] = {}

    # Run probes concurrently
    tasks: dict[str, asyncio.Task] = {}
    if db_session is not None:
        tasks["database"] = asyncio.create_task(check_database(db_session))
    if redis_client is not None:
        tasks["redis"] = asyncio.create_task(check_redis(redis_client))

    for name, task in tasks.items():
        components[name] = await task

    # Determine overall status
    all_up = all(c["status"] == "up" for c in components.values())
    overall = "healthy" if (not components or all_up) else "degraded"

    return {
        "status": overall,
        "app": app_name,
        "version": app_version,
        "environment": app_env,
        "timestamp": datetime.now(UTC).isoformat(),
        "components": components,
    }
