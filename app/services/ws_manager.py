"""
WebSocket connection manager for real-time push notifications.

Manages per-user WebSocket connections and provides a publish interface
for backend services to push events to connected clients.

This is a **separate** system from SSE (Server-Sent Events).
SSE handles bulk conversion streaming (request-scoped, POST-based).
WebSocket handles persistent push notifications (price alerts, listing
updates, conversion completions, rate limit warnings).

Event Types:
    - welcome: Sent on connect with user info.
    - price_alert: Price change detected by PriceMonitorService.
    - listing_updated: Listing status/price changed.
    - conversion_complete: Background conversion finished.
    - rate_limit_warning: Approaching daily rate limit (80%+).
    - heartbeat: Keep-alive ping sent every N seconds.
    - error: Server-side error notification.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum

from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger(__name__)


class WSEventType(StrEnum):
    """Types of WebSocket events pushed to clients."""

    WELCOME = "welcome"
    PRICE_ALERT = "price_alert"
    LISTING_UPDATED = "listing_updated"
    CONVERSION_COMPLETE = "conversion_complete"
    RATE_LIMIT_WARNING = "rate_limit_warning"
    TIER_CHANGED = "tier_changed"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class WSEvent:
    """A single WebSocket event to be sent to the client."""

    event: WSEventType
    data: dict = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON string for transmission."""
        return json.dumps({
            "event": self.event.value,
            "data": self.data,
            "timestamp": datetime.now(UTC).isoformat(),
        })


# Per-tier connection limits
WS_CONNECTION_LIMITS: dict[str, int] = {
    "free": 1,
    "pro": 3,
    "enterprise": 10,
}


class WebSocketManager:
    """
    Manages WebSocket connections and event delivery.

    Each user can have multiple simultaneous connections (up to their tier
    limit). Events are delivered to ALL connections for a given user.

    Architecture:
    - In-memory connection registry (single-process deployment).
    - Upgrade path: replace with Redis pubsub for multi-worker scaling.
    - Dead connections are silently pruned on send failure.

    Usage:
        manager = WebSocketManager()

        # In WebSocket endpoint:
        await manager.connect(user_id, websocket)
        ...
        await manager.disconnect(user_id, websocket)

        # In any service:
        await manager.send_to_user(user_id, WSEvent(
            event=WSEventType.PRICE_ALERT,
            data={"product_id": "...", "old_price": 29.99, "new_price": 24.99},
        ))
    """

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    @property
    def total_connections(self) -> int:
        """Total number of active WebSocket connections across all users."""
        return sum(len(conns) for conns in self._connections.values())

    def get_connection_count(self, user_id: str) -> int:
        """Get the number of active connections for a user."""
        return len(self._connections.get(user_id, []))

    def get_connection_limit(self, tier: str) -> int:
        """Get the max allowed connections for a tier."""
        return WS_CONNECTION_LIMITS.get(tier, 1)

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        """
        Register a new WebSocket connection for a user.

        Args:
            user_id: The authenticated user's ID.
            ws: The WebSocket connection to register.

        Note: Connection limit checks should be done BEFORE calling this.
        """
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(ws)
        logger.info(
            f"[WS] User {user_id} connected "
            f"({self.get_connection_count(user_id)} active)"
        )

    async def disconnect(self, user_id: str, ws: WebSocket) -> None:
        """
        Remove a WebSocket connection for a user.

        Args:
            user_id: The authenticated user's ID.
            ws: The WebSocket connection to remove.
        """
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(user_id, None)
        logger.info(
            f"[WS] User {user_id} disconnected "
            f"({self.get_connection_count(user_id)} remaining)"
        )

    async def send_to_user(self, user_id: str, event: WSEvent) -> int:
        """
        Send an event to all active connections for a specific user.

        Dead connections are silently pruned on send failure.

        Args:
            user_id: Target user's ID.
            event: The event to send.

        Returns:
            Number of connections the event was successfully delivered to.
        """
        conns = self._connections.get(user_id, [])
        if not conns:
            return 0

        message = event.to_json()
        dead: list[WebSocket] = []
        delivered = 0

        for ws in conns:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
                    delivered += 1
                else:
                    dead.append(ws)
            except Exception:
                logger.debug(f"[WS] Failed to send to user {user_id}, pruning connection")
                dead.append(ws)

        # Prune dead connections
        for ws in dead:
            if ws in conns:
                conns.remove(ws)
        if not conns:
            self._connections.pop(user_id, None)

        return delivered

    async def broadcast(self, event: WSEvent) -> int:
        """
        Send an event to ALL connected users.

        Args:
            event: The event to broadcast.

        Returns:
            Total number of connections the event was delivered to.
        """
        total = 0
        # Iterate over a copy of keys since send_to_user may mutate
        for user_id in list(self._connections.keys()):
            total += await self.send_to_user(user_id, event)
        return total

    async def send_heartbeat(self, user_id: str) -> int:
        """Send a heartbeat event to a specific user."""
        return await self.send_to_user(user_id, WSEvent(
            event=WSEventType.HEARTBEAT,
            data={"message": "pong"},
        ))


# ─── Module-level singleton ──────────────────────────────────

_ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """
    Get the shared WebSocket manager singleton.

    Exposed as a function for testability (can be patched in tests).
    """
    return _ws_manager
