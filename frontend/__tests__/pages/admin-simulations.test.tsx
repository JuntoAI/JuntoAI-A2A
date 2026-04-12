import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

import AdminSimulationsPage from "@/app/admin/simulations/page";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockSimulationsResponse = {
  simulations: [
    {
      session_id: "abc12345-6789-0000-1111-222233334444",
      scenario_id: "talent-war",
      owner_email: "alice@example.com",
      deal_status: "Agreed",
      turn_count: 6,
      max_turns: 15,
      total_tokens_used: 1200,
      active_toggles: ["competing-offer"],
      model_overrides: { Buyer: "gemini-3-flash-preview" },
      created_at: "2025-01-15T10:30:00Z",
    },
    {
      session_id: "def67890-abcd-1111-2222-333344445555",
      scenario_id: "ma-buyout",
      owner_email: null,
      deal_status: "Blocked",
      turn_count: 10,
      max_turns: 15,
      total_tokens_used: 3500,
      active_toggles: [],
      model_overrides: {},
      created_at: null,
    },
  ],
  next_cursor: "2025-01-15T10:30:00Z",
};

const mockSimulationsNoMore = {
  simulations: [
    {
      session_id: "ghi11111-2222-3333-4444-555566667777",
      scenario_id: "b2b-sales",
      owner_email: "bob@example.com",
      deal_status: "Failed",
      turn_count: 15,
      max_turns: 15,
      total_tokens_used: 5000,
      active_toggles: [],
      model_overrides: {},
      created_at: "2025-03-01T08:00:00Z",
    },
  ],
  next_cursor: null,
};

// ---------------------------------------------------------------------------
// Tests — Validates: Requirements 5.6
// ---------------------------------------------------------------------------

describe("AdminSimulationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockSimulationsResponse,
    });
  });

  // Validates: Req 5.6 — table columns
  it("renders simulation table with correct columns", async () => {
    await act(async () => {
      render(<AdminSimulationsPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("abc12345")).toBeInTheDocument();
    });

    // Column headers (use selector to avoid matching filter labels)
    expect(screen.getByText("Session ID")).toBeInTheDocument();
    expect(screen.getByText("Scenario", { selector: "th" })).toBeInTheDocument();
    expect(screen.getByText("User Email", { selector: "th" })).toBeInTheDocument();
    expect(screen.getByText("Outcome", { selector: "th" })).toBeInTheDocument();
    expect(screen.getByText("Turns", { selector: "th" })).toBeInTheDocument();
    expect(screen.getByText("AI Tokens", { selector: "th" })).toBeInTheDocument();
    expect(screen.getByText("Created", { selector: "th" })).toBeInTheDocument();
  });

  it("renders simulation data with truncated session IDs", async () => {
    await act(async () => {
      render(<AdminSimulationsPage />);
    });

    await waitFor(() => {
      // Session IDs truncated to 8 chars
      expect(screen.getByText("abc12345")).toBeInTheDocument();
      expect(screen.getByText("def67890")).toBeInTheDocument();
    });

    // Scenario IDs
    expect(screen.getByText("talent-war")).toBeInTheDocument();
    expect(screen.getByText("ma-buyout")).toBeInTheDocument();

    // Owner emails
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();

    // Turn counts
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  // Filter controls
  it("renders filter controls for scenario, outcome, and email", async () => {
    await act(async () => {
      render(<AdminSimulationsPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("abc12345")).toBeInTheDocument();
    });

    // Scenario text input
    expect(screen.getByPlaceholderText("e.g. talent-war")).toBeInTheDocument();

    // Outcome dropdown
    expect(screen.getByText("All Outcomes")).toBeInTheDocument();

    // Email text input
    expect(screen.getByPlaceholderText("user@example.com")).toBeInTheDocument();
  });

  it("sends filter params when outcome filter is changed", async () => {
    await act(async () => {
      render(<AdminSimulationsPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("abc12345")).toBeInTheDocument();
    });

    mockFetch.mockClear();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockSimulationsNoMore,
    });

    const outcomeSelect = screen.getByDisplayValue("All Outcomes");
    await act(async () => {
      fireEvent.change(outcomeSelect, { target: { value: "Agreed" } });
    });

    await waitFor(() => {
      const lastCall = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
      expect(lastCall[0]).toContain("deal_status=Agreed");
    });
  });

  // Pagination
  it("shows Load More button when next_cursor is present", async () => {
    await act(async () => {
      render(<AdminSimulationsPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("abc12345")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /load more/i })).toBeInTheDocument();
  });

  it("hides Load More button when next_cursor is null", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockSimulationsNoMore,
    });

    await act(async () => {
      render(<AdminSimulationsPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("ghi11111")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument();
  });

  // Row click navigates to detail page
  it("navigates to detail page when a row is clicked", async () => {
    await act(async () => {
      render(<AdminSimulationsPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("abc12345")).toBeInTheDocument();
    });

    const firstRow = screen.getByText("abc12345").closest("tr")!;
    await act(async () => {
      fireEvent.click(firstRow);
    });

    expect(mockPush).toHaveBeenCalledWith(
      "/admin/simulations/abc12345-6789-0000-1111-222233334444",
    );
  });

  it("shows error message on API failure", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
    });

    await act(async () => {
      render(<AdminSimulationsPage />);
    });

    await waitFor(() => {
      expect(screen.getByText(/session expired/i)).toBeInTheDocument();
    });
  });
});
