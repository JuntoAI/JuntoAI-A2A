import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

import AdminUsersPage from "@/app/admin/users/page";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockUsersResponse = {
  users: [
    {
      email: "alice@example.com",
      signed_up_at: "2025-01-10T08:00:00Z",
      token_balance: 45,
      last_reset_date: "2025-06-01",
      tier: 3,
      user_status: "active",
    },
    {
      email: "bob@example.com",
      signed_up_at: "2025-02-15T12:00:00Z",
      token_balance: 0,
      last_reset_date: "2025-06-01",
      tier: 1,
      user_status: "suspended",
    },
  ],
  next_cursor: "2025-02-15T12:00:00Z",
  total_count: 100,
};

const mockUsersResponseNoMore = {
  users: [
    {
      email: "charlie@example.com",
      signed_up_at: "2025-03-01T10:00:00Z",
      token_balance: 20,
      last_reset_date: "2025-06-01",
      tier: 2,
      user_status: "active",
    },
  ],
  next_cursor: null,
  total_count: 3,
};

// ---------------------------------------------------------------------------
// Tests — Validates: Requirements 4.8, 4.9
// ---------------------------------------------------------------------------

describe("AdminUsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUsersResponse,
    });
  });

  // Validates: Req 4.8 — table columns
  it("renders user table with correct columns", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    // Column headers (use selector to avoid matching action buttons)
    const headers = Array.from(document.querySelectorAll("th")).map((th) => th.textContent?.trim() ?? "");
    expect(headers).toContain("Email");
    expect(headers).toContain("Tier");
    expect(headers).toContain("Token Balance");
    expect(headers.some((h) => h.startsWith("Status"))).toBe(true);
    expect(headers).toContain("Signed Up");
    expect(headers).toContain("Last Login");
    expect(headers).toContain("Actions");
  });

  it("renders user data in table rows", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
      expect(screen.getByText("bob@example.com")).toBeInTheDocument();
    });

    // Tier badges (use selector to avoid matching dropdown options)
    expect(screen.getByText("Tier 3", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("Tier 1", { selector: "span" })).toBeInTheDocument();

    // Token balances
    expect(screen.getByText("45")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();

    // Status badges (use selector to avoid matching dropdown options)
    expect(screen.getByText("active", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("suspended", { selector: "span" })).toBeInTheDocument();
  });

  // Validates: Req 4.9 — filter controls
  it("renders tier and status filter dropdowns", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    // Tier filter options
    expect(screen.getByText("All Tiers")).toBeInTheDocument();
    expect(screen.getByText("Tier 1", { selector: "option" })).toBeInTheDocument();
    expect(screen.getByText("Tier 2", { selector: "option" })).toBeInTheDocument();
    expect(screen.getByText("Tier 3", { selector: "option" })).toBeInTheDocument();

    // Status filter options
    expect(screen.getByText("All Statuses")).toBeInTheDocument();
    expect(screen.getByText("Active", { selector: "option" })).toBeInTheDocument();
    expect(screen.getByText("Suspended", { selector: "option" })).toBeInTheDocument();
    expect(screen.getByText("Banned", { selector: "option" })).toBeInTheDocument();
  });

  it("sends tier filter param when tier is selected", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    mockFetch.mockClear();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUsersResponseNoMore,
    });

    const tierSelect = screen.getByDisplayValue("All Tiers");
    await act(async () => {
      fireEvent.change(tierSelect, { target: { value: "2" } });
    });

    await waitFor(() => {
      const lastCall = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
      expect(lastCall[0]).toContain("tier=2");
    });
  });

  it("sends status filter param when status is selected", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    mockFetch.mockClear();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUsersResponseNoMore,
    });

    const statusSelect = screen.getByDisplayValue("All Statuses");
    await act(async () => {
      fireEvent.change(statusSelect, { target: { value: "banned" } });
    });

    await waitFor(() => {
      const lastCall = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
      expect(lastCall[0]).toContain("status=banned");
    });
  });

  // Pagination — Load More button
  it("shows Load More button when next_cursor is present", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /load more/i })).toBeInTheDocument();
  });

  it("hides Load More button when next_cursor is null", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUsersResponseNoMore,
    });

    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("charlie@example.com")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument();
  });

  it("renders action buttons (Tokens, Status) for each user", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    const tokenButtons = screen.getAllByRole("button", { name: /tokens/i });
    const statusButtons = screen.getAllByRole("button", { name: /status/i });

    expect(tokenButtons.length).toBe(2);
    expect(statusButtons.length).toBe(2);
  });

  it("shows error message on API failure", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
    });

    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText(/session expired/i)).toBeInTheDocument();
    });
  });
});
