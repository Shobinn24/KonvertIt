"""
Unit tests for WebSocket connection manager.

Tests:
- WSEvent serialization
- WebSocketManager connect/disconnect lifecycle
- send_to_user delivers to correct user only
- broadcast delivers to all users
- Connection limit enforcement per tier
- Dead connection pruning on send failure
"""

import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from app.services.ws_manager import (
    WS_CONNECTION_LIMITS,
    WSEvent,
    WSEventType,
    WebSocketManager,
)


# ─── Helpers ─────────────────────────────────────────────────


def _mock_ws(connected: bool = True) -> MagicMock:
    """Create a mock WebSocket that appears connected."""
    from starlette.websockets import WebSocketState

    ws = MagicMock()
    ws.send_text = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
    return ws


# ─── WSEvent Tests ───────────────────────────────────────────


class TestWSEvent:
    """Tests for WebSocket event serialization."""

    def test_to_json_basic(self):
        """Should serialize event type, data, and timestamp."""
        event = WSEvent(event=WSEventType.WELCOME, data={"user_id": "abc"})
        raw = event.to_json()
        parsed = json.loads(raw)

        assert parsed["event"] == "welcome"
        assert parsed["data"]["user_id"] == "abc"
        assert "timestamp" in parsed

    def test_to_json_price_alert(self):
        """Should serialize price alert data correctly."""
        event = WSEvent(
            event=WSEventType.PRICE_ALERT,
            data={
                "product_id": "123",
                "old_price": 29.99,
                "new_price": 24.99,
            },
        )
        parsed = json.loads(event.to_json())
        assert parsed["event"] == "price_alert"
        assert parsed["data"]["old_price"] == 29.99
        assert parsed["data"]["new_price"] == 24.99

    def test_to_json_empty_data(self):
        """Should handle empty data dict."""
        event = WSEvent(event=WSEventType.HEARTBEAT)
        parsed = json.loads(event.to_json())
        assert parsed["event"] == "heartbeat"
        assert parsed["data"] == {}

    def test_all_event_types_serializable(self):
        """Every WSEventType should produce valid JSON."""
        for event_type in WSEventType:
            event = WSEvent(event=event_type, data={"test": True})
            parsed = json.loads(event.to_json())
            assert parsed["event"] == event_type.value


# ─── WebSocketManager Connect/Disconnect ─────────────────────


class TestConnect:
    """Tests for connection registration."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    async def test_connect_registers_user(self, manager):
        ws = _mock_ws()
        await manager.connect("user-1", ws)
        assert manager.get_connection_count("user-1") == 1

    async def test_connect_multiple_connections(self, manager):
        ws1, ws2 = _mock_ws(), _mock_ws()
        await manager.connect("user-1", ws1)
        await manager.connect("user-1", ws2)
        assert manager.get_connection_count("user-1") == 2

    async def test_connect_different_users(self, manager):
        ws1, ws2 = _mock_ws(), _mock_ws()
        await manager.connect("user-1", ws1)
        await manager.connect("user-2", ws2)
        assert manager.get_connection_count("user-1") == 1
        assert manager.get_connection_count("user-2") == 1
        assert manager.total_connections == 2

    async def test_disconnect_removes_connection(self, manager):
        ws = _mock_ws()
        await manager.connect("user-1", ws)
        await manager.disconnect("user-1", ws)
        assert manager.get_connection_count("user-1") == 0

    async def test_disconnect_keeps_other_connections(self, manager):
        ws1, ws2 = _mock_ws(), _mock_ws()
        await manager.connect("user-1", ws1)
        await manager.connect("user-1", ws2)
        await manager.disconnect("user-1", ws1)
        assert manager.get_connection_count("user-1") == 1

    async def test_disconnect_unknown_user(self, manager):
        """Should not raise for unknown user."""
        ws = _mock_ws()
        await manager.disconnect("unknown", ws)  # No error

    async def test_disconnect_cleans_up_empty_list(self, manager):
        ws = _mock_ws()
        await manager.connect("user-1", ws)
        await manager.disconnect("user-1", ws)
        # Internal dict should be cleaned up
        assert "user-1" not in manager._connections


# ─── send_to_user Tests ──────────────────────────────────────


class TestSendToUser:
    """Tests for targeted event delivery."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    async def test_sends_to_correct_user(self, manager):
        ws1, ws2 = _mock_ws(), _mock_ws()
        await manager.connect("user-1", ws1)
        await manager.connect("user-2", ws2)

        event = WSEvent(event=WSEventType.PRICE_ALERT, data={"price": 10})
        delivered = await manager.send_to_user("user-1", event)

        assert delivered == 1
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    async def test_sends_to_all_user_connections(self, manager):
        ws1, ws2 = _mock_ws(), _mock_ws()
        await manager.connect("user-1", ws1)
        await manager.connect("user-1", ws2)

        event = WSEvent(event=WSEventType.WELCOME, data={})
        delivered = await manager.send_to_user("user-1", event)

        assert delivered == 2
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    async def test_returns_zero_for_unknown_user(self, manager):
        event = WSEvent(event=WSEventType.HEARTBEAT, data={})
        delivered = await manager.send_to_user("unknown", event)
        assert delivered == 0

    async def test_prunes_dead_connections(self, manager):
        ws_alive = _mock_ws()
        ws_dead = _mock_ws()
        ws_dead.send_text = AsyncMock(side_effect=Exception("Connection closed"))

        await manager.connect("user-1", ws_alive)
        await manager.connect("user-1", ws_dead)

        event = WSEvent(event=WSEventType.HEARTBEAT, data={})
        delivered = await manager.send_to_user("user-1", event)

        assert delivered == 1
        assert manager.get_connection_count("user-1") == 1

    async def test_prunes_disconnected_state_connections(self, manager):
        ws_alive = _mock_ws(connected=True)
        ws_disconnected = _mock_ws(connected=False)

        await manager.connect("user-1", ws_alive)
        await manager.connect("user-1", ws_disconnected)

        event = WSEvent(event=WSEventType.HEARTBEAT, data={})
        delivered = await manager.send_to_user("user-1", event)

        assert delivered == 1
        assert manager.get_connection_count("user-1") == 1

    async def test_message_format(self, manager):
        ws = _mock_ws()
        await manager.connect("user-1", ws)

        event = WSEvent(event=WSEventType.LISTING_UPDATED, data={"listing_id": "L1"})
        await manager.send_to_user("user-1", event)

        sent_raw = ws.send_text.call_args[0][0]
        parsed = json.loads(sent_raw)
        assert parsed["event"] == "listing_updated"
        assert parsed["data"]["listing_id"] == "L1"
        assert "timestamp" in parsed


# ─── broadcast Tests ─────────────────────────────────────────


class TestBroadcast:
    """Tests for broadcast delivery."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    async def test_broadcast_to_all_users(self, manager):
        ws1, ws2, ws3 = _mock_ws(), _mock_ws(), _mock_ws()
        await manager.connect("user-1", ws1)
        await manager.connect("user-2", ws2)
        await manager.connect("user-3", ws3)

        event = WSEvent(event=WSEventType.HEARTBEAT, data={})
        delivered = await manager.broadcast(event)

        assert delivered == 3
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()
        ws3.send_text.assert_called_once()

    async def test_broadcast_empty(self, manager):
        event = WSEvent(event=WSEventType.HEARTBEAT, data={})
        delivered = await manager.broadcast(event)
        assert delivered == 0


# ─── Connection Limits ───────────────────────────────────────


class TestConnectionLimits:
    """Tests for per-tier connection limits."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    def test_default_limits(self):
        assert WS_CONNECTION_LIMITS["free"] == 1
        assert WS_CONNECTION_LIMITS["pro"] == 3
        assert WS_CONNECTION_LIMITS["enterprise"] == 10

    def test_get_connection_limit(self, manager):
        assert manager.get_connection_limit("free") == 1
        assert manager.get_connection_limit("pro") == 3
        assert manager.get_connection_limit("enterprise") == 10
        assert manager.get_connection_limit("unknown") == 1  # fallback

    async def test_connection_count_tracks_correctly(self, manager):
        for i in range(3):
            await manager.connect("user-1", _mock_ws())
        assert manager.get_connection_count("user-1") == 3

    def test_get_connection_count_unknown_user(self, manager):
        assert manager.get_connection_count("nonexistent") == 0


# ─── Heartbeat ───────────────────────────────────────────────


class TestHeartbeat:
    """Tests for heartbeat delivery."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    async def test_send_heartbeat(self, manager):
        ws = _mock_ws()
        await manager.connect("user-1", ws)

        delivered = await manager.send_heartbeat("user-1")

        assert delivered == 1
        sent_raw = ws.send_text.call_args[0][0]
        parsed = json.loads(sent_raw)
        assert parsed["event"] == "heartbeat"
        assert parsed["data"]["message"] == "pong"
