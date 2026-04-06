/**
 * SSE client for the AI Scenario Builder chat endpoint.
 *
 * Uses fetch + ReadableStream (not EventSource) because the chat
 * endpoint requires POST with a JSON body.
 */

import type {
  BuilderEventType,
  HealthCheckFinding,
  HealthCheckFullReport,
} from "./types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL || "";

// ---------------------------------------------------------------------------
// Callback interface
// ---------------------------------------------------------------------------

export interface BuilderSSECallbacks {
  onToken: (token: string) => void;
  onJsonDelta: (section: string, data: Record<string, unknown>) => void;
  onComplete: () => void;
  onError: (message: string) => void;
  onHealthStart: () => void;
  onHealthFinding: (finding: HealthCheckFinding) => void;
  onHealthComplete: (report: HealthCheckFullReport) => void;
}

// ---------------------------------------------------------------------------
// SSE line parser
// ---------------------------------------------------------------------------

/**
 * Parse a raw SSE `data:` payload into a typed event and dispatch to the
 * appropriate callback.  Malformed JSON is logged and skipped.
 */
function dispatchEvent(
  json: string,
  callbacks: BuilderSSECallbacks,
): void {
  let parsed: { event_type: BuilderEventType; [key: string]: unknown };
  try {
    parsed = JSON.parse(json);
  } catch {
    console.warn("[builder-sse] Skipping malformed SSE payload:", json);
    return;
  }

  switch (parsed.event_type) {
    case "builder_token":
      callbacks.onToken(parsed.token as string);
      break;
    case "builder_json_delta":
      callbacks.onJsonDelta(
        parsed.section as string,
        parsed.data as Record<string, unknown>,
      );
      break;
    case "builder_complete":
      callbacks.onComplete();
      break;
    case "builder_error":
      callbacks.onError(parsed.message as string);
      break;
    case "builder_health_check_start":
      callbacks.onHealthStart();
      break;
    case "builder_health_check_finding":
      callbacks.onHealthFinding(parsed as unknown as HealthCheckFinding);
      break;
    case "builder_health_check_complete":
      callbacks.onHealthComplete(
        parsed.report as unknown as HealthCheckFullReport,
      );
      break;
    default:
      console.warn("[builder-sse] Unknown event_type:", parsed.event_type);
  }
}

// ---------------------------------------------------------------------------
// Stream reader
// ---------------------------------------------------------------------------

async function readSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  callbacks: BuilderSSECallbacks,
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by double newlines
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      // Extract the data payload (skip id: lines, etc.)
      for (const line of rawEvent.split("\n")) {
        if (line.startsWith("data: ")) {
          dispatchEvent(line.slice(6), callbacks);
        }
      }

      boundary = buffer.indexOf("\n\n");
    }
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

/**
 * Stream a builder chat message via SSE.
 *
 * Implements reconnection with exponential backoff (max 3 retries).
 * Returns an AbortController so the caller can cancel the stream.
 */
export function streamBuilderChat(
  email: string,
  sessionId: string,
  message: string,
  callbacks: BuilderSSECallbacks,
): AbortController {
  const controller = new AbortController();

  (async () => {
    let attempt = 0;

    while (attempt <= MAX_RETRIES) {
      try {
        const res = await fetch(`${BACKEND_URL}/api/v1/builder/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, session_id: sessionId, message }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const detail = await res.text();
          callbacks.onError(detail || `HTTP ${res.status}`);
          return; // Don't retry on HTTP errors (4xx/5xx are intentional)
        }

        if (!res.body) {
          callbacks.onError("Response body is empty");
          return;
        }

        await readSSEStream(res.body.getReader(), callbacks);
        return; // Success — no retry needed
      } catch (err: unknown) {
        if (controller.signal.aborted) return;

        attempt++;
        if (attempt > MAX_RETRIES) {
          callbacks.onError(
            `Connection failed after ${MAX_RETRIES} retries: ${
              err instanceof Error ? err.message : String(err)
            }`,
          );
          return;
        }

        // Exponential backoff: 1s, 2s, 4s
        const delay = BASE_DELAY_MS * Math.pow(2, attempt - 1);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  })();

  return controller;
}
