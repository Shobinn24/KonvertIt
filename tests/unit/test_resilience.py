"""
Tests for the resilience layer — Circuit Breaker and Retry with Backoff.
"""

import time

import pytest

from app.core.exceptions import CircuitBreakerOpenError, ScrapingError
from app.core.resilience import CircuitBreaker, CircuitState, retry_with_backoff

# ─── Circuit Breaker Tests ────────────────────────────────────


class TestCircuitBreaker:
    """Tests for CircuitBreaker state machine."""

    def test_initial_state_is_closed(self):
        breaker = CircuitBreaker(name="test")
        assert breaker.state == CircuitState.CLOSED

    def test_stays_closed_on_success(self):
        breaker = CircuitBreaker(name="test", failure_threshold=5)
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0

    def test_stays_closed_under_threshold(self):
        breaker = CircuitBreaker(name="test", failure_threshold=5)
        for _ in range(4):
            breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

    def test_opens_at_failure_threshold(self):
        breaker = CircuitBreaker(name="test", failure_threshold=5)
        for _ in range(5):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        breaker = CircuitBreaker(name="test", failure_threshold=5)
        for _ in range(4):
            breaker.record_failure()
        breaker.record_success()
        assert breaker._failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_transitions_to_half_open_after_cooldown(self):
        breaker = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=1)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Simulate cooldown passing
        breaker._opened_at = time.monotonic() - 2
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_closes_on_success(self):
        breaker = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=0)
        breaker.record_failure()
        breaker.record_failure()

        # Force cooldown expiry
        breaker._opened_at = time.monotonic() - 1
        assert breaker.state == CircuitState.HALF_OPEN

        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self):
        breaker = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=1)
        breaker.record_failure()
        breaker.record_failure()

        # Force half-open
        breaker._opened_at = time.monotonic() - 2
        assert breaker.state == CircuitState.HALF_OPEN

        breaker.record_failure()
        assert breaker._state == CircuitState.OPEN

    def test_cooldown_remaining_when_open(self):
        breaker = CircuitBreaker(name="test", failure_threshold=1, cooldown_seconds=300)
        breaker.record_failure()
        assert breaker.cooldown_remaining > 0
        assert breaker.cooldown_remaining <= 300

    def test_cooldown_remaining_when_closed(self):
        breaker = CircuitBreaker(name="test")
        assert breaker.cooldown_remaining == 0.0

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        breaker = CircuitBreaker(name="test")
        async with breaker:
            pass  # Simulates successful operation
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_context_manager_failure(self):
        breaker = CircuitBreaker(name="test", failure_threshold=5)
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("test error")
        assert breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_context_manager_blocks_when_open(self):
        breaker = CircuitBreaker(name="test", failure_threshold=1, cooldown_seconds=300)
        breaker.record_failure()  # Trips the breaker

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            async with breaker:
                pass
        assert exc_info.value.source == "test"
        assert exc_info.value.cooldown_remaining > 0

    def test_old_failures_pruned_outside_window(self):
        breaker = CircuitBreaker(
            name="test", failure_threshold=3, window_seconds=10
        )
        # Record failures "in the past" outside the window
        old_time = time.monotonic() - 20
        breaker._failure_timestamps = [old_time, old_time + 1]
        breaker.record_failure()

        # Only 1 recent failure should remain after pruning
        assert len(breaker._failure_timestamps) == 1
        assert breaker.state == CircuitState.CLOSED


# ─── Retry with Backoff Tests ─────────────────────────────────


class TestRetryWithBackoff:
    """Tests for the retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await always_succeeds()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ScrapingError("temporary failure")
            return "ok"

        result = await fails_twice()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ScrapingError("persistent failure")

        with pytest.raises(ScrapingError, match="persistent failure"):
            await always_fails()

        # Initial attempt + 2 retries = 3 total
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_passes_through(self):
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ScrapingError,),
        )
        async def raises_unexpected():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            await raises_unexpected()

        # Should not retry — only 1 call
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_backoff_timing(self):
        """Verify that delays increase exponentially (roughly)."""
        timestamps = []

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.05,
            multiplier=2.0,
            jitter_pct=0.0,  # No jitter for predictable timing
        )
        async def fails_with_timing():
            timestamps.append(time.monotonic())
            raise ScrapingError("fail")

        with pytest.raises(ScrapingError):
            await fails_with_timing()

        assert len(timestamps) == 3

        # First delay should be ~0.05s
        delay_1 = timestamps[1] - timestamps[0]
        assert 0.03 <= delay_1 <= 0.15

        # Second delay should be ~0.10s (doubled)
        delay_2 = timestamps[2] - timestamps[1]
        assert 0.06 <= delay_2 <= 0.25

    @pytest.mark.asyncio
    async def test_jitter_adds_randomness(self):
        """Verify that jitter produces varying delays."""
        delays = []

        async def _run_one_trial():
            ts = []

            @retry_with_backoff(
                max_retries=1,
                base_delay=0.1,
                jitter_pct=0.25,
            )
            async def fails_once():
                ts.append(time.monotonic())
                raise ScrapingError("fail")

            with pytest.raises(ScrapingError):
                await fails_once()
            return ts

        for _ in range(5):
            timestamps = await _run_one_trial()
            if len(timestamps) >= 2:
                delays.append(timestamps[1] - timestamps[0])

        # With 25% jitter on 0.1s base, delays should vary
        # Not all delays should be identical (statistically very unlikely with jitter)
        if len(delays) >= 3:
            assert not all(
                abs(d - delays[0]) < 0.001 for d in delays
            ), "Jitter should produce varying delays"
