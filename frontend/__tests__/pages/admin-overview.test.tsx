import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockCookieStore = {
  get: vi.fn(),
};

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => mockCookieStore),
}));

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

import AdminOverviewPage from "@/app/admin/page";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockOverviewData = {
  total_users: 1234,
  simulations_today: 56,
  active_sse_connections: 8,
  ai_tokens_today: 98765,
  scenario_analytics: [
    { scenario_id: "talent-war", run_count: 30, avg_tokens_used: 1500.5 },
    { scenario_id: "ma-buyout", run_count: 20, avg_tokens_used: 2200.0 },
  ],
  model_performance: [
    {
      model_id: "gemini-2.5-flash",
      avg_latency_ms: 450.2,
      avg_input_tokens: 800.0,
      avg_output_tokens: 200.0,
      error_count: 2,
      total_calls: 150,
    },
    {
      model_id: "claude-sonnet-4",
      avg_latency_ms: 620.8,
      avg_input_tokens: 900.0,
      avg_output_tokens: 300.0,
      error_count: 0,
      total_calls: 100,
    },
  ],
  recent_simulations: [
    {
      session_id: "abc12345-6789-0000-1111-222233334444",
      scenario_id: "talent-war",
      deal_status: "Agreed",
      turn_count: 6,
      total_tokens_used: 1200,
      owner_email: "user@example.com",
      created_at: "2025-01-15T10:30:00Z",
    },
    {
      session_id: "def12345-6789-0000-1111-222233334444",
      scenario_id: "ma-buyout",
      deal_status: "Blocked",
      turn_count: 10,
      total_tokens_used: 3500,
      owner_email: null,
      created_at: null,
    },
  ],
};

// ---------------------------------------------------------------------------
// Tests — Validates: Requirements 3.1, 3.5, 3.6, 3.7
// ---------------------------------------------------------------------------

describe("AdminOverviewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCookieStore.get.mockReturnValue({ value: "valid-session-token" });
  });

  it("renders stat cards with correct data", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockOverviewData,
    });

    const page = await AdminOverviewPage();
    render(page);

    // Stat cards — Validates: Req 3.1, 3.2, 3.3, 3.4
    expect(screen.getByText("Total Users")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("Simulations Today")).toBeInTheDocument();
    expect(screen.getByText("56")).toBeInTheDocument();
    expect(screen.getByText("Active SSE Connections")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("AI Tokens Today")).toBeInTheDocument();
    expect(screen.getByText("98,765")).toBeInTheDocument();
  });

  it("renders scenario analytics table", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockOverviewData,
    });

    const page = await AdminOverviewPage();
    render(page);

    // Validates: Req 3.5
    expect(screen.getByText("Scenario Analytics")).toBeInTheDocument();
    // talent-war appears in both scenario analytics and recent simulations
    expect(screen.getAllByText("talent-war").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("ma-buyout").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("1500.5")).toBeInTheDocument();
    expect(screen.getByText("2200.0")).toBeInTheDocument();
  });

  it("renders model performance table", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockOverviewData,
    });

    const page = await AdminOverviewPage();
    render(page);

    // Validates: Req 3.6
    expect(screen.getByText("Model Performance")).toBeInTheDocument();
    expect(screen.getByText("gemini-2.5-flash")).toBeInTheDocument();
    expect(screen.getByText("claude-sonnet-4")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("renders recent simulations feed", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockOverviewData,
    });

    const page = await AdminOverviewPage();
    render(page);

    // Validates: Req 3.7
    expect(screen.getByText("Recent Simulations")).toBeInTheDocument();
    // Session IDs truncated to 8 chars
    expect(screen.getByText("abc12345")).toBeInTheDocument();
    expect(screen.getByText("def12345")).toBeInTheDocument();
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
  });

  it("shows not authenticated message when no cookie", async () => {
    mockCookieStore.get.mockReturnValue(undefined);

    const page = await AdminOverviewPage();
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

    const page = await AdminOverviewPage();
    render(page);

    expect(screen.getByText(/unable to load dashboard/i)).toBeInTheDocument();
  });

  it("shows error when fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    const page = await AdminOverviewPage();
    render(page);

    expect(screen.getByText(/unable to load dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/failed to reach the api server/i)).toBeInTheDocument();
  });
});
