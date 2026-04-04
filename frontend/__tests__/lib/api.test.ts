import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  fetchScenarios,
  fetchScenarioDetail,
  startNegotiation,
  TokenLimitError,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

const fetchSpy = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchSpy);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// fetchScenarios
// ---------------------------------------------------------------------------

describe("fetchScenarios", () => {
  it("returns scenario list on 200", async () => {
    const data = [
      { id: "talent_war", name: "Talent War", description: "HR scenario" },
    ];
    fetchSpy.mockResolvedValueOnce(jsonResponse(data));

    const result = await fetchScenarios();

    expect(result).toEqual(data);
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/scenarios",
    );
  });

  it("throws with detail on non-2xx", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ detail: "Server error" }, 500),
    );

    await expect(fetchScenarios()).rejects.toThrow("Server error");
  });

  it("throws with statusText when body is not JSON", async () => {
    fetchSpy.mockResolvedValueOnce(
      new Response("bad", { status: 502, statusText: "Bad Gateway" }),
    );

    await expect(fetchScenarios()).rejects.toThrow("Bad Gateway");
  });
});

// ---------------------------------------------------------------------------
// fetchScenarioDetail
// ---------------------------------------------------------------------------

describe("fetchScenarioDetail", () => {
  const scenario = {
    id: "talent_war",
    name: "Talent War",
    description: "HR scenario",
    agents: [
      {
        name: "Recruiter",
        role: "recruiter",
        goals: ["Hire"],
        model_id: "gemini-3-flash-preview",
        type: "negotiator",
      },
    ],
    toggles: [{ id: "competing_offer", label: "Competing Offer" }],
    negotiation_params: { max_turns: 15 },
    outcome_receipt: {
      equivalent_human_time: "2 weeks",
      process_label: "Salary Negotiation",
    },
  };

  it("returns full scenario on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(scenario));

    const result = await fetchScenarioDetail("talent_war");

    expect(result).toEqual(scenario);
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/scenarios/talent_war",
    );
  });

  it("throws with detail on 404", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ detail: "Scenario not found" }, 404),
    );

    await expect(fetchScenarioDetail("nope")).rejects.toThrow(
      "Scenario not found",
    );
  });
});

// ---------------------------------------------------------------------------
// startNegotiation
// ---------------------------------------------------------------------------

describe("startNegotiation", () => {
  it("returns session data on 200", async () => {
    const response = {
      session_id: "uuid-123",
      tokens_remaining: 85,
      max_turns: 15,
    };
    fetchSpy.mockResolvedValueOnce(jsonResponse(response));

    const result = await startNegotiation("user@test.com", "talent_war", [
      "competing_offer",
    ]);

    expect(result).toEqual(response);
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/negotiation/start",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "user@test.com",
          scenario_id: "talent_war",
          active_toggles: ["competing_offer"],
          structured_memory_enabled: false,
          structured_memory_roles: [],
          milestone_summaries_enabled: false,
          no_memory_roles: [],
        }),
      },
    );
  });

  it("throws TokenLimitError on 429", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ detail: "Token limit reached" }, 429),
    );

    const err = await startNegotiation("user@test.com", "talent_war", []).catch(
      (e: unknown) => e,
    );

    expect(err).toBeInstanceOf(TokenLimitError);
    expect((err as TokenLimitError).message).toBe("Token limit reached");
  });

  it("throws generic Error on other 4xx/5xx", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ detail: "Invalid payload" }, 422),
    );

    const err = await startNegotiation("user@test.com", "talent_war", []).catch(
      (e: unknown) => e,
    );

    expect(err).toBeInstanceOf(Error);
    expect(err).not.toBeInstanceOf(TokenLimitError);
    expect((err as Error).message).toBe("Invalid payload");
  });

  it("sends correct payload with empty toggles", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ session_id: "s1", tokens_remaining: 100, max_turns: 10 }),
    );

    await startNegotiation("a@b.com", "ma_buyout", []);

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/negotiation/start",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "a@b.com",
          scenario_id: "ma_buyout",
          active_toggles: [],
          structured_memory_enabled: false,
          structured_memory_roles: [],
          milestone_summaries_enabled: false,
          no_memory_roles: [],
        }),
      },
    );
  });
});

// ---------------------------------------------------------------------------
// startNegotiation — milestone_summaries_enabled
// ---------------------------------------------------------------------------

describe("startNegotiation milestone_summaries_enabled", () => {
  it("includes milestone_summaries_enabled=true in request body when enabled", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ session_id: "s1", tokens_remaining: 90, max_turns: 15 }),
    );

    await startNegotiation(
      "user@test.com",
      "talent_war",
      ["competing_offer"],
      undefined,
      undefined,
      ["recruiter"],
      true,
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/negotiation/start",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"milestone_summaries_enabled":true'),
      }),
    );
  });

  it("includes milestone_summaries_enabled=false when toggle is off", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ session_id: "s2", tokens_remaining: 95, max_turns: 10 }),
    );

    await startNegotiation(
      "user@test.com",
      "ma_buyout",
      [],
      undefined,
      undefined,
      [],
      false,
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/negotiation/start",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"milestone_summaries_enabled":false'),
      }),
    );
  });

  it("defaults milestone_summaries_enabled to false when parameter is omitted", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ session_id: "s3", tokens_remaining: 100, max_turns: 10 }),
    );

    await startNegotiation("a@b.com", "b2b_sales", []);

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/negotiation/start",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"milestone_summaries_enabled":false'),
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// TokenLimitError
// ---------------------------------------------------------------------------

describe("TokenLimitError", () => {
  it("is an instance of Error", () => {
    const err = new TokenLimitError("limit");
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("TokenLimitError");
    expect(err.message).toBe("limit");
  });
});
