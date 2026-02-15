import { getAccessToken } from "./apiClient";
import type { SSEEventType } from "@/types/api";

export interface SSEEvent {
  event: SSEEventType;
  data: Record<string, unknown>;
}

type SSECallback = (event: SSEEvent) => void;

/**
 * Opens an SSE stream via fetch() + ReadableStream.
 * We use fetch (not EventSource) because we need POST + custom headers.
 * Returns an abort function to cancel the stream.
 */
export function startBulkStream(
  urls: string[],
  onEvent: SSECallback,
  onError: (err: Error) => void,
  onDone: () => void,
  options?: { publish?: boolean; sellPrice?: number },
): () => void {
  const controller = new AbortController();

  const body: Record<string, unknown> = { urls };
  if (options?.publish) body.publish = true;
  if (options?.sellPrice != null) body.sell_price = options.sellPrice;

  (async () => {
    try {
      const token = getAccessToken();
      const res = await fetch("/api/v1/conversions/bulk/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        let message = `HTTP ${res.status}`;
        try {
          const json = JSON.parse(text) as { detail?: string };
          if (json.detail) message = json.detail;
        } catch {
          if (text) message = text;
        }
        onError(new Error(message));
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        onError(new Error("No response body"));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        // Last part may be incomplete — keep it in the buffer
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const parsed = parseSSE(part);
          if (parsed) onEvent(parsed);
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        const parsed = parseSSE(buffer);
        if (parsed) onEvent(parsed);
      }

      onDone();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        onDone();
        return;
      }
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  })();

  return () => controller.abort();
}

function parseSSE(raw: string): SSEEvent | null {
  let eventType: SSEEventType | null = null;
  let dataStr = "";

  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim() as SSEEventType;
    } else if (line.startsWith("data:")) {
      dataStr += line.slice(5).trim();
    }
  }

  if (!eventType || !dataStr) return null;

  try {
    const data = JSON.parse(dataStr) as Record<string, unknown>;
    return { event: eventType, data };
  } catch {
    return null;
  }
}
