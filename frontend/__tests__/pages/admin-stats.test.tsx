import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

/**
 * Feature: 270_public-stats-dashboard
 * Unit tests for the admin stats page.
 *
 * Validates: Requirements 1.2, 2.1, 10.5, 12.4
 */

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockCookieStore = {
  get: vi.fn(),
};

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => mockCookieStore),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

import AdminStatsPage from "@/app/admin/stats/page";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockStatsData = {
  unique_users_today: 42,
  unique_users_7d: 187,
  simulations_today: 156,
  simulations_7d: 1023,
  active_simulations: 3,
  outcomes_today: { agreed: 80, blocked: 12, failed: 8 },
  outcomes_7d: { agreed: 520, blocked: 95, failed: 60 },
  total_tokens_today: 245000,
  total_tokens_7d: 1890000,
  model_tokens: [
    { model_id: "gemini-2.5-flash", tokens_today: 150000, tokens_7d: 1200000 },
    { model_id: "claude-sonnet-4", tokens_today: 95000, tokens_7d: 690000 },
  ],
  model_performance: [
    { model_id: "gemini-2.5-flash", avg_response_time_today: 423.5, avg_response_time_7d: 445.2 },
    { model_id: "claude-sonnet-4", avg_response_time_today: 612.8, avg_response_time_7d: null },
  ],
  scenario_popularity: [
    { scenario_id: "talent-war", scenario_name: "talent-war", count_today: 80, count_7d: 500 },
    { scenario_id: "mna-buyout", scenario_name: "mna-buyout", count_today: 50, count_7d: 350 },
  ],
  avg_turns_today: 6.3,
  avg_turns_7d: 7.1,
  custom_scenarios_today: 5,
  custom_scenarios_7d: 23,
  custom_scenarios_all_time: 89,
  custom_agent_sessions_today: 2,
  custom_agent_sessions_7d: 14,
  custom_agent_sessions_all_time: 45,
  generated_at: "2026-04-11T14:00:00+00:00",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AdminStatsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCookieStore.get.mockReturnValue({ value: "valid-session-token" });
  });

  it("renders top-level stat cards with formatted numbers", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStatsData,
    });

    const page = await AdminStatsPage();
    render(page);

    // Validates: Req 12.4 — comma separators
    expect(screen.getByText("Platform Stats")).toBeInTheDocument();
    expect(screen.getByText("Unique Users")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("187")).toBeInTheDocument();
    expect(screen.getByText("Simulations")).toBeInTheDocument();
    expect(screen.getByText("156")).toBeInTheDocument();
    expect(screen.getByText("1,023")).toBeInTheDocument();
    expect(screen.getByText("Total Tokens")).toBeInTheDocument();
    expect(screen.getByText("245,000")).toBeInTheDocument();
    expect(screen.getByText("1,890,000")).toBeInTheDocument();
  });

  it("renders average turns with one decimal place", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStatsData,
    });

    const page = await AdminStatsPage();
    render(page);

    // Validates: Req 12.4 — one decimal for averages
    expect(screen.getByText("Avg Turns to Resolution")).toBeInTheDocument();
    expect(screen.getByText("6.3")).toBeInTheDocument();
    expect(screen.getByText("7.1")).toBeInTheDocument();
  });

  it("renders active simulations count", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStatsData,
    });

    const page = await AdminStatsPage();
    render(page);

    expect(screen.getByText("Active Simulations")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders outcome breakdown badges", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStatsData,
    });

    const page = await AdminStatsPage();
    render(page);

    // Validates: Req 4.4 — outcome breakdown
    expect(screen.getByText("Outcomes Today")).toBeInTheDocument();
    expect(screen.getByText("Outcomes 7 Days")).toBeInTheDocument();
    // Badges contain "Agreed: 80", "Blocked: 12", etc.
    expect(screen.getByText("Agreed: 80")).toBeInTheDocument();
    expect(screen.getByText("Blocked: 12")).toBeInTheDocument();
    expect(screen.getByText("Failed: 8")).toBeInTheDocument();
  });

  it("renders scenario popularity table", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStatsData,
    });

    const page = await AdminStatsPage();
    render(page);

    expect(screen.getByText("Scenario Popularity")).toBeInTheDocument();
    expect(screen.getAllByText("talent-war").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("mna-buyout").length).toBeGreaterThanOrEqual(1);
  });

  it("renders model token breakdown table", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStatsData,
    });

    const page = await AdminStatsPage();
    render(page);

    expect(screen.getByText("Token Usage by Model")).toBeInTheDocument();
    // Model IDs appear in both token and performance tables
    expect(screen.getAllByText("gemini-2.5-flash").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("claude-sonnet-4").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("150,000")).toBeInTheDocument();
  });

  it("renders model response times table", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStatsData,
    });

    const page = await AdminStatsPage();
    render(page);

    expect(screen.getByText("Model Response Times")).toBeInTheDocument();
    expect(screen.getByText("423.5")).toBeInTheDocument();
    expect(screen.getByText("445.2")).toBeInTheDocument();
  });

  it("renders custom scenario and BYOA metrics", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockStatsData,
    });

    const page = await AdminStatsPage();
    render(page);

    expect(screen.getByText("Custom Scenarios")).toBeInTheDocument();
    expect(screen.getByText("Custom Agent Sessions (BYOA)")).toBeInTheDocument();
    expect(screen.getByText("89")).toBeInTheDocument(); // all-time custom scenarios
    expect(screen.getByText("45")).toBeInTheDocument(); // all-time BYOA
  });

  it("shows not authenticated message when no cookie", async () => {
    mockCookieStore.get.mockReturnValue(undefined);

    const page = await AdminStatsPage();
    render(page);

    expect(screen.getByText(/not authenticated/i)).toBeInTheDocument();
    expect(screen.getByText(/log in/i)).toBeInTheDocument();
  });

  it("shows error when API returns non-200", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    const page = await AdminStatsPage();
    render(page);

    expect(screen.getByText(/unable to load stats/i)).toBeInTheDocument();
  });

  it("shows error when fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    const page = await AdminStatsPage();
    render(page);

    expect(screen.getByText(/unable to load stats/i)).toBeInTheDocument();
    expect(screen.getByText(/failed to reach the api server/i)).toBeInTheDocument();
  });

  it("shows session expired message on 401", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({}),
    });

    const page = await AdminStatsPage();
    render(page);

    expect(screen.getByText(/session expired/i)).toBeInTheDocument();
  });
});
