"""
Rate limiting for authentication endpoints (login, register).

Protects against brute-force attacks and credential stuffing by limiting
the number of attempts per IP address within a sliding window.

Limits:
- Register: 5 attempts per 15 minutes per IP
- Login: 10 attempts per 15 minutes per IP
"""

import logging

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from app.middleware.rate_limiter import get_redis

logger = logging.getLogger(__name__)

# Rate limit configuration per action
AUTH_RATE_LIMITS = {
    "register": {"max_attempts": 5, "window_seconds": 900},  # 5 per 15 min
    "login": {"max_attempts": 10, "window_seconds": 900},  # 10 per 15 min
}


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting common proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


async def check_auth_rate_limit(request: Request, action: str = "login") -> None:
    """
    Check rate limit for auth endpoints. Raises 429 if exceeded.

    Args:
        request: The FastAPI request (for client IP extraction).
        action: "login" or "register" — determines the limit.
    """
    limits = AUTH_RATE_LIMITS.get(action, AUTH_RATE_LIMITS["login"])
    max_attempts = limits["max_attempts"]
    window = limits["window_seconds"]

    client_ip = _get_client_ip(request)
    key = f"auth_ratelimit:{action}:{client_ip}"

    try:
        redis = await get_redis()
        if redis is None:
            return  # Fail-open if Redis unavailable

        current = await redis.get(key)
        count = int(current) if current else 0

        if count >= max_attempts:
            ttl = await redis.ttl(key)
            retry_after = max(ttl, 1)
            logger.warning(
                f"Auth rate limit exceeded: {action} from {client_ip} ({count}/{max_attempts})"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many {action} attempts. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        await pipe.execute()

    except HTTPException:
        raise
    except (ConnectionError, TimeoutError, RedisError, OSError) as e:
        logger.error(f"Redis unavailable for auth rate limiting: {e}")
        # Fail-open
