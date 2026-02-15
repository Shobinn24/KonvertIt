"""
Redis-backed rate limiting for KonvertIt API.

Enforces per-user daily conversion limits based on subscription tier:
- Free: 50 conversions/day, 100 max listings
- Pro: 500 conversions/day, 5,000 max listings
- Enterprise: unlimited (-1)

Uses Redis INCR with TTL for atomic counter operations.
Returns X-RateLimit-* headers for client consumption.

Architecture: FastAPI dependency injection (Depends pattern),
consistent with auth_middleware.py.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import get_settings
from app.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)


# ─── Tier Rate Limits (single source of truth) ──────────────


TIER_RATE_LIMITS: dict[str, dict[str, int]] = {
    "free": {"daily_conversions": 50, "max_listings": 100},
    "pro": {"daily_conversions": 500, "max_listings": 5000},
    "enterprise": {"daily_conversions": -1, "max_listings": -1},  # Unlimited
}


# ─── Rate Limit Info Dataclass ───────────────────────────────


@dataclass
class RateLimitInfo:
    """Rate limit state returned to the endpoint for header injection."""

    limit: int  # Total allowed per day (-1 = unlimited)
    remaining: int  # Remaining for today (-1 = unlimited)
    reset_timestamp: int  # Unix timestamp when the daily window resets
    current_count: int  # Current usage count for today


# ─── Redis Connection Management ─────────────────────────────


_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """
    Get or create the shared async Redis client.

    Uses the redis_url from application Settings. The client is created
    lazily on first access and reused for all subsequent requests.
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


# ─── Redis Key & Time Helpers ────────────────────────────────


def _get_rate_limit_key(user_id: str) -> str:
    """
    Build the Redis key for today's conversion count.

    Pattern: ratelimit:conversions:{user_id}:{YYYY-MM-DD}
    Uses UTC date for consistent daily windows across time zones.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"ratelimit:conversions:{user_id}:{today}"


def _get_reset_timestamp() -> int:
    """Get the Unix timestamp for midnight UTC (start of next day)."""
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(tomorrow.timestamp())


def _get_seconds_until_reset() -> int:
    """Get the number of seconds remaining until midnight UTC."""
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((tomorrow - now).total_seconds()))


# ─── Core Rate Limit Logic ───────────────────────────────────


async def _check_rate_limit(
    user_id: str,
    tier: str,
    url_count: int,
    redis: Redis,
) -> RateLimitInfo:
    """
    Check and increment the conversion rate limit for a user.

    Args:
        user_id: The user's UUID string.
        tier: The user's subscription tier (free, pro, enterprise).
        url_count: Number of conversions being requested (1 for single, N for bulk).
        redis: Async Redis client.

    Returns:
        RateLimitInfo with current state.

    Raises:
        HTTPException 429 if the rate limit would be exceeded.
    """
    limits = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS["free"])
    daily_limit = limits["daily_conversions"]
    reset_ts = _get_reset_timestamp()

    # Enterprise tier: unlimited — skip Redis entirely
    if daily_limit == -1:
        return RateLimitInfo(
            limit=-1,
            remaining=-1,
            reset_timestamp=reset_ts,
            current_count=0,
        )

    key = _get_rate_limit_key(user_id)

    try:
        # Read current count to check before incrementing
        current_count_raw = await redis.get(key)
        current_count = int(current_count_raw) if current_count_raw else 0

        # Would this request exceed the limit?
        if current_count + url_count > daily_limit:
            remaining = max(0, daily_limit - current_count)
            seconds_until_reset = _get_seconds_until_reset()

            logger.warning(
                f"Rate limit exceeded for user {user_id} (tier={tier}): "
                f"{current_count}/{daily_limit}, requested {url_count}"
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Daily conversion limit exceeded",
                    "limit": daily_limit,
                    "used": current_count,
                    "requested": url_count,
                    "remaining": remaining,
                    "reset": reset_ts,
                    "tier": tier,
                    "upgrade_hint": (
                        "Upgrade to a higher tier for more conversions"
                        if tier != "enterprise"
                        else None
                    ),
                },
                headers={
                    "X-RateLimit-Limit": str(daily_limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_ts),
                    "Retry-After": str(seconds_until_reset),
                },
            )

        # Atomically increment counter and set TTL
        pipe = redis.pipeline()
        pipe.incrby(key, url_count)
        pipe.expire(key, _get_seconds_until_reset())
        results = await pipe.execute()

        new_count = results[0]  # Result of INCRBY
        remaining = max(0, daily_limit - new_count)

        # Push WebSocket warning when usage exceeds 80% of limit
        if daily_limit > 0 and new_count >= daily_limit * 0.8:
            try:
                from app.services.ws_manager import WSEvent, WSEventType, get_ws_manager
                ws_mgr = get_ws_manager()
                await ws_mgr.send_to_user(user_id, WSEvent(
                    event=WSEventType.RATE_LIMIT_WARNING,
                    data={
                        "used": new_count,
                        "limit": daily_limit,
                        "remaining": remaining,
                        "tier": tier,
                        "pct_used": round((new_count / daily_limit) * 100, 1),
                    },
                ))
            except Exception:
                pass  # WS is best-effort

        return RateLimitInfo(
            limit=daily_limit,
            remaining=remaining,
            reset_timestamp=reset_ts,
            current_count=new_count,
        )

    except HTTPException:
        # Re-raise 429 — don't catch our own exception
        raise

    except (ConnectionError, TimeoutError, RedisError, OSError) as e:
        # Fail-open: if Redis is down, allow the request
        logger.error(f"Redis unavailable for rate limiting: {e}")
        return RateLimitInfo(
            limit=daily_limit,
            remaining=-1,  # Unknown
            reset_timestamp=reset_ts,
            current_count=-1,
        )


# ─── FastAPI Dependencies ────────────────────────────────────


async def check_conversion_rate_limit(
    user: dict = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> RateLimitInfo:
    """
    FastAPI dependency: check single-conversion rate limit.

    Consumes 1 from the daily quota. Use for:
    - POST /conversions/
    - POST /conversions/preview

    Raises HTTPException 429 if limit exceeded.
    Returns RateLimitInfo for header injection.
    """
    return await _check_rate_limit(
        user_id=user["sub"],
        tier=user.get("tier", "free"),
        url_count=1,
        redis=redis,
    )


async def check_bulk_conversion_rate_limit(
    request: Request,
    user: dict = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> RateLimitInfo:
    """
    FastAPI dependency: check bulk-conversion rate limit.

    Reads the request body to determine the number of URLs,
    then consumes that many from the daily quota. Use for:
    - POST /conversions/bulk
    - POST /conversions/bulk/stream

    Raises HTTPException 429 if limit would be exceeded.
    Returns RateLimitInfo for header injection.
    """
    body = await request.json()
    urls = body.get("urls", [])
    url_count = len(urls) if urls else 1

    return await _check_rate_limit(
        user_id=user["sub"],
        tier=user.get("tier", "free"),
        url_count=url_count,
        redis=redis,
    )


# ─── Response Header Helper ─────────────────────────────────


def add_rate_limit_headers(response, rate_info: RateLimitInfo) -> None:
    """
    Add X-RateLimit-* headers to a response object.

    Called by endpoints after receiving RateLimitInfo from the dependency.

    Works with both FastAPI Response objects (which have a .headers dict)
    and plain dicts (for StreamingResponse headers).
    """
    if isinstance(response, dict):
        # For StreamingResponse headers dict
        headers = response
    else:
        headers = response.headers

    if rate_info.limit == -1:
        headers["X-RateLimit-Limit"] = "unlimited"
        headers["X-RateLimit-Remaining"] = "unlimited"
    else:
        headers["X-RateLimit-Limit"] = str(rate_info.limit)
        headers["X-RateLimit-Remaining"] = str(rate_info.remaining)

    headers["X-RateLimit-Reset"] = str(rate_info.reset_timestamp)
