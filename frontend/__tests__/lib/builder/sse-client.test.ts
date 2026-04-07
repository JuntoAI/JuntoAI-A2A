import { describe, it, expect, vi, beforeEach } from "vitest";

// We need to test dispatchEvent and readSSEStream indirectly through streamBuilderChat.
// Mock fetch at the global level.
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Import after mocking
import { streamBuilderChat, type BuilderSSECallbacks } from "@/lib/builder/sse-client";

function makeCallbacks(): BuilderSSECallbacks & { calls: Record<string, unknown[][]> } {
  const calls: Record<string, unknown[][]> = {};
  const track = (name: string) => (...args: unknown[]) => {
    if (!calls[name]) calls[name] = [];
    calls[name].push(args);
  };
  return {
    calls,
    onToken: track("onToken"),
    onJsonDelta: track("onJsonDelta"),
    onComplete: track("onComplete"),
    onError: track("onError"),
    onHealthStart: track("onHealthStart"),
    onHealthFinding: track("onHealthFinding"),
    onHealthComplete: track("onHealthComplete"),
  };
}

function sseBody(events: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const raw = events.map((e) => `data: ${e}\n\n`).join("");
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(raw));
      controller.close();
    },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("streamBuilderChat", () => {
  it("dispatches builder_token events", async () => {
    const cb = makeCallbacks();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: sseBody([JSON.stringify({ event_type: "builder_token", token: "Hello" })]),
    });

    streamBuilderChat("u@e.com", "sess1", "hi", cb);
    // Wait for async processing
    await vi.waitFor(() => expect(cb.calls.onToken).toBeDefined());
    await vi.waitFor(() => expect(cb.calls.onToken[0]).toEqual(["Hello"]));
  });

  it("dispatches builder_json_delta events", async () => {
    const cb = makeCallbacks();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: sseBody([
        JSON.stringify({ event_type: "builder_json_delta", section: "agents", data: { name: "Bot" } }),
      ]),
    });

    streamBuilderChat("u@e.com", "s1", "msg", cb);
    await vi.waitFor(() => expect(cb.calls.onJsonDelta?.[0]).toEqual(["agents", { name: "Bot" }]));
  });

  it("dispatches builder_complete events", async () => {
    const cb = makeCallbacks();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: sseBody([JSON.stringify({ event_type: "builder_complete" })]),
    });

    streamBuilderChat("u@e.com", "s1", "msg", cb);
    await vi.waitFor(() => expect(cb.calls.onComplete?.length).toBe(1));
  });

  it("dispatches builder_error events", async () => {
    const cb = makeCallbacks();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: sseBody([JSON.stringify({ event_type: "builder_error", message: "oops" })]),
    });

    streamBuilderChat("u@e.com", "s1", "msg", cb);
    await vi.waitFor(() => expect(cb.calls.onError?.[0]).toEqual(["oops"]));
  });

  it("dispatches health check events", async () => {
    const cb = makeCallbacks();
    const finding = {
      event_type: "builder_health_check_finding",
      check_name: "budget",
      severity: "warning",
      agent_role: null,
      message: "Budget overlap",
    };
    const report = { readiness_score: 85, tier: "Ready" };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: sseBody([
        JSON.stringify({ event_type: "builder_health_check_start" }),
        JSON.stringify(finding),
        JSON.stringify({ event_type: "builder_health_check_complete", report }),
      ]),
    });

    streamBuilderChat("u@e.com", "s1", "msg", cb);
    await vi.waitFor(() => expect(cb.calls.onHealthStart?.length).toBe(1));
    await vi.waitFor(() => expect(cb.calls.onHealthFinding?.length).toBe(1));
    await vi.waitFor(() => expect(cb.calls.onHealthComplete?.[0]).toEqual([report]));
  });

  it("calls onError on HTTP error response", async () => {
    const cb = makeCallbacks();
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 429,
      text: () => Promise.resolve("Rate limited"),
    });

    streamBuilderChat("u@e.com", "s1", "msg", cb);
    await vi.waitFor(() => expect(cb.calls.onError?.[0]).toEqual(["Rate limited"]));
  });

  it("calls onError when response body is null", async () => {
    const cb = makeCallbacks();
    mockFetch.mockResolvedValueOnce({ ok: true, body: null });

    streamBuilderChat("u@e.com", "s1", "msg", cb);
    await vi.waitFor(() => expect(cb.calls.onError?.[0]).toEqual(["Response body is empty"]));
  });

  it("skips malformed JSON payloads without crashing", async () => {
    const cb = makeCallbacks();
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: sseBody([
        "not-json",
        JSON.stringify({ event_type: "builder_token", token: "ok" }),
      ]),
    });

    streamBuilderChat("u@e.com", "s1", "msg", cb);
    await vi.waitFor(() => expect(cb.calls.onToken?.[0]).toEqual(["ok"]));
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });

  it("skips unknown event types", async () => {
    const cb = makeCallbacks();
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: sseBody([
        JSON.stringify({ event_type: "unknown_type" }),
        JSON.stringify({ event_type: "builder_complete" }),
      ]),
    });

    streamBuilderChat("u@e.com", "s1", "msg", cb);
    await vi.waitFor(() => expect(cb.calls.onComplete?.length).toBe(1));
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("Unknown event_type"),
      "unknown_type",
    );
    warnSpy.mockRestore();
  });

  it("returns an AbortController", () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: sseBody([JSON.stringify({ event_type: "builder_complete" })]),
    });
    const controller = streamBuilderChat("u@e.com", "s1", "msg", makeCallbacks());
    expect(controller).toBeInstanceOf(AbortController);
  });

  it("does not call onError after abort", async () => {
    const cb = makeCallbacks();
    mockFetch.mockImplementation(() => {
      const err = new Error("aborted");
      err.name = "AbortError";
      return Promise.reject(err);
    });

    const controller = streamBuilderChat("u@e.com", "s1", "msg", cb);
    controller.abort();
    // Give time for async to settle
    await new Promise((r) => setTimeout(r, 100));
    expect(cb.calls.onError).toBeUndefined();
  });
});
