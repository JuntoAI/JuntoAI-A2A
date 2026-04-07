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

  it("shows generic error for non-401 API failure", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
    });

    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText(/API error: 500/i)).toBeInTheDocument();
    });
  });

  it("shows 'No users found' when API returns empty list", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ users: [], next_cursor: null, total_count: 0 }),
    });

    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("No users found")).toBeInTheDocument();
    });
  });

  it("loads more users when Load More is clicked", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUsersResponseNoMore,
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /load more/i }));
    });

    await waitFor(() => {
      expect(screen.getByText("charlie@example.com")).toBeInTheDocument();
    });
    // Original users still present
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
  });

  it("adjustTokens updates balance on success", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce("99");
    mockFetch.mockResolvedValueOnce({ ok: true, status: 200 });

    const tokenButtons = screen.getAllByRole("button", { name: /tokens/i });
    await act(async () => {
      fireEvent.click(tokenButtons[0]);
    });

    await waitFor(() => {
      expect(screen.getByText("99")).toBeInTheDocument();
    });
  });

  it("adjustTokens does nothing when prompt is cancelled", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce(null);

    const tokenButtons = screen.getAllByRole("button", { name: /tokens/i });
    await act(async () => {
      fireEvent.click(tokenButtons[0]);
    });

    // Balance unchanged
    expect(screen.getByText("45")).toBeInTheDocument();
  });

  it("adjustTokens alerts on invalid input", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce("abc");
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const tokenButtons = screen.getAllByRole("button", { name: /tokens/i });
    await act(async () => {
      fireEvent.click(tokenButtons[0]);
    });

    expect(alertSpy).toHaveBeenCalledWith("Token balance must be a non-negative integer.");
    alertSpy.mockRestore();
  });

  it("adjustTokens alerts on API failure", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce("50");
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Server error" }),
    });
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const tokenButtons = screen.getAllByRole("button", { name: /tokens/i });
    await act(async () => {
      fireEvent.click(tokenButtons[0]);
    });

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Server error");
    });
    alertSpy.mockRestore();
  });

  it("adjustTokens alerts on network error", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce("50");
    mockFetch.mockRejectedValueOnce(new Error("Network fail"));
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const tokenButtons = screen.getAllByRole("button", { name: /tokens/i });
    await act(async () => {
      fireEvent.click(tokenButtons[0]);
    });

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Network error while updating tokens.");
    });
    alertSpy.mockRestore();
  });

  it("changeStatus updates status on success", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce("suspended");
    mockFetch.mockResolvedValueOnce({ ok: true, status: 200 });

    const statusButtons = screen.getAllByRole("button", { name: /^status$/i });
    await act(async () => {
      fireEvent.click(statusButtons[0]);
    });

    await waitFor(() => {
      const badges = screen.getAllByText("suspended", { selector: "span" });
      expect(badges.length).toBe(2); // both alice and bob now suspended
    });
  });

  it("changeStatus does nothing when prompt is cancelled", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce(null);

    const statusButtons = screen.getAllByRole("button", { name: /^status$/i });
    await act(async () => {
      fireEvent.click(statusButtons[0]);
    });

    // Status unchanged
    expect(screen.getByText("active", { selector: "span" })).toBeInTheDocument();
  });

  it("changeStatus alerts on invalid status", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce("invalid");
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const statusButtons = screen.getAllByRole("button", { name: /^status$/i });
    await act(async () => {
      fireEvent.click(statusButtons[0]);
    });

    expect(alertSpy).toHaveBeenCalledWith("Status must be one of: active, suspended, banned.");
    alertSpy.mockRestore();
  });

  it("changeStatus alerts on API failure", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce("banned");
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Forbidden" }),
    });
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const statusButtons = screen.getAllByRole("button", { name: /^status$/i });
    await act(async () => {
      fireEvent.click(statusButtons[0]);
    });

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Forbidden");
    });
    alertSpy.mockRestore();
  });

  it("changeStatus alerts on network error", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce("banned");
    mockFetch.mockRejectedValueOnce(new Error("Network fail"));
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const statusButtons = screen.getAllByRole("button", { name: /^status$/i });
    await act(async () => {
      fireEvent.click(statusButtons[0]);
    });

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Network error while updating status.");
    });
    alertSpy.mockRestore();
  });

  it("deleteUser removes user on confirm", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "confirm").mockReturnValueOnce(true);
    mockFetch.mockResolvedValueOnce({ ok: true, status: 200 });

    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    await act(async () => {
      fireEvent.click(deleteButtons[0]);
    });

    await waitFor(() => {
      expect(screen.queryByText("alice@example.com")).not.toBeInTheDocument();
    });
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();
  });

  it("deleteUser does nothing when confirm is cancelled", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "confirm").mockReturnValueOnce(false);

    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    await act(async () => {
      fireEvent.click(deleteButtons[0]);
    });

    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
  });

  it("deleteUser alerts on API failure", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "confirm").mockReturnValueOnce(true);
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Cannot delete" }),
    });
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    await act(async () => {
      fireEvent.click(deleteButtons[0]);
    });

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Cannot delete");
    });
    alertSpy.mockRestore();
  });

  it("deleteUser alerts on network error", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "confirm").mockReturnValueOnce(true);
    mockFetch.mockRejectedValueOnce(new Error("Network fail"));
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    await act(async () => {
      fireEvent.click(deleteButtons[0]);
    });

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Network error while deleting user.");
    });
    alertSpy.mockRestore();
  });

  it("shows last_login as 'Never' when null", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        users: [
          {
            email: "noLogin@example.com",
            signed_up_at: null,
            last_login: null,
            token_balance: 10,
            last_reset_date: null,
            tier: 1,
            user_status: "active",
          },
        ],
        next_cursor: null,
        total_count: 1,
      }),
    });

    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("noLogin@example.com")).toBeInTheDocument();
    });

    expect(screen.getByText("Never")).toBeInTheDocument();
    // signed_up_at null shows "—"
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("adjustTokens alerts fallback when API returns non-JSON error", async () => {
    await act(async () => {
      render(<AdminUsersPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    vi.spyOn(window, "prompt").mockReturnValueOnce("50");
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("not json")),
    });
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const tokenButtons = screen.getAllByRole("button", { name: /tokens/i });
    await act(async () => {
      fireEvent.click(tokenButtons[0]);
    });

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Failed to update tokens: 500");
    });
    alertSpy.mockRestore();
  });
});
