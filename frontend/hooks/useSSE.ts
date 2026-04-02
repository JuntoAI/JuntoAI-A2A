"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { GlassBoxAction } from "@/lib/glassBoxReducer";
import type { SSEEvent } from "@/types/sse";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Hook that manages an SSE connection to the negotiation stream.
 *
 * Opens an EventSource when `sessionId` is non-null, parses incoming
 * JSON events, and dispatches typed actions to the Glass Box reducer.
 *
 * Attempts one reconnect after a 2-second delay on connection error.
 * Cleans up the EventSource on unmount.
 */
export function useSSE(
  sessionId: string | null,
  email: string,
  maxTurns: number,
  dispatch: React.Dispatch<GlassBoxAction>,
): { isConnected: boolean; startTime: number | null; stop: () => void } {
  const [isConnected, setIsConnected] = useState(false);
  const [startTime, setStartTime] = useState<number | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const hasRetriedRef = useRef(false);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(
    (sid: string) => {
      const url = `${API_BASE}/negotiation/stream/${sid}?email=${encodeURIComponent(email)}`;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.onopen = () => {
        hasRetriedRef.current = false;
        setIsConnected(true);
        setStartTime(Date.now());
        dispatch({ type: "CONNECTION_OPENED" });
      };

      es.onmessage = (event: MessageEvent) => {
        let parsed: SSEEvent;
        try {
          parsed = JSON.parse(event.data) as SSEEvent;
        } catch {
          // Skip malformed JSON — log and continue
          console.warn("useSSE: skipping malformed JSON event", event.data);
          return;
        }

        switch (parsed.event_type) {
          case "agent_thought":
            dispatch({ type: "AGENT_THOUGHT", payload: parsed });
            break;
          case "agent_message":
            dispatch({ type: "AGENT_MESSAGE", payload: parsed });
            break;
          case "negotiation_complete":
            dispatch({ type: "NEGOTIATION_COMPLETE", payload: parsed });
            setIsConnected(false);
            es.close();
            break;
          case "error":
            dispatch({
              type: "SSE_ERROR",
              payload: { message: parsed.message },
            });
            setIsConnected(false);
            es.close();
            break;
        }
      };

      es.onerror = () => {
        es.close();
        setIsConnected(false);

        if (!hasRetriedRef.current) {
          // First failure — attempt one reconnect after 2 seconds
          hasRetriedRef.current = true;
          reconnectTimerRef.current = setTimeout(() => {
            connect(sid);
          }, 2000);
        } else {
          // Retry already attempted — give up
          dispatch({
            type: "CONNECTION_ERROR",
            payload: { message: "SSE connection failed after retry" },
          });
        }
      };
    },
    [email, dispatch],
  );

  useEffect(() => {
    if (!sessionId) return;

    hasRetriedRef.current = false;
    connect(sessionId);

    return () => {
      // Cleanup: close EventSource and cancel any pending reconnect timer
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [sessionId, email, connect]);

  const stop = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  return { isConnected, startTime, stop };
}
