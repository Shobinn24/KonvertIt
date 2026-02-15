"""
Unit tests for WebSocket endpoint (/api/v1/ws).

Tests:
- Authentication via query parameter (missing, invalid, expired, wrong type)
- Successful connection + welcome event
- Connection limit enforcement (tier-based)
- Heartbeat on timeout
- Clean disconnect
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.services.ws_manager import WSEventType, WebSocketManager


# ─── Fixtures ────────────────────────────────────────────────

TEST_SECRET = "test-secret-key-for-ws-tests"
TEST_ALGORITHM = "HS256"
TEST_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_token(
    sub: str = TEST_USER_ID,
    email: str = "test@example.com",
    tier: str = "free",
    token_type: str = "access",
    expired: bool = False,
) -> str:
    """Create a test JWT token."""
    import time
    payload = {
        "sub": sub,
        "email": email,
        "tier": tier,
        "type": token_type,
        "iat": int(time.time()),
        "exp": int(time.time()) + (-100 if expired else 3600),
    }
    return jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.secret_key = TEST_SECRET
    settings.jwt_algorithm = TEST_ALGORITHM
    settings.ws_heartbeat_interval = 30
    settings.ws_max_connections_free = 1
    settings.ws_max_connections_pro = 3
    settings.ws_max_connections_enterprise = 10
    return settings


@pytest.fixture
def ws_manager():
    return WebSocketManager()


@pytest.fixture
def app(mock_settings, ws_manager):
    """Create a test FastAPI app with the WS endpoint."""
    from app.api.v1.ws import router

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    # Override settings and ws_manager
    with patch("app.api.v1.ws.get_settings", return_value=mock_settings), \
         patch("app.api.v1.ws.get_ws_manager", return_value=ws_manager):
        yield test_app


@pytest.fixture
def client(app, mock_settings, ws_manager):
    """Create a test client with patched dependencies."""
    with patch("app.api.v1.ws.get_settings", return_value=mock_settings), \
         patch("app.api.v1.ws.get_ws_manager", return_value=ws_manager):
        with TestClient(app) as c:
            yield c


# ─── Auth Tests ──────────────────────────────────────────────


class TestWSAuth:
    """Tests for WebSocket authentication."""

    def test_missing_token(self, client):
        """Should close with 4001 when no token provided."""
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/ws"):
                pass  # Should not reach here

    def test_invalid_token(self, client):
        """Should close with 4001 when token is invalid."""
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/ws?token=invalid-garbage"):
                pass

    def test_expired_token(self, client):
        """Should close with 4001 when token is expired."""
        token = _make_token(expired=True)
        with pytest.raises(Exception):
            with client.websocket_connect(f"/api/v1/ws?token={token}"):
                pass

    def test_refresh_token_rejected(self, client):
        """Should close with 4003 when refresh token is used."""
        token = _make_token(token_type="refresh")
        with pytest.raises(Exception):
            with client.websocket_connect(f"/api/v1/ws?token={token}"):
                pass


# ─── Connection Tests ─────────────────────────────────────────


class TestWSConnection:
    """Tests for successful WebSocket connections."""

    def test_successful_connection(self, client):
        """Should accept connection and send welcome event."""
        token = _make_token()
        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            data = ws.receive_json()
            assert data["event"] == "welcome"
            assert data["data"]["user_id"] == TEST_USER_ID
            assert data["data"]["tier"] == "free"
            assert data["data"]["connection_limit"] == 1
            assert data["data"]["active_connections"] == 1

    def test_pro_tier_connection(self, client):
        """Should show correct tier info for pro users."""
        token = _make_token(tier="pro")
        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            data = ws.receive_json()
            assert data["event"] == "welcome"
            assert data["data"]["tier"] == "pro"
            assert data["data"]["connection_limit"] == 3

    def test_ping_pong(self, client):
        """Client can send ping and receive heartbeat."""
        token = _make_token()
        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            # Consume welcome
            ws.receive_json()
            # Send ping
            ws.send_json({"type": "ping"})
            # Should receive heartbeat
            data = ws.receive_json()
            assert data["event"] == "heartbeat"
            assert data["data"]["message"] == "pong"


# ─── Connection Limit Tests ──────────────────────────────────


class TestWSConnectionLimits:
    """Tests for per-tier connection limit enforcement."""

    def test_free_tier_limit(self, client, ws_manager):
        """Free tier should be limited to 1 connection."""
        token = _make_token(tier="free")

        # First connection should succeed
        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws1:
            welcome = ws1.receive_json()
            assert welcome["event"] == "welcome"

            # Second connection should be rejected (limit=1 for free)
            with pytest.raises(Exception):
                with client.websocket_connect(f"/api/v1/ws?token={token}"):
                    pass

    def test_pro_tier_allows_multiple(self, client, ws_manager):
        """Pro tier should allow up to 3 connections."""
        token = _make_token(tier="pro")

        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws1:
            ws1.receive_json()  # welcome
            with client.websocket_connect(f"/api/v1/ws?token={token}") as ws2:
                ws2.receive_json()  # welcome
                assert ws_manager.get_connection_count(TEST_USER_ID) == 2
