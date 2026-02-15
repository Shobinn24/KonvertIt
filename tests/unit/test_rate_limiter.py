"""
Tests for Redis-backed rate limiting.

Verifies:
1. Rate limit checking and counter increment logic
2. Tier-based limits (free, pro, enterprise)
3. 429 response with correct headers when exceeded
4. Bulk URL counting (N URLs = N conversions)
5. Redis key pattern and TTL
6. Enterprise unlimited bypass
7. Integration with conversion endpoints
8. Graceful handling of Redis connection errors (fail-open)
"""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import create_app
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limiter import (
    TIER_RATE_LIMITS,
    RateLimitInfo,
    _check_rate_limit,
    _get_rate_limit_key,
    _get_reset_timestamp,
    _get_seconds_until_reset,
    add_rate_limit_headers,
    check_conversion_rate_limit,
    get_redis,
)


# ─── Test Constants ────────────────────────────────────────

TEST_USER_ID = str(uuid.uuid4())

TEST_USER_FREE = {
    "sub": TEST_USER_ID,
    "email": "free@example.com",
    "tier": "free",
    "type": "access",
}

TEST_USER_PRO = {
    "sub": TEST_USER_ID,
    "email": "pro@example.com",
    "tier": "pro",
    "type": "access",
}

TEST_USER_ENTERPRISE = {
    "sub": TEST_USER_ID,
    "email": "enterprise@example.com",
    "tier": "enterprise",
    "type": "access",
}


# ─── Helper: Create mock Redis pipeline ───────────────────


def _mock_redis(current_count=None, new_count=None):
    """Create a mock Redis client with pipeline support."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=str(current_count) if current_count is not None else None)

    mock_pipe = AsyncMock()
    mock_pipe.incrby = MagicMock(return_value=mock_pipe)
    mock_pipe.expire = MagicMock(return_value=mock_pipe)
    mock_pipe.execute = AsyncMock(
        return_value=[new_count if new_count is not None else (current_count or 0) + 1, True]
    )
    mock.pipeline = MagicMock(return_value=mock_pipe)

    return mock


# ─── Tier Limits Tests ────────────────────────────────────


class TestTierLimits:
    """Verify tier limit configuration."""

    def test_free_tier_limits(self):
        """Free tier should have 50 daily conversions and 100 max listings."""
        assert TIER_RATE_LIMITS["free"]["daily_conversions"] == 50
        assert TIER_RATE_LIMITS["free"]["max_listings"] == 100

    def test_pro_tier_limits(self):
        """Pro tier should have 500 daily conversions and 5000 max listings."""
        assert TIER_RATE_LIMITS["pro"]["daily_conversions"] == 500
        assert TIER_RATE_LIMITS["pro"]["max_listings"] == 5000

    def test_enterprise_unlimited(self):
        """Enterprise tier should be unlimited (-1)."""
        assert TIER_RATE_LIMITS["enterprise"]["daily_conversions"] == -1
        assert TIER_RATE_LIMITS["enterprise"]["max_listings"] == -1

    def test_unknown_tier_defaults_to_free(self):
        """Unknown tier should fall back to free tier limits."""
        limits = TIER_RATE_LIMITS.get("unknown", TIER_RATE_LIMITS["free"])
        assert limits["daily_conversions"] == 50


# ─── Redis Key Pattern Tests ─────────────────────────────


class TestRedisKeyPattern:
    """Verify Redis key construction and time helpers."""

    def test_key_contains_user_id(self):
        """Key should contain the user ID."""
        key = _get_rate_limit_key("user-123")
        assert "user-123" in key

    def test_key_contains_today_date(self):
        """Key should contain today's UTC date."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        key = _get_rate_limit_key("user-123")
        assert today in key

    def test_key_has_correct_prefix(self):
        """Key should start with ratelimit:conversions: prefix."""
        key = _get_rate_limit_key("user-123")
        assert key.startswith("ratelimit:conversions:")

    def test_reset_timestamp_is_future(self):
        """Reset timestamp should be in the future."""
        reset_ts = _get_reset_timestamp()
        now_ts = int(datetime.now(UTC).timestamp())
        assert reset_ts > now_ts

    def test_reset_timestamp_is_within_24h(self):
        """Reset timestamp should be within 24 hours."""
        reset_ts = _get_reset_timestamp()
        now_ts = int(datetime.now(UTC).timestamp())
        assert reset_ts - now_ts <= 86400

    def test_seconds_until_reset_is_positive(self):
        """Seconds until reset should always be positive (at least 1)."""
        seconds = _get_seconds_until_reset()
        assert seconds >= 1

    def test_seconds_until_reset_within_24h(self):
        """Seconds until reset should be within 24 hours."""
        seconds = _get_seconds_until_reset()
        assert seconds <= 86400


# ─── Core Rate Limit Check Tests ─────────────────────────


class TestRateLimitCheck:
    """Test the core _check_rate_limit function."""

    @pytest.mark.asyncio
    async def test_first_request_succeeds(self):
        """First request of the day should succeed with remaining = limit - 1."""
        mock_redis = _mock_redis(current_count=None, new_count=1)

        info = await _check_rate_limit("user-1", "free", 1, mock_redis)

        assert info.limit == 50
        assert info.remaining == 49
        assert info.current_count == 1

    @pytest.mark.asyncio
    async def test_increments_counter(self):
        """Should increment Redis counter via pipeline."""
        mock_redis = _mock_redis(current_count=10, new_count=11)

        info = await _check_rate_limit("user-1", "free", 1, mock_redis)

        assert info.current_count == 11
        assert info.remaining == 39

    @pytest.mark.asyncio
    async def test_limit_exactly_reached(self):
        """Request that exactly reaches the limit should succeed."""
        mock_redis = _mock_redis(current_count=49, new_count=50)

        info = await _check_rate_limit("user-1", "free", 1, mock_redis)

        assert info.remaining == 0
        assert info.current_count == 50

    @pytest.mark.asyncio
    async def test_limit_exceeded_raises_429(self):
        """Request exceeding the limit should raise 429."""
        mock_redis = _mock_redis(current_count=50)

        with pytest.raises(HTTPException) as exc_info:
            await _check_rate_limit("user-1", "free", 1, mock_redis)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_429_includes_rate_limit_headers(self):
        """429 response should include X-RateLimit-* and Retry-After headers."""
        mock_redis = _mock_redis(current_count=50)

        with pytest.raises(HTTPException) as exc_info:
            await _check_rate_limit("user-1", "free", 1, mock_redis)

        headers = exc_info.value.headers
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert "Retry-After" in headers
        assert headers["X-RateLimit-Limit"] == "50"
        assert headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_429_detail_includes_usage_info(self):
        """429 detail should include usage info, tier, and upgrade hint."""
        mock_redis = _mock_redis(current_count=50)

        with pytest.raises(HTTPException) as exc_info:
            await _check_rate_limit("user-1", "free", 1, mock_redis)

        detail = exc_info.value.detail
        assert detail["error"] == "Daily conversion limit exceeded"
        assert detail["limit"] == 50
        assert detail["used"] == 50
        assert detail["requested"] == 1
        assert detail["remaining"] == 0
        assert detail["tier"] == "free"
        assert "upgrade" in detail["upgrade_hint"].lower()

    @pytest.mark.asyncio
    async def test_enterprise_skips_redis(self):
        """Enterprise tier should not touch Redis at all."""
        mock_redis = _mock_redis()

        info = await _check_rate_limit("user-1", "enterprise", 1, mock_redis)

        assert info.limit == -1
        assert info.remaining == -1
        assert info.current_count == 0
        mock_redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_pro_tier_has_higher_limit(self):
        """Pro tier should allow 500/day."""
        mock_redis = _mock_redis(current_count=400, new_count=401)

        info = await _check_rate_limit("user-1", "pro", 1, mock_redis)

        assert info.limit == 500
        assert info.remaining == 99

    @pytest.mark.asyncio
    async def test_unknown_tier_uses_free_limit(self):
        """Unknown tier should fall back to free limits."""
        mock_redis = _mock_redis(current_count=50)

        with pytest.raises(HTTPException) as exc_info:
            await _check_rate_limit("user-1", "unknown_tier", 1, mock_redis)

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["limit"] == 50

    @pytest.mark.asyncio
    async def test_sets_ttl_on_pipeline(self):
        """Should call expire on the pipeline for key TTL."""
        mock_redis = _mock_redis(current_count=0, new_count=1)

        await _check_rate_limit("user-1", "free", 1, mock_redis)

        pipe = mock_redis.pipeline.return_value
        pipe.incrby.assert_called_once()
        pipe.expire.assert_called_once()


# ─── Bulk Rate Limit Tests ───────────────────────────────


class TestBulkRateLimit:
    """Test bulk conversion rate limit counting."""

    @pytest.mark.asyncio
    async def test_bulk_counts_all_urls(self):
        """Bulk request with 5 URLs should consume 5 from quota."""
        mock_redis = _mock_redis(current_count=10, new_count=15)

        info = await _check_rate_limit("user-1", "free", 5, mock_redis)

        assert info.current_count == 15
        assert info.remaining == 35

    @pytest.mark.asyncio
    async def test_bulk_rejected_if_would_exceed(self):
        """Bulk request that would exceed limit should be fully rejected."""
        mock_redis = _mock_redis(current_count=48)

        with pytest.raises(HTTPException) as exc_info:
            await _check_rate_limit("user-1", "free", 5, mock_redis)

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["remaining"] == 2
        assert exc_info.value.detail["requested"] == 5

    @pytest.mark.asyncio
    async def test_bulk_exactly_fills_quota(self):
        """Bulk request that exactly fills remaining quota should succeed."""
        mock_redis = _mock_redis(current_count=45, new_count=50)

        info = await _check_rate_limit("user-1", "free", 5, mock_redis)

        assert info.remaining == 0
        assert info.current_count == 50


# ─── Rate Limit Headers Tests ────────────────────────────


class TestRateLimitHeaders:
    """Test header injection helper."""

    def test_add_headers_to_response(self):
        """Should add all three X-RateLimit-* headers."""
        mock_response = MagicMock()
        mock_response.headers = {}

        info = RateLimitInfo(limit=50, remaining=30, reset_timestamp=1700000000, current_count=20)
        add_rate_limit_headers(mock_response, info)

        assert mock_response.headers["X-RateLimit-Limit"] == "50"
        assert mock_response.headers["X-RateLimit-Remaining"] == "30"
        assert mock_response.headers["X-RateLimit-Reset"] == "1700000000"

    def test_enterprise_headers_show_unlimited(self):
        """Enterprise tier should show 'unlimited' in headers."""
        mock_response = MagicMock()
        mock_response.headers = {}

        info = RateLimitInfo(limit=-1, remaining=-1, reset_timestamp=1700000000, current_count=0)
        add_rate_limit_headers(mock_response, info)

        assert mock_response.headers["X-RateLimit-Limit"] == "unlimited"
        assert mock_response.headers["X-RateLimit-Remaining"] == "unlimited"

    def test_add_headers_to_dict(self):
        """Should work with plain dict (for StreamingResponse headers)."""
        headers = {"X-Job-ID": "abc"}

        info = RateLimitInfo(limit=50, remaining=25, reset_timestamp=1700000000, current_count=25)
        add_rate_limit_headers(headers, info)

        assert headers["X-RateLimit-Limit"] == "50"
        assert headers["X-RateLimit-Remaining"] == "25"
        assert headers["X-Job-ID"] == "abc"  # Existing headers preserved


# ─── Redis Fail-Open Tests ───────────────────────────────


class TestRedisFailOpen:
    """Test graceful handling when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_connection_error_allows_request(self):
        """If Redis is down, should allow the request (fail-open)."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis unavailable"))

        info = await _check_rate_limit("user-1", "free", 1, mock_redis)

        assert info.limit == 50
        assert info.remaining == -1  # Unknown
        assert info.current_count == -1

    @pytest.mark.asyncio
    async def test_timeout_error_allows_request(self):
        """If Redis times out, should allow the request (fail-open)."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=TimeoutError("Redis timeout"))

        info = await _check_rate_limit("user-1", "free", 1, mock_redis)

        assert info.limit == 50
        assert info.remaining == -1

    @pytest.mark.asyncio
    async def test_os_error_allows_request(self):
        """If Redis has OS error, should allow the request (fail-open)."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=OSError("Connection refused"))

        info = await _check_rate_limit("user-1", "free", 1, mock_redis)

        assert info.limit == 50
        assert info.remaining == -1


# ─── RateLimitInfo Dataclass Tests ────────────────────────


class TestRateLimitInfo:
    """Test RateLimitInfo dataclass."""

    def test_create_info(self):
        """Should create a RateLimitInfo with all fields."""
        info = RateLimitInfo(limit=50, remaining=30, reset_timestamp=1700000000, current_count=20)
        assert info.limit == 50
        assert info.remaining == 30
        assert info.reset_timestamp == 1700000000
        assert info.current_count == 20

    def test_unlimited_info(self):
        """Should create unlimited RateLimitInfo for enterprise."""
        info = RateLimitInfo(limit=-1, remaining=-1, reset_timestamp=1700000000, current_count=0)
        assert info.limit == -1
        assert info.remaining == -1


# ─── Endpoint Integration Tests ──────────────────────────


def _make_app_with_overrides(user_payload, redis_mock=None):
    """Create a test app with auth and Redis overrides."""
    application = create_app()

    application.dependency_overrides[get_current_user] = lambda: user_payload

    if redis_mock is None:
        redis_mock = _mock_redis(current_count=0, new_count=1)

    async def mock_get_redis():
        return redis_mock

    application.dependency_overrides[get_redis] = mock_get_redis

    # Mock DB
    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    async def mock_get_db():
        yield mock_session

    application.dependency_overrides[get_db] = mock_get_db

    return application


class TestEndpointIntegration:
    """Test rate limiting integrated with FastAPI endpoints."""

    def test_conversion_returns_rate_headers(self):
        """POST /conversions should include rate limit headers."""
        app = _make_app_with_overrides(TEST_USER_FREE)
        client = TestClient(app)

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"status": "completed"}

        mock_svc = MagicMock()
        mock_svc.convert_url = AsyncMock(return_value=mock_result)

        @asynccontextmanager
        async def _mock_ctx():
            yield mock_svc

        with patch("app.api.v1.conversions._conversion_service_context", _mock_ctx):
            resp = client.post(
                "/api/v1/conversions/",
                json={"url": "https://amazon.com/dp/B09C5RG6KV"},
            )

        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "50"

        app.dependency_overrides.clear()

    def test_conversion_429_when_exceeded(self):
        """POST /conversions should return 429 when limit exceeded."""
        redis_mock = _mock_redis(current_count=50)
        app = _make_app_with_overrides(TEST_USER_FREE, redis_mock)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/conversions/",
            json={"url": "https://amazon.com/dp/B09C5RG6KV"},
        )

        assert resp.status_code == 429
        data = resp.json()
        assert data["detail"]["error"] == "Daily conversion limit exceeded"
        assert data["detail"]["limit"] == 50
        assert "X-RateLimit-Limit" in resp.headers

        app.dependency_overrides.clear()

    def test_preview_returns_rate_headers(self):
        """POST /conversions/preview should include rate limit headers."""
        app = _make_app_with_overrides(TEST_USER_FREE)
        client = TestClient(app)

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"status": "preview"}

        mock_svc = MagicMock()
        mock_svc.preview_conversion = AsyncMock(return_value=mock_result)

        @asynccontextmanager
        async def _mock_ctx():
            yield mock_svc

        with patch("app.api.v1.conversions._conversion_service_context", _mock_ctx):
            resp = client.post(
                "/api/v1/conversions/preview",
                json={"url": "https://amazon.com/dp/B09C5RG6KV"},
            )

        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "50"

        app.dependency_overrides.clear()

    def test_preview_429_when_exceeded(self):
        """POST /conversions/preview should return 429 when limit exceeded."""
        redis_mock = _mock_redis(current_count=50)
        app = _make_app_with_overrides(TEST_USER_FREE, redis_mock)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/conversions/preview",
            json={"url": "https://amazon.com/dp/B09C5RG6KV"},
        )

        assert resp.status_code == 429

        app.dependency_overrides.clear()

    def test_enterprise_user_never_rate_limited(self):
        """Enterprise users should never receive 429."""
        app = _make_app_with_overrides(TEST_USER_ENTERPRISE)
        client = TestClient(app)

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"status": "completed"}

        mock_svc = MagicMock()
        mock_svc.convert_url = AsyncMock(return_value=mock_result)

        @asynccontextmanager
        async def _mock_ctx():
            yield mock_svc

        with patch("app.api.v1.conversions._conversion_service_context", _mock_ctx):
            resp = client.post(
                "/api/v1/conversions/",
                json={"url": "https://amazon.com/dp/B09C5RG6KV"},
            )

        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "unlimited"

        app.dependency_overrides.clear()

    def test_list_conversions_not_rate_limited(self):
        """GET /conversions should NOT have rate limit headers."""
        app = _make_app_with_overrides(TEST_USER_FREE)
        client = TestClient(app)

        with patch("app.api.v1.conversions.ConversionRepository") as MockRepo:
            MockRepo.return_value.find_by_user = AsyncMock(return_value=[])
            resp = client.get("/api/v1/conversions/")

        assert resp.status_code == 200
        # GET endpoints should NOT have rate limit headers
        assert "X-RateLimit-Limit" not in resp.headers

        app.dependency_overrides.clear()

    def test_bulk_429_with_url_count(self):
        """POST /conversions/bulk should count URLs and return 429 if over limit."""
        redis_mock = _mock_redis(current_count=48)
        app = _make_app_with_overrides(TEST_USER_FREE, redis_mock)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/conversions/bulk",
            json={"urls": [
                "https://amazon.com/dp/B001",
                "https://amazon.com/dp/B002",
                "https://amazon.com/dp/B003",
                "https://amazon.com/dp/B004",
                "https://amazon.com/dp/B005",
            ]},
        )

        assert resp.status_code == 429
        data = resp.json()
        assert data["detail"]["requested"] == 5
        assert data["detail"]["remaining"] == 2

        app.dependency_overrides.clear()

    def test_bulk_success_with_rate_headers(self):
        """POST /conversions/bulk should return rate headers on success."""
        redis_mock = _mock_redis(current_count=10, new_count=12)
        app = _make_app_with_overrides(TEST_USER_FREE, redis_mock)
        client = TestClient(app)

        mock_progress = MagicMock()
        mock_progress.to_dict.return_value = {"total": 2, "completed": 2}

        mock_svc = MagicMock()
        mock_svc.convert_bulk = AsyncMock(return_value=mock_progress)

        @asynccontextmanager
        async def _mock_ctx():
            yield mock_svc

        with patch("app.api.v1.conversions._conversion_service_context", _mock_ctx):
            resp = client.post(
                "/api/v1/conversions/bulk",
                json={"urls": [
                    "https://amazon.com/dp/B001",
                    "https://amazon.com/dp/B002",
                ]},
            )

        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers

        app.dependency_overrides.clear()

    def test_pro_user_higher_limit(self):
        """Pro user should see 500 as their limit in headers."""
        app = _make_app_with_overrides(TEST_USER_PRO)
        client = TestClient(app)

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"status": "completed"}

        mock_svc = MagicMock()
        mock_svc.convert_url = AsyncMock(return_value=mock_result)

        @asynccontextmanager
        async def _mock_ctx():
            yield mock_svc

        with patch("app.api.v1.conversions._conversion_service_context", _mock_ctx):
            resp = client.post(
                "/api/v1/conversions/",
                json={"url": "https://amazon.com/dp/B09C5RG6KV"},
            )

        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "500"

        app.dependency_overrides.clear()


# ─── Health Check Still Works ─────────────────────────────


class TestHealthCheckNoRateLimit:
    """Health check should work without rate limiting or auth."""

    def test_health_no_rate_limit(self):
        """GET /health should not require rate limiting."""
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" not in resp.headers
