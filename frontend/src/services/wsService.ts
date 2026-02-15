/**
 * WebSocket client for real-time push notifications.
 *
 * Provides a persistent connection to the backend WebSocket endpoint
 * with automatic reconnection, event dispatch, and heartbeat monitoring.
 *
 * This is SEPARATE from SSE (sseService.ts), which handles bulk
 * conversion streaming. WebSocket is for persistent push notifications.
 */

import { getAccessToken } from "./apiClient";
import type { WSEvent, WSEventType } from "@/types/api";

type WSCallback = (event: WSEvent) => void;
type ConnectionState = "connecting" | "connected" | "disconnected" | "reconnecting";
type ConnectionCallback = (state: ConnectionState) => void;

// Reconnect backoff: 1s → 2s → 4s → 8s → 16s max
const MIN_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 16000;
const HEARTBEAT_TIMEOUT = 45000; // If no message for 45s, reconnect

class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners = new Map<string, Set<WSCallback>>();
  private connectionListeners = new Set<ConnectionCallback>();
  private reconnectDelay = MIN_RECONNECT_DELAY;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;
  private _state: ConnectionState = "disconnected";

  get state(): ConnectionState {
    return this._state;
  }

  get isConnected(): boolean {
    return this._state === "connected";
  }

  /**
   * Connect to the WebSocket endpoint.
   * Uses the JWT access token from localStorage for authentication.
   */
  connect(): void {
    const token = getAccessToken();
    if (!token) {
      this.setState("disconnected");
      return;
    }

    this.intentionalClose = false;
    this.setState("connecting");

    // Build WebSocket URL — use current origin, replace protocol
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws?token=${encodeURIComponent(token)}`;

    try {
      this.ws = new WebSocket(wsUrl);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.setState("connected");
      this.reconnectDelay = MIN_RECONNECT_DELAY;
      this.resetHeartbeatTimer();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      this.resetHeartbeatTimer();

      try {
        const parsed = JSON.parse(event.data as string) as WSEvent;
        this.dispatch(parsed);
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onerror = () => {
      // Error handling is done in onclose
    };

    this.ws.onclose = () => {
      this.clearHeartbeatTimer();
      this.ws = null;

      if (!this.intentionalClose) {
        this.setState("reconnecting");
        this.scheduleReconnect();
      } else {
        this.setState("disconnected");
      }
    };
  }

  /**
   * Cleanly close the WebSocket connection.
   * Does NOT auto-reconnect after this.
   */
  close(): void {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    this.clearHeartbeatTimer();

    if (this.ws) {
      this.ws.close(1000, "Client closing");
      this.ws = null;
    }

    this.setState("disconnected");
  }

  /**
   * Send a ping to the server.
   */
  ping(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "ping" }));
    }
  }

  /**
   * Subscribe to events of a specific type.
   * Use "*" to listen to ALL events.
   */
  addEventListener(type: WSEventType | "*", callback: WSCallback): void {
    const key = type;
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key)!.add(callback);
  }

  /**
   * Unsubscribe from events.
   */
  removeEventListener(type: WSEventType | "*", callback: WSCallback): void {
    this.listeners.get(type)?.delete(callback);
  }

  /**
   * Subscribe to connection state changes.
   */
  onConnectionChange(callback: ConnectionCallback): () => void {
    this.connectionListeners.add(callback);
    return () => this.connectionListeners.delete(callback);
  }

  // ─── Internal ──────────────────────────────────────────────

  private setState(state: ConnectionState): void {
    this._state = state;
    this.connectionListeners.forEach((cb) => {
      try {
        cb(state);
      } catch {
        // Ignore callback errors
      }
    });
  }

  private dispatch(event: WSEvent): void {
    // Dispatch to type-specific listeners
    const typeListeners = this.listeners.get(event.event);
    if (typeListeners) {
      typeListeners.forEach((cb) => {
        try {
          cb(event);
        } catch {
          // Ignore callback errors
        }
      });
    }

    // Dispatch to wildcard listeners
    const wildcardListeners = this.listeners.get("*");
    if (wildcardListeners) {
      wildcardListeners.forEach((cb) => {
        try {
          cb(event);
        } catch {
          // Ignore callback errors
        }
      });
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);

    // Exponential backoff
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, MAX_RECONNECT_DELAY);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private resetHeartbeatTimer(): void {
    this.clearHeartbeatTimer();
    this.heartbeatTimer = setTimeout(() => {
      // No message received within timeout — force reconnect
      if (this.ws) {
        this.ws.close();
      }
    }, HEARTBEAT_TIMEOUT);
  }

  private clearHeartbeatTimer(): void {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
}

/**
 * Singleton WebSocket client instance.
 * Import this in components/hooks to interact with the WS connection.
 */
export const wsClient = new WebSocketClient();
