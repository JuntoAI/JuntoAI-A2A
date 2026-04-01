import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSSE } from "@/hooks/useSSE";
import type { GlassBoxAction } from "@/lib/glassBoxReducer";

// ---------------------------------------------------------------------------
// Mock EventSource
// ---------------------------------------------------------------------------

type EventSourceHandler = ((event: Event) => void) | null;
type MessageHandler = ((event: MessageEvent) => void) | null;

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  onopen: EventSourceHandler = null;
  onmessage: MessageHandler = null;
  onerror: EventSourceHandler = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  /** Simulate the connection opening */
  simulateOpen() {
    this.onopen?.(new Event("open"));
  }

  /** Simulate an incoming message with a JSON data payload */
  simulateMessage(data: string) {
    this.onmessage?.(new MessageEvent("message", { data }));
  }

  /** Simulate a connection error */
  simulateError() {
    this.onerror?.(new Event("error"));
  }
}

// Install mock globally (jsdom has no EventSource)
vi.stubGlobal("EventSource", MockEventSource);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SESSION_ID = "test-session-123";
const EMAIL = "investor@example.com";
const MAX_TURNS = 15;
const API_BASE = "http://localhost:8000/api/v1";

function latestES(): MockEventSource {
  return MockEventSource.instances[MockEventSource.instances.length - 1];
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useSSE", () => {
  let dispatch: ReturnType<typeof vi.fn<(action: GlassBoxAction) => void>>;

  beforeEach(() => {
    MockEventSource.instances = [];
    dispatch = vi.fn();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  // -----------------------------------------------------------------------
  // Connection URL
  // -----------------------------------------------------------------------

  it("opens EventSource with correct URL including sessionId and email", () => {
    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    expect(MockEventSource.instances).toHaveLength(1);
    const es = latestES();
    expect(es.url).toBe(
      `${API_BASE}/negotiation/stream/${SESSION_ID}?email=${encodeURIComponent(EMAIL)}`,
    );
  });

  it("does not open EventSource when sessionId is null", () => {
    renderHook(() => useSSE(null, EMAIL, MAX_TURNS, dispatch));
    expect(MockEventSource.instances).toHaveLength(0);
  });

  // -----------------------------------------------------------------------
  // Connection opened
  // -----------------------------------------------------------------------

  it("dispatches CONNECTION_OPENED and returns isConnected=true on open", () => {
    const { result } = renderHook(() =>
      useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch),
    );

    act(() => latestES().simulateOpen());

    expect(dispatch).toHaveBeenCalledWith({ type: "CONNECTION_OPENED" });
    expect(result.current.isConnected).toBe(true);
    expect(result.current.startTime).toBeGreaterThan(0);
  });

  // -----------------------------------------------------------------------
  // agent_thought event
  // -----------------------------------------------------------------------

  it("dispatches AGENT_THOUGHT on agent_thought event", () => {
    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    const payload = {
      event_type: "agent_thought",
      agent_name: "Buyer",
      inner_thought: "I should lowball.",
      turn_number: 1,
    };

    act(() => {
      latestES().simulateOpen();
      latestES().simulateMessage(JSON.stringify(payload));
    });

    expect(dispatch).toHaveBeenCalledWith({
      type: "AGENT_THOUGHT",
      payload,
    });
  });

  // -----------------------------------------------------------------------
  // agent_message event
  // -----------------------------------------------------------------------

  it("dispatches AGENT_MESSAGE on agent_message event", () => {
    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    const payload = {
      event_type: "agent_message",
      agent_name: "Seller",
      public_message: "I propose $500k.",
      turn_number: 2,
      proposed_price: 500000,
    };

    act(() => {
      latestES().simulateOpen();
      latestES().simulateMessage(JSON.stringify(payload));
    });

    expect(dispatch).toHaveBeenCalledWith({
      type: "AGENT_MESSAGE",
      payload,
    });
  });

  // -----------------------------------------------------------------------
  // negotiation_complete event
  // -----------------------------------------------------------------------

  it("dispatches NEGOTIATION_COMPLETE on negotiation_complete event", () => {
    const { result } = renderHook(() =>
      useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch),
    );

    const payload = {
      event_type: "negotiation_complete",
      session_id: SESSION_ID,
      deal_status: "Agreed",
      final_summary: { price: 450000 },
    };

    act(() => {
      latestES().simulateOpen();
      latestES().simulateMessage(JSON.stringify(payload));
    });

    expect(dispatch).toHaveBeenCalledWith({
      type: "NEGOTIATION_COMPLETE",
      payload,
    });
    // Hook should close the connection and set isConnected=false
    expect(latestES().close).toHaveBeenCalled();
    expect(result.current.isConnected).toBe(false);
  });

  // -----------------------------------------------------------------------
  // error event
  // -----------------------------------------------------------------------

  it("dispatches SSE_ERROR on error event", () => {
    const { result } = renderHook(() =>
      useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch),
    );

    const payload = {
      event_type: "error",
      message: "Something went wrong",
    };

    act(() => {
      latestES().simulateOpen();
      latestES().simulateMessage(JSON.stringify(payload));
    });

    expect(dispatch).toHaveBeenCalledWith({
      type: "SSE_ERROR",
      payload: { message: "Something went wrong" },
    });
    expect(latestES().close).toHaveBeenCalled();
    expect(result.current.isConnected).toBe(false);
  });

  // -----------------------------------------------------------------------
  // Cleanup on unmount
  // -----------------------------------------------------------------------

  it("calls eventSource.close() on unmount", () => {
    const { unmount } = renderHook(() =>
      useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch),
    );

    const es = latestES();
    act(() => es.simulateOpen());

    unmount();

    expect(es.close).toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // Reconnect after 2-second delay on error
  // -----------------------------------------------------------------------

  it("attempts reconnect after 2-second delay on connection error", () => {
    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    const firstES = latestES();

    // Simulate connection error (first attempt)
    act(() => firstES.simulateError());

    expect(firstES.close).toHaveBeenCalled();
    // No new EventSource yet — waiting for 2s timer
    expect(MockEventSource.instances).toHaveLength(1);

    // Advance timer by 2 seconds
    act(() => vi.advanceTimersByTime(2000));

    // A second EventSource should have been created (reconnect)
    expect(MockEventSource.instances).toHaveLength(2);
    const secondES = latestES();
    expect(secondES.url).toBe(firstES.url);
  });

  it("dispatches CONNECTION_ERROR after retry also fails", () => {
    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    const firstES = latestES();

    // First error → triggers reconnect timer
    act(() => firstES.simulateError());
    act(() => vi.advanceTimersByTime(2000));

    const secondES = latestES();

    // Second error → gives up
    act(() => secondES.simulateError());

    expect(dispatch).toHaveBeenCalledWith({
      type: "CONNECTION_ERROR",
      payload: { message: "SSE connection failed after retry" },
    });
  });

  // -----------------------------------------------------------------------
  // Malformed JSON
  // -----------------------------------------------------------------------

  it("skips malformed JSON without crashing", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    act(() => {
      latestES().simulateOpen();
      latestES().simulateMessage("not valid json {{{");
    });

    // CONNECTION_OPENED dispatched, but no event action for the bad message
    const eventActions = dispatch.mock.calls.filter(
      ([a]) => a.type !== "CONNECTION_OPENED",
    );
    expect(eventActions).toHaveLength(0);

    // Console.warn was called
    expect(warnSpy).toHaveBeenCalledWith(
      "useSSE: skipping malformed JSON event",
      "not valid json {{{",
    );

    warnSpy.mockRestore();
  });

  it("continues processing valid events after malformed JSON", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});

    renderHook(() => useSSE(SESSION_ID, EMAIL, MAX_TURNS, dispatch));

    const thoughtPayload = {
      event_type: "agent_thought",
      agent_name: "Buyer",
      inner_thought: "After the bad one",
      turn_number: 1,
    };

    act(() => {
      latestES().simulateOpen();
      latestES().simulateMessage("broken json");
      latestES().simulateMessage(JSON.stringify(thoughtPayload));
    });

    expect(dispatch).toHaveBeenCalledWith({
      type: "AGENT_THOUGHT",
      payload: thoughtPayload,
    });
  });
});
