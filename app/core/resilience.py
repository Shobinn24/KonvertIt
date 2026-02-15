"""
Resilience patterns for KonvertIt — Circuit Breaker and Retry with Backoff.

These patterns protect the scraping pipeline from cascading failures
and provide graceful degradation when source marketplaces are unavailable.
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from enum import StrEnum
from functools import wraps
from typing import Any

from app.core.exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


# ─── Circuit Breaker ──────────────────────────────────────────


class CircuitState(StrEnum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation, requests flow through
    OPEN = "open"           # Failures exceeded threshold, requests blocked
    HALF_OPEN = "half_open" # Cooldown expired, testing with single request


class CircuitBreaker:
    """
    Circuit breaker that tracks consecutive failures per source.

    States:
        CLOSED: Normal. Failure counter increments on failure, resets on success.
        OPEN: After `failure_threshold` consecutive failures within `window_seconds`,
              all requests immediately raise CircuitBreakerOpenError.
              Remains open for `cooldown_seconds`.
        HALF_OPEN: After cooldown, one test request is allowed through.
              If it succeeds → CLOSED. If it fails → OPEN for another cooldown.

    Usage:
        breaker = CircuitBreaker(name="amazon")
        async with breaker:
            result = await scrape_amazon(url)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        cooldown_seconds: int = 300,
        window_seconds: int = 600,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.window_seconds = window_seconds

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._failure_timestamps: list[float] = []
        self._last_failure_time: float = 0.0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        """Get current state, checking if cooldown has expired."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    f"Circuit breaker '{self.name}' transitioned to HALF_OPEN "
                    f"after {elapsed:.0f}s cooldown"
                )
        return self._state

    @property
    def cooldown_remaining(self) -> float:
        """Seconds remaining in the cooldown period (0 if not open)."""
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.monotonic() - self._opened_at
        return max(0.0, self.cooldown_seconds - elapsed)

    def _prune_old_failures(self) -> None:
        """Remove failure timestamps outside the tracking window."""
        cutoff = time.monotonic() - self.window_seconds
        self._failure_timestamps = [t for t in self._failure_timestamps if t > cutoff]

    def record_success(self) -> None:
        """Record a successful request — resets failure count and closes circuit."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker '{self.name}' CLOSED after successful test request")

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._failure_timestamps.clear()

    def record_failure(self) -> None:
        """Record a failed request — may trip the circuit to OPEN."""
        now = time.monotonic()
        self._failure_count += 1
        self._failure_timestamps.append(now)
        self._last_failure_time = now

        self._prune_old_failures()

        if self._state == CircuitState.HALF_OPEN:
            # Test request failed — reopen circuit
            self._state = CircuitState.OPEN
            self._opened_at = now
            logger.warning(
                f"Circuit breaker '{self.name}' re-OPENED "
                f"(half-open test request failed)"
            )
        elif len(self._failure_timestamps) >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = now
            logger.warning(
                f"Circuit breaker '{self.name}' OPENED "
                f"({len(self._failure_timestamps)} failures in "
                f"{self.window_seconds}s window)"
            )

    async def __aenter__(self) -> "CircuitBreaker":
        """Check circuit state before allowing a request through."""
        current_state = self.state  # This checks cooldown transitions

        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                source=self.name,
                cooldown_remaining=self.cooldown_remaining,
            )

        if current_state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker '{self.name}' allowing test request (HALF_OPEN)")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Record success or failure based on whether an exception occurred."""
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure()
        # Don't suppress exceptions
        return False


# ─── Retry with Exponential Backoff ───────────────────────────


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 2.0,
    multiplier: float = 2.0,
    jitter_pct: float = 0.25,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Async retry decorator with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Starting delay in seconds.
        multiplier: Delay multiplier per attempt (2.0 = double each time).
        jitter_pct: Random jitter as percentage of delay (0.25 = ±25%).
        retryable_exceptions: Tuple of exception types that trigger a retry.
            Non-matching exceptions pass through immediately.

    Backoff schedule (with base_delay=2, multiplier=2):
        Attempt 1: ~2s  (± 25% jitter → 1.5s-2.5s)
        Attempt 2: ~4s  (± 25% jitter → 3.0s-5.0s)
        Attempt 3: ~8s  (± 25% jitter → 6.0s-10.0s)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff + jitter
                    delay = base_delay * (multiplier ** attempt)
                    jitter = delay * jitter_pct * (2 * random.random() - 1)
                    actual_delay = max(0, delay + jitter)

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {actual_delay:.1f}s..."
                    )

                    await asyncio.sleep(actual_delay)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator
