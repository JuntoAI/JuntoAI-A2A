import { describe, it, expect, vi, beforeEach } from "vitest";
import { saveScenario, listCustomScenarios, deleteCustomScenario } from "@/lib/builder/api";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Helper: build a mock ReadableStream from SSE event strings
// ---------------------------------------------------------------------------

function sseStream(events: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const raw = events.join("");
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(raw));
      controller.close();
    },
  });
}

function sseEvent(data: Record<string, unknown>, id?: number): string {
  const parts: string[] = [];
  if (id !== undefined) parts.push(`id: ${id}`);
  parts.push(`data: ${JSON.stringify(data)}`);
  return parts.join("\n") + "\n\n";
}

function mockSSEResponse(events: string[]) {
  return {
    ok: true,
    body: sseStream(events),
  };
}

// ---------------------------------------------------------------------------
// saveScenario
// ---------------------------------------------------------------------------

describe("saveScenario", () => {
  it("parses SSE stream and returns save_complete payload", async () => {
    const events = [
      sseEvent({ event_type: "builder_health_check_start" }, 1),
      sseEvent({
        event_type: "builder_save_complete",
        scenario_id: "s1",
        name: "Test",
        readiness_score: 80,
        tier: "Ready",
      }, 2),
    ];
    mockFetch.mockResolvedValueOnce(mockSSEResponse(events));

    const result = await saveScenario("u@e.com", { name: "Test" });
    expect(result).toEqual({
      scenario_id: "s1",
      name: "Test",
      readiness_score: 80,
      tier: "Ready",
    });
    expect(mockFetch).toHaveBeenCalledWith("/api/v1/builder/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "u@e.com", scenario_json: { name: "Test" } }),
    });
  });

  it("invokes health check callbacks during stream", async () => {
    const finding = {
      event_type: "builder_health_check_finding",
      check_name: "agent_count",
      severity: "info",
      agent_role: null,
      message: "OK",
    };
    const report = {
      readiness_score: 90,
      tier: "Ready",
      findings: [],
      recommendations: [],
      prompt_quality_scores: [],
      tension_score: 0,
      budget_overlap_score: 0,
      toggle_effectiveness_score: 0,
      turn_sanity_score: 0,
      stall_risk: { stall_risk_score: 0, risks: [] },
    };
    const events = [
      sseEvent({ event_type: "builder_health_check_start" }, 1),
      sseEvent(finding, 2),
      sseEvent({ event_type: "builder_health_check_complete", report }, 3),
      sseEvent({
        event_type: "builder_save_complete",
        scenario_id: "s1",
        name: "T",
        readiness_score: 90,
        tier: "Ready",
      }, 4),
    ];
    mockFetch.mockResolvedValueOnce(mockSSEResponse(events));

    const onHealthStart = vi.fn();
    const onHealthFinding = vi.fn();
    const onHealthComplete = vi.fn();

    await saveScenario("u@e.com", {}, {
      onHealthStart,
      onHealthFinding,
      onHealthComplete,
    });

    expect(onHealthStart).toHaveBeenCalledOnce();
    expect(onHealthFinding).toHaveBeenCalledWith(finding);
    expect(onHealthComplete).toHaveBeenCalledWith(report);
  });

  it("throws on builder_error event", async () => {
    const events = [
      sseEvent({ event_type: "builder_error", message: "Health check error: boom" }, 1),
    ];
    mockFetch.mockResolvedValueOnce(mockSSEResponse(events));

    await expect(saveScenario("u@e.com", {})).rejects.toThrow("Health check error: boom");
  });

  it("throws when stream ends without save_complete", async () => {
    const events = [
      sseEvent({ event_type: "builder_health_check_start" }, 1),
    ];
    mockFetch.mockResolvedValueOnce(mockSSEResponse(events));

    await expect(saveScenario("u@e.com", {})).rejects.toThrow(
      "Save stream ended without a save_complete event",
    );
  });

  it("throws on HTTP error with detail", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      statusText: "Unprocessable",
      json: () => Promise.resolve({ detail: "Invalid scenario" }),
    });
    await expect(saveScenario("u@e.com", {})).rejects.toThrow("Invalid scenario");
  });

  it("throws with message field", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Error",
      json: () => Promise.resolve({ message: "Server error" }),
    });
    await expect(saveScenario("u@e.com", {})).rejects.toThrow("Server error");
  });

  it("falls back to statusText on non-JSON error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: () => Promise.reject(new Error("nope")),
    });
    await expect(saveScenario("u@e.com", {})).rejects.toThrow("Internal Server Error");
  });

  it("falls back to HTTP status when statusText empty", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: "",
      json: () => Promise.reject(new Error("nope")),
    });
    await expect(saveScenario("u@e.com", {})).rejects.toThrow("HTTP 503");
  });

  it("throws when response body is null", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, body: null });
    await expect(saveScenario("u@e.com", {})).rejects.toThrow("Response body is empty");
  });
});


// ---------------------------------------------------------------------------
// listCustomScenarios
// ---------------------------------------------------------------------------

describe("listCustomScenarios", () => {
  it("fetches scenarios for email", async () => {
    const scenarios = [{ scenario_id: "s1", scenario_json: {}, created_at: "", updated_at: "" }];
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(scenarios) });

    const result = await listCustomScenarios("u@e.com");
    expect(result).toEqual(scenarios);
    expect(mockFetch).toHaveBeenCalledWith("/api/v1/builder/scenarios?email=u%40e.com");
  });

  it("throws on error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: () => Promise.resolve({ detail: "No scenarios" }),
    });
    await expect(listCustomScenarios("u@e.com")).rejects.toThrow("No scenarios");
  });
});

// ---------------------------------------------------------------------------
// deleteCustomScenario
// ---------------------------------------------------------------------------

describe("deleteCustomScenario", () => {
  it("sends DELETE request", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true });

    await deleteCustomScenario("u@e.com", "s1");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/builder/scenarios/s1?email=u%40e.com",
      { method: "DELETE" },
    );
  });

  it("throws on error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: () => Promise.resolve({ detail: "Not allowed" }),
    });
    await expect(deleteCustomScenario("u@e.com", "s1")).rejects.toThrow("Not allowed");
  });
});
