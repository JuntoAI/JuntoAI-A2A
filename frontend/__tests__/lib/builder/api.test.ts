import { describe, it, expect, vi, beforeEach } from "vitest";
import { saveScenario, listCustomScenarios, deleteCustomScenario } from "@/lib/builder/api";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("saveScenario", () => {
  it("posts scenario JSON and returns response", async () => {
    const body = { scenario_id: "s1", name: "Test", readiness_score: 80, tier: "Ready" };
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(body) });

    const result = await saveScenario("u@e.com", { name: "Test" });
    expect(result).toEqual(body);
    expect(mockFetch).toHaveBeenCalledWith("/api/v1/builder/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "u@e.com", scenario_json: { name: "Test" } }),
    });
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
});

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
