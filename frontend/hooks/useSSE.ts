"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { GlassBoxAction } from "@/lib/glassBoxReducer";
import type { SSEEvent } from "@/types/sse";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/** Max reconnection attempts before giving up. */
const MAX_RETRIES = 5;
/** Base delay in ms for exponential backoff (doubles each attempt). */
const BASE_DELAY_MS = 1_000;
/** Cap the backoff at 16 seconds. */
const MAX_DELAY_MS = 16_000;

/**
 * Hook that manages an SSE connection to the negotiation stream.
 *
 * Uses `fetch` + `ReadableStream` instead of `EventSource` so we can
 * pass `last_event_id` as a query param on reconnect and parse the
 * `id:` field from the SSE wire format.
 *
 * Reconnects with exponential backoff (1s → 2s → 4s → 8s → 16s)
 * up to MAX_RETRIES. Skips reconnect if the session already reached
 * a terminal state (negotiation_complete or error).
 */
export function useSSE(
  sessionId: string | null,
  email: string,
  maxTurns: number,
  dispatch: React.Dispatch<GlassBoxAction>,
): { isConnected: boolean; startTime: number | null; stop: () => void } {
  const [isConnected, setIsConnected] = useState(false);
  const [startTime, setStartTime] = useState<number | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const lastEventIdRef = useRef<string | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isTerminalRef = useRef(false);
  const stoppedRef = useRef(false);

  const connect = useCallback(
    async (sid: string) => {
      if (stoppedRef.current || isTerminalRef.current) return;

      const controller = new AbortController();
      abortRef.current = controller;

      let url = `${API_BASE}/negotiation/stream/${sid}?email=${encodeURIComponent(email)}`;
      if (lastEventIdRef.current) {
        url += `&last_event_id=${lastEventIdRef.current}`;
      }

      try {
        const response = await fetch(url, {
          signal: controller.signal,
          headers: { Accept: "text/event-stream" },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        // Connected successfully — reset retry counter
        retryCountRef.current = 0;
        setIsConnected(true);
        if (!startTime) setStartTime(Date.now());
        dispatch({ type: "CONNECTION_OPENED" });

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE events are separated by double newlines
          const parts = buffer.split("\n\n");
          // Keep the last incomplete chunk in the buffer
          buffer = parts.pop() ?? "";

          for (const raw of parts) {
            if (!raw.trim()) continue;

            let eventId: string | null = null;
            let data: string | null = null;

            for (const line of raw.split("\n")) {
              if (line.startsWith("id: ")) {
                eventId = line.slice(4).trim();
              } else if (line.startsWith("data: ")) {
                data = line.slice(6);
              }
            }

            if (eventId) {
              lastEventIdRef.current = eventId;
            }

            if (!data) continue;

            let parsed: SSEEvent;
            try {
              parsed = JSON.parse(data) as SSEEvent;
            } catch {
              console.warn("useSSE: skipping malformed JSON event", data);
              continue;
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
                isTerminalRef.current = true;
                setIsConnected(false);
                return; // Don't reconnect
              case "error":
                dispatch({
                  type: "SSE_ERROR",
                  payload: { message: parsed.message },
                });
                isTerminalRef.current = true;
                setIsConnected(false);
                return; // Don't reconnect
            }
          }
        }

        // Stream ended without terminal event — server closed connection (deploy drain)
        setIsConnected(false);
        scheduleReconnect(sid);
      } catch (err: unknown) {
        if (controller.signal.aborted) return; // Intentional stop

        setIsConnected(false);

        if (isTerminalRef.current || stoppedRef.current) return;

        scheduleReconnect(sid);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [email, dispatch],
  );

  const scheduleReconnect = useCallback(
    (sid: string) => {
      if (stoppedRef.current || isTerminalRef.current) return;

      if (retryCountRef.current >= MAX_RETRIES) {
        dispatch({
          type: "CONNECTION_ERROR",
          payload: {
            message: `SSE connection failed after ${MAX_RETRIES} reconnection attempts`,
          },
        });
        return;
      }

      const delay = Math.min(
        BASE_DELAY_MS * 2 ** retryCountRef.current,
        MAX_DELAY_MS,
      );
      retryCountRef.current += 1;

      reconnectTimerRef.current = setTimeout(() => {
        connect(sid);
      }, delay);
    },
    [connect, dispatch],
  );

  useEffect(() => {
    if (!sessionId) return;

    // Reset state for new session
    stoppedRef.current = false;
    isTerminalRef.current = false;
    lastEventIdRef.current = null;
    retryCountRef.current = 0;

    connect(sessionId);

    return () => {
      stoppedRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
    };
  }, [sessionId, email, connect]);

  const stop = useCallback(() => {
    stoppedRef.current = true;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsConnected(false);
  }, []);

  return { isConnected, startTime, stop };
}
