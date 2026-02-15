/**
 * Global WebSocket toast notification handler.
 *
 * Mounts once in AppShell. Listens for all WS events and
 * shows toast notifications for actionable events.
 *
 * Also manages the WebSocket lifecycle (connect on auth, disconnect on logout).
 */

import { useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { useWebSocket, useWebSocketLifecycle } from "@/hooks/useWebSocket";
import { useAuthContext } from "@/contexts/AuthContext";
import { Toaster } from "@/components/ui/toaster";
import type { WSEvent } from "@/types/api";

function formatPriceAlert(data: Record<string, unknown>): {
  title: string;
  description: string;
} {
  const title = (data.title as string) || "Product";
  const oldPrice = data.old_price as number;
  const newPrice = data.new_price as number;
  const direction = newPrice < oldPrice ? "dropped" : "increased";
  return {
    title: `Price ${direction}`,
    description: `${title}: $${oldPrice.toFixed(2)} → $${newPrice.toFixed(2)}`,
  };
}

function formatListingUpdated(data: Record<string, unknown>): {
  title: string;
  description: string;
} {
  const title = (data.title as string) || "Listing";
  const action = data.action as string;
  if (action === "price_updated") {
    const price = data.new_price as number;
    return {
      title: "Listing price updated",
      description: `${title}: new price $${price.toFixed(2)}`,
    };
  }
  if (action === "ended") {
    return {
      title: "Listing ended",
      description: `${title} has been delisted`,
    };
  }
  return { title: "Listing updated", description: title };
}

function formatConversionComplete(data: Record<string, unknown>): {
  title: string;
  description: string;
} {
  const url = (data.url as string) || "";
  const status = (data.status as string) || "completed";
  const shortUrl = url.length > 50 ? url.slice(0, 47) + "..." : url;
  return {
    title: status === "completed" ? "Conversion complete" : "Conversion failed",
    description: shortUrl,
  };
}

function formatRateLimitWarning(data: Record<string, unknown>): {
  title: string;
  description: string;
} {
  const used = data.used as number;
  const limit = data.limit as number;
  const pct = data.pct_used as number;
  return {
    title: "Rate limit warning",
    description: `${pct}% used (${used}/${limit} conversions today)`,
  };
}

export function WebSocketToast() {
  const { isAuthenticated } = useAuthContext();
  const { lastEvent } = useWebSocket();
  const { toast } = useToast();

  // Manage WS lifecycle with auth state
  useWebSocketLifecycle(isAuthenticated);

  // React to incoming WS events
  useEffect(() => {
    if (!lastEvent) return;

    let toastData: { title: string; description: string; variant?: "default" | "destructive" } | null = null;

    switch (lastEvent.event) {
      case "price_alert":
        toastData = formatPriceAlert(lastEvent.data);
        break;
      case "listing_updated":
        toastData = formatListingUpdated(lastEvent.data);
        break;
      case "conversion_complete": {
        const info = formatConversionComplete(lastEvent.data);
        const status = lastEvent.data.status as string;
        toastData = {
          ...info,
          variant: status === "failed" ? "destructive" : "default",
        };
        break;
      }
      case "rate_limit_warning":
        toastData = {
          ...formatRateLimitWarning(lastEvent.data),
          variant: "destructive",
        };
        break;
      // welcome, heartbeat, error — no toast
    }

    if (toastData) {
      toast(toastData);
    }
  }, [lastEvent, toast]);

  return <Toaster />;
}
