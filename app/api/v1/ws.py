"""
WebSocket endpoint for real-time push notifications.

Provides:
- GET /api/v1/ws?token=<jwt> — WebSocket upgrade endpoint

Authentication is via JWT passed as a query parameter (WebSocket
handshake does not support custom Authorization headers).

Close codes:
- 4001: Missing or invalid token
- 4003: Token is not an access token
- 4008: Connection limit exceeded for user's tier
- 1000: Normal closure
- 1011: Unexpected server error
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import get_settings
from app.middleware.auth_middleware import _decode_token
from app.services.ws_manager import (
    WSEvent,
    WSEventType,
    WS_CONNECTION_LIMITS,
    get_ws_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


def _get_tier_limit(tier: str) -> int:
    """Get connection limit for a tier, falling back to config then defaults."""
    settings = get_settings()
    tier_map = {
        "free": settings.ws_max_connections_free,
        "pro": settings.ws_max_connections_pro,
        "enterprise": settings.ws_max_connections_enterprise,
    }
    return tier_map.get(tier, 1)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    WebSocket endpoint for real-time push notifications.

    Connect with: ws://host/api/v1/ws?token=<access_token>

    The server pushes events for:
    - price_alert: Source product price changed
    - listing_updated: eBay listing status/price changed
    - conversion_complete: Background conversion finished
    - rate_limit_warning: Approaching daily rate limit
    - heartbeat: Keep-alive ping every 30s

    The client can send {"type": "ping"} to trigger a heartbeat response.
    """
    settings = get_settings()
    manager = get_ws_manager()

    # ─── Authenticate via query parameter ─────────────────
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    try:
        payload = _decode_token(token, settings)
    except Exception:
        await ws.close(code=4001, reason="Invalid or expired token")
        return

    if payload.get("type") != "access":
        await ws.close(code=4003, reason="Access token required")
        return

    user_id = payload.get("sub", "")
    tier = payload.get("tier", "free")

    # ─── Check connection limit ───────────────────────────
    limit = _get_tier_limit(tier)
    current = manager.get_connection_count(user_id)
    if current >= limit:
        await ws.close(
            code=4008,
            reason=f"Connection limit reached ({limit} for {tier} tier)",
        )
        return

    # ─── Accept connection ────────────────────────────────
    await ws.accept()
    await manager.connect(user_id, ws)

    # Send welcome event
    try:
        welcome = WSEvent(
            event=WSEventType.WELCOME,
            data={
                "user_id": user_id,
                "tier": tier,
                "connection_limit": limit,
                "active_connections": manager.get_connection_count(user_id),
            },
        )
        await ws.send_text(welcome.to_json())
    except Exception:
        await manager.disconnect(user_id, ws)
        return

    # ─── Main event loop ─────────────────────────────────
    try:
        while True:
            try:
                # Wait for client messages with heartbeat timeout
                data = await asyncio.wait_for(
                    ws.receive_text(),
                    timeout=float(settings.ws_heartbeat_interval),
                )

                # Client sent a message — handle ping
                try:
                    import json
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await manager.send_heartbeat(user_id)
                except (ValueError, TypeError):
                    pass  # Ignore malformed messages

            except asyncio.TimeoutError:
                # No message from client within heartbeat interval — send ping
                if ws.client_state == WebSocketState.CONNECTED:
                    heartbeat = WSEvent(
                        event=WSEventType.HEARTBEAT,
                        data={"message": "ping"},
                    )
                    await ws.send_text(heartbeat.to_json())
                else:
                    break

    except WebSocketDisconnect:
        logger.debug(f"[WS] Client disconnected: user {user_id}")
    except Exception as e:
        logger.error(f"[WS] Error for user {user_id}: {e}", exc_info=True)
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                error_event = WSEvent(
                    event=WSEventType.ERROR,
                    data={"error": "Internal server error"},
                )
                await ws.send_text(error_event.to_json())
                await ws.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    finally:
        await manager.disconnect(user_id, ws)
