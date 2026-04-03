import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSSE } from "@/hooks/useSSE";
import type { GlassBoxAction } from "@/lib/glassBoxReducer";

// ---------------------------------------------------------------------------
// Helpers for mocking fetch-based SSE (ReadableStream)
// ---------------------------------------------------------------------------

const SESSION_ID = "test-session-123";
const EMAIL = "investor@example.com";
const MAX_TURNS = 15;

/** Encode an SSE frame: optional id + data line, terminated by double newline */
function sseFrame(data: string, id?: string): string {
  let frame = "";
  if (id) frame += `id: ${id}\n`;
  frame += `data: ${data}\n\n`;
  return frame;
}

/** Create a ReadableStream that yields the given chunks, then closes */
function createSSEStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]));
        index++;
      } else {
        controller.close();
      }
    },
  });
}

/** Create a mock Response with a ReadableStream body */
function mockSSEResponse(chunks: string[]): Response {
  return {
    ok: true,
    status: 200,
    body: createSSEStream(chunks),
  } as unknown as Response;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useSSE", () => {
  let dispatch: ReturnType<typeof vi.fn<(action: GlassBoxAction) => void>>;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    dispatch = vi.fn();
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // -----------------------------------------------------------------------
  // Connection URL
  // -----------------------------------------------------------------------

  it("calls fetch with correct URL including sessionId and email", async () => {
    fetchMock.mockResolvedValue(mockSSEResponse([]));

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/v1/negotiation/stream/${SESSION_ID}?email=${encodeURIComponent(EMAIL)}`,
        expect.objectContaining({
          headers: { Accept: "text/event-stream" },
        }),
      );
    });
  });

  it("does not call fetch when sessionId is null", async () => {
    renderHook(() => useSSE(null, EMAIL, MAX_TURNS, dispatch));
    // Give it a tick to ensure nothing fires
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // Connection opened + agent_thought
  // -----------------------------------------------------------------------

  it("dispatches CONNECTION_OPENED and AGENT_THOUGHT on agent_thought event", async () => {
    const payload = {
      event_type: "agent_thought",
      agent_name: "Buyer",
      inner_thought: "I should lowball.",
      turn_number: 1,
    };

    fetchMock.mockResolvedValue(
      mockSSEResponse([sseFrame(JSON.stringify(payload), "evt-1")]),
    );

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({ type: "CONNECTION_OPENED" });
      expect(dispatch).toHaveBeenCalledWith({
        type: "AGENT_THOUGHT",
        payload,
      });
    });
  });

  // -----------------------------------------------------------------------
  // agent_message event
  // -----------------------------------------------------------------------

  it("dispatches AGENT_MESSAGE on agent_message event", async () => {
    const payload = {
      event_type: "agent_message",
      agent_name: "Seller",
      public_message: "I propose $500k.",
      turn_number: 2,
      proposed_price: 500000,
    };

    fetchMock.mockResolvedValue(
      mockSSEResponse([sseFrame(JSON.stringify(payload))]),
    );

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({
        type: "AGENT_MESSAGE",
        payload,
      });
    });
  });

  // -----------------------------------------------------------------------
  // negotiation_complete event
  // -----------------------------------------------------------------------

  it("dispatches NEGOTIATION_COMPLETE on negotiation_complete event", async () => {
    const payload = {
      event_type: "negotiation_complete",
      session_id: SESSION_ID,
      deal_status: "Agreed",
      final_summary: { price: 450000 },
    };

    fetchMock.mockResolvedValue(
      mockSSEResponse([sseFrame(JSON.stringify(payload))]),
    );

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({
        type: "NEGOTIATION_COMPLETE",
        payload,
      });
    });
  });

  // -----------------------------------------------------------------------
  // error event
  // -----------------------------------------------------------------------

  it("dispatches SSE_ERROR on error event", async () => {
    const payload = {
      event_type: "error",
      message: "Something went wrong",
    };

    fetchMock.mockResolvedValue(
      mockSSEResponse([sseFrame(JSON.stringify(payload))]),
    );

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({
        type: "SSE_ERROR",
        payload: { message: "Something went wrong" },
      });
    });
  });

  // -----------------------------------------------------------------------
  // Cleanup on unmount
  // -----------------------------------------------------------------------

  it("aborts fetch on unmount", async () => {
    let abortSignal: AbortSignal | undefined;
    fetchMock.mockImplementation((_url: string, init: RequestInit) => {
      abortSignal = init.signal;
      return new Promise(() => {}); // Never resolves — keeps connection open
    });

    const { unmount } = renderHook(() =>
      useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch),
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    unmount();

    expect(abortSignal?.aborted).toBe(true);
  });

  // -----------------------------------------------------------------------
  // Malformed JSON
  // -----------------------------------------------------------------------

  it("skips malformed JSON without crashing", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    fetchMock.mockResolvedValue(
      mockSSEResponse([sseFrame("not valid json {{{")]),
    );

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    await waitFor(() => {
      expect(warnSpy).toHaveBeenCalledWith(
        "useSSE: skipping malformed JSON event",
        "not valid json {{{",
      );
    });

    // CONNECTION_OPENED dispatched, but no event action for the bad message
    const eventActions = dispatch.mock.calls.filter(
      ([a]) => a.type !== "CONNECTION_OPENED",
    );
    expect(eventActions).toHaveLength(0);

    warnSpy.mockRestore();
  });

  it("continues processing valid events after malformed JSON", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});

    const thoughtPayload = {
      event_type: "agent_thought",
      agent_name: "Buyer",
      inner_thought: "After the bad one",
      turn_number: 1,
    };

    fetchMock.mockResolvedValue(
      mockSSEResponse([
        sseFrame("broken json"),
        sseFrame(JSON.stringify(thoughtPayload)),
      ]),
    );

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({
        type: "AGENT_THOUGHT",
        payload: thoughtPayload,
      });
    });
  });

  // -----------------------------------------------------------------------
  // Reconnect on fetch failure
  // -----------------------------------------------------------------------

  it("attempts reconnect on fetch failure", async () => {
    // First call fails, second succeeds with empty stream
    fetchMock
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce(mockSSEResponse([]));

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    // Wait for reconnect (1s backoff + some buffer)
    await waitFor(
      () => {
        expect(fetchMock).toHaveBeenCalledTimes(2);
      },
      { timeout: 3000 },
    );
  });
});
