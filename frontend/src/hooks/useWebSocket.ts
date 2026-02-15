/**
 * React hook for WebSocket real-time events.
 *
 * Provides reactive access to the WebSocket connection state
 * and incoming events, with automatic cleanup on unmount.
 *
 * Usage:
 *   // All events
 *   const { lastEvent, isConnected } = useWebSocket();
 *
 *   // Filtered by type
 *   const { lastEvent } = useWebSocket("price_alert");
 */

import { useState, useEffect, useCallback } from "react";
import { wsClient } from "@/services/wsService";
import type { WSEvent, WSEventType } from "@/types/api";

type ConnectionState = "connecting" | "connected" | "disconnected" | "reconnecting";

interface UseWebSocketResult {
  /** Most recently received event (optionally filtered by type). */
  lastEvent: WSEvent | null;
  /** Whether the WebSocket is currently connected. */
  isConnected: boolean;
  /** Current connection state. */
  connectionState: ConnectionState;
  /** All events received since mount (last 50). */
  events: WSEvent[];
}

export function useWebSocket(eventType?: WSEventType): UseWebSocketResult {
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>(wsClient.state);

  useEffect(() => {
    const handleEvent = (event: WSEvent) => {
      setLastEvent(event);
      setEvents((prev) => [...prev.slice(-49), event]);
    };

    const filterType = eventType ?? "*";
    wsClient.addEventListener(filterType, handleEvent);

    const unsubConnection = wsClient.onConnectionChange(setConnectionState);

    return () => {
      wsClient.removeEventListener(filterType, handleEvent);
      unsubConnection();
    };
  }, [eventType]);

  return {
    lastEvent,
    isConnected: connectionState === "connected",
    connectionState,
    events,
  };
}

/**
 * Hook to manage the WebSocket lifecycle tied to auth state.
 *
 * Should be called once in the app root (e.g., AppShell).
 * Connects when authenticated, disconnects on logout.
 */
export function useWebSocketLifecycle(isAuthenticated: boolean): void {
  useEffect(() => {
    if (isAuthenticated) {
      wsClient.connect();
    } else {
      wsClient.close();
    }

    return () => {
      wsClient.close();
    };
  }, [isAuthenticated]);
}
