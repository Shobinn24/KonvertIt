"""
Unit tests for JWT auth middleware — token decoding, FastAPI dependencies.

Tests the _decode_token function and get_current_user/get_current_user_optional
dependencies in isolation (no FastAPI app needed — just function calls).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.config import Settings
from app.middleware.auth_middleware import (
    _decode_token,
    get_current_user,
    get_current_user_optional,
)


# ─── Test Settings ───────────────────────────────────────────


def _test_settings() -> Settings:
    return Settings(
        secret_key="test-secret-key-for-middleware-tests-64-chars-padding-here-ok",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
    )


def _make_token(
    token_type: str = "access",
    user_id: str | None = None,
    email: str = "test@example.com",
    tier: str = "free",
    secret: str | None = None,
    expired: bool = False,
) -> str:
    """Helper to create test JWT tokens."""
    settings = _test_settings()
    now = datetime.now(UTC)

    if expired:
        exp = now - timedelta(hours=1)
    else:
        exp = now + timedelta(hours=1)

    payload = {
        "sub": user_id or str(uuid.uuid4()),
        "email": email,
        "tier": tier,
        "type": token_type,
        "iat": now,
        "exp": exp,
    }

    return jwt.encode(
        payload,
        secret or settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


# ─── _decode_token Tests ────────────────────────────────────


class TestDecodeToken:
    """Tests for the low-level token decoder."""

    def test_decode_valid_token(self):
        """Should decode a valid token."""
        settings = _test_settings()
        token = _make_token()
        payload = _decode_token(token, settings)

        assert "sub" in payload
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"

    def test_decode_expired_token(self):
        """Should raise 401 for expired tokens."""
        settings = _test_settings()
        token = _make_token(expired=True)

        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token, settings)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired" in exc_info.value.detail

    def test_decode_wrong_secret(self):
        """Should raise 401 for tokens signed with wrong secret."""
        settings = _test_settings()
        token = _make_token(secret="wrong-secret-key-padding-here-for-tests-1234")

        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token, settings)

        assert exc_info.value.status_code == 401

    def test_decode_malformed_token(self):
        """Should raise 401 for garbage tokens."""
        settings = _test_settings()

        with pytest.raises(HTTPException) as exc_info:
            _decode_token("not.a.jwt", settings)

        assert exc_info.value.status_code == 401

    def test_decode_token_missing_subject(self):
        """Should raise 401 for tokens without 'sub' claim."""
        settings = _test_settings()
        payload = {
            "email": "test@test.com",
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = jwt.encode(
            payload, settings.secret_key, algorithm=settings.jwt_algorithm
        )

        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token, settings)

        assert exc_info.value.status_code == 401
        assert "missing subject" in exc_info.value.detail


# ─── get_current_user Tests ─────────────────────────────────


class TestGetCurrentUser:
    """Tests for the get_current_user FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_valid_access_token(self):
        """Should return payload for valid access token."""
        settings = _test_settings()
        token = _make_token(token_type="access")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        payload = await get_current_user(credentials=creds, settings=settings)

        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_rejects_refresh_token(self):
        """Should reject refresh tokens on the access-only dependency."""
        settings = _test_settings()
        token = _make_token(token_type="refresh")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=creds, settings=settings)

        assert exc_info.value.status_code == 401
        assert "access token required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejects_expired_token(self):
        """Should raise 401 for expired access tokens."""
        settings = _test_settings()
        token = _make_token(token_type="access", expired=True)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=creds, settings=settings)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_payload_contains_user_info(self):
        """Payload should contain sub, email, and tier."""
        settings = _test_settings()
        user_id = str(uuid.uuid4())
        token = _make_token(
            token_type="access",
            user_id=user_id,
            email="pro@example.com",
            tier="pro",
        )
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        payload = await get_current_user(credentials=creds, settings=settings)

        assert payload["sub"] == user_id
        assert payload["email"] == "pro@example.com"
        assert payload["tier"] == "pro"


# ─── get_current_user_optional Tests ─────────────────────────


class TestGetCurrentUserOptional:
    """Tests for the optional auth dependency."""

    @pytest.mark.asyncio
    async def test_returns_payload_when_valid(self):
        """Should return payload when token is valid."""
        settings = _test_settings()
        token = _make_token(token_type="access")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        payload = await get_current_user_optional(credentials=creds, settings=settings)
        assert payload is not None
        assert payload["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_credentials(self):
        """Should return None when no token is provided."""
        settings = _test_settings()

        payload = await get_current_user_optional(credentials=None, settings=settings)
        assert payload is None

    @pytest.mark.asyncio
    async def test_returns_none_for_expired_token(self):
        """Should return None (not raise) for expired tokens."""
        settings = _test_settings()
        token = _make_token(token_type="access", expired=True)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        payload = await get_current_user_optional(credentials=creds, settings=settings)
        assert payload is None

    @pytest.mark.asyncio
    async def test_returns_none_for_refresh_token(self):
        """Should return None for refresh tokens (not access)."""
        settings = _test_settings()
        token = _make_token(token_type="refresh")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        payload = await get_current_user_optional(credentials=creds, settings=settings)
        assert payload is None

    @pytest.mark.asyncio
    async def test_returns_none_for_malformed_token(self):
        """Should return None for garbage tokens."""
        settings = _test_settings()
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="garbage")

        payload = await get_current_user_optional(credentials=creds, settings=settings)
        assert payload is None
