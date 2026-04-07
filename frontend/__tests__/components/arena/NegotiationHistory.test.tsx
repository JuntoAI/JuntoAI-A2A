import { createElement } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NegotiationHistory } from "@/components/arena/NegotiationHistory";
import type { SessionHistoryResponse } from "@/lib/history";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    [k: string]: unknown;
  }) => createElement("a", { href, ...rest }, children),
}));

const mockFetch = vi.fn();
vi.mock("@/lib/history", () => ({
  fetchNegotiationHistory: (...args: unknown[]) => mockFetch(...args),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function todayUTC(): string {
  return new Date().toISOString().slice(0, 10);
}

function yesterdayUTC(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

function buildResponse(
  days: SessionHistoryResponse["days"] = [],
): SessionHistoryResponse {
  const total = days.reduce((s, g) => s + g.total_token_cost, 0);
  return { days, total_token_cost: total, period_days: 7 };
}

const defaultProps = { email: "test@example.com", dailyLimit: 100 };

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NegotiationHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Req 4.7: loading skeleton
  it("renders loading skeleton while fetching", () => {
    mockFetch.mockReturnValue(new Promise(() => {})); // never resolves
    render(<NegotiationHistory {...defaultProps} />);
    const container = screen.getByTestId("negotiation-history");
    expect(container).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeTruthy();
  });

  // Req 4.8: error state with retry
  it("renders error state with Retry button on failure", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    render(<NegotiationHistory {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("retries fetch when Retry button is clicked", async () => {
    mockFetch
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce(buildResponse());
    render(<NegotiationHistory {...defaultProps} />);
    await waitFor(() => screen.getByText("fail"));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(screen.getByText("No negotiations yet. Start one above.")).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  // Req 4.6: empty state
  it("renders empty state when no sessions", async () => {
    mockFetch.mockResolvedValueOnce(buildResponse());
    render(<NegotiationHistory {...defaultProps} />);
    await waitFor(() => {
      expect(
        screen.getByText("No negotiations yet. Start one above."),
      ).toBeInTheDocument();
    });
  });

  // Req 4.3, 5.2, 5.3: day groups with date labels
  it("renders Today and Yesterday labels correctly", async () => {
    const response = buildResponse([
      {
        date: todayUTC(),
        total_token_cost: 5,
        sessions: [
          {
            session_id: "s1",
            scenario_id: "sc1",
            scenario_name: "Talent War",
            deal_status: "Agreed",
            total_tokens_used: 4500,
            token_cost: 5,
            created_at: `${todayUTC()}T10:00:00Z`,
            completed_at: `${todayUTC()}T10:05:00Z`,
          },
        ],
      },
      {
        date: yesterdayUTC(),
        total_token_cost: 3,
        sessions: [
          {
            session_id: "s2",
            scenario_id: "sc2",
            scenario_name: "M&A Buyout",
            deal_status: "Failed",
            total_tokens_used: 2500,
            token_cost: 3,
            created_at: `${yesterdayUTC()}T08:00:00Z`,
            completed_at: `${yesterdayUTC()}T08:10:00Z`,
          },
        ],
      },
    ]);
    mockFetch.mockResolvedValueOnce(response);
    render(<NegotiationHistory {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText("Today")).toBeInTheDocument();
    });
    expect(screen.getByText("Yesterday")).toBeInTheDocument();
  });

  // Req 5.4: today expanded, others collapsed
  it("expands today group by default and collapses others", async () => {
    const response = buildResponse([
      {
        date: todayUTC(),
        total_token_cost: 5,
        sessions: [
          {
            session_id: "s1",
            scenario_id: "sc1",
            scenario_name: "Talent War",
            deal_status: "Agreed",
            total_tokens_used: 4500,
            token_cost: 5,
            created_at: `${todayUTC()}T10:00:00Z`,
            completed_at: null,
          },
        ],
      },
      {
        date: yesterdayUTC(),
        total_token_cost: 3,
        sessions: [
          {
            session_id: "s2",
            scenario_id: "sc2",
            scenario_name: "M&A Buyout",
            deal_status: "Failed",
            total_tokens_used: 2500,
            token_cost: 3,
            created_at: `${yesterdayUTC()}T08:00:00Z`,
            completed_at: null,
          },
        ],
      },
    ]);
    mockFetch.mockResolvedValueOnce(response);
    render(<NegotiationHistory {...defaultProps} />);
    await waitFor(() => screen.getByText("Talent War"));
    // Today's session visible (expanded)
    expect(screen.getByText("Talent War")).toBeInTheDocument();
    // Yesterday's session NOT visible (collapsed)
    expect(screen.queryByText("M&A Buyout")).not.toBeInTheDocument();
  });

  // Req 4.4: status badge colors
  it("renders colored status badges", async () => {
    const response = buildResponse([
      {
        date: todayUTC(),
        total_token_cost: 9,
        sessions: [
          {
            session_id: "s1",
            scenario_id: "sc1",
            scenario_name: "Deal A",
            deal_status: "Agreed",
            total_tokens_used: 3000,
            token_cost: 3,
            created_at: `${todayUTC()}T12:00:00Z`,
            completed_at: null,
          },
          {
            session_id: "s2",
            scenario_id: "sc2",
            scenario_name: "Deal B",
            deal_status: "Failed",
            total_tokens_used: 3000,
            token_cost: 3,
            created_at: `${todayUTC()}T11:00:00Z`,
            completed_at: null,
          },
          {
            session_id: "s3",
            scenario_id: "sc3",
            scenario_name: "Deal C",
            deal_status: "Blocked",
            total_tokens_used: 3000,
            token_cost: 3,
            created_at: `${todayUTC()}T10:00:00Z`,
            completed_at: null,
          },
        ],
      },
    ]);
    mockFetch.mockResolvedValueOnce(response);
    render(<NegotiationHistory {...defaultProps} />);
    await waitFor(() => screen.getByText("Deal A"));

    const agreed = screen.getByText("Agreed");
    expect(agreed.className).toContain("bg-green-100");

    const failed = screen.getByText("Failed");
    expect(failed.className).toContain("bg-red-100");

    const blocked = screen.getByText("Blocked");
    expect(blocked.className).toContain("bg-yellow-100");
  });

  // Req 5.1: daily token cost as fraction of limit
  it("shows daily token cost as fraction of dailyLimit", async () => {
    const response = buildResponse([
      {
        date: todayUTC(),
        total_token_cost: 12,
        sessions: [
          {
            session_id: "s1",
            scenario_id: "sc1",
            scenario_name: "Test",
            deal_status: "Agreed",
            total_tokens_used: 12000,
            token_cost: 12,
            created_at: `${todayUTC()}T10:00:00Z`,
            completed_at: null,
          },
        ],
      },
    ]);
    mockFetch.mockResolvedValueOnce(response);
    render(<NegotiationHistory {...defaultProps} dailyLimit={100} />);
    await waitFor(() => {
      expect(screen.getByText("12 / 100 tokens used")).toBeInTheDocument();
    });
  });

  // Req 8.2: local mode shows ∞
  it("shows ∞ for dailyLimit when Infinity (local mode)", async () => {
    const response = buildResponse([
      {
        date: todayUTC(),
        total_token_cost: 5,
        sessions: [
          {
            session_id: "s1",
            scenario_id: "sc1",
            scenario_name: "Test",
            deal_status: "Agreed",
            total_tokens_used: 5000,
            token_cost: 5,
            created_at: `${todayUTC()}T10:00:00Z`,
            completed_at: null,
          },
        ],
      },
    ]);
    mockFetch.mockResolvedValueOnce(response);
    render(<NegotiationHistory {...defaultProps} dailyLimit={Infinity} />);
    await waitFor(() => {
      expect(screen.getByText("5 / ∞ tokens used")).toBeInTheDocument();
    });
  });

  // Req 4.5: View link navigates to session
  it("renders View links pointing to /arena/session/{id}", async () => {
    const response = buildResponse([
      {
        date: todayUTC(),
        total_token_cost: 2,
        sessions: [
          {
            session_id: "abc-123",
            scenario_id: "sc1",
            scenario_name: "Test",
            deal_status: "Agreed",
            total_tokens_used: 2000,
            token_cost: 2,
            created_at: `${todayUTC()}T10:00:00Z`,
            completed_at: null,
          },
        ],
      },
    ]);
    mockFetch.mockResolvedValueOnce(response);
    render(<NegotiationHistory {...defaultProps} />);
    await waitFor(() => screen.getByText("Test"));
    const link = screen.getByRole("link", { name: "View" });
    expect(link).toHaveAttribute("href", "/arena/session/abc-123");
  });

  // Collapsible toggle
  it("toggles day group expansion on click", async () => {
    const response = buildResponse([
      {
        date: todayUTC(),
        total_token_cost: 2,
        sessions: [
          {
            session_id: "s1",
            scenario_id: "sc1",
            scenario_name: "Toggle Test",
            deal_status: "Agreed",
            total_tokens_used: 2000,
            token_cost: 2,
            created_at: `${todayUTC()}T10:00:00Z`,
            completed_at: null,
          },
        ],
      },
    ]);
    mockFetch.mockResolvedValueOnce(response);
    render(<NegotiationHistory {...defaultProps} />);
    await waitFor(() => screen.getByText("Toggle Test"));

    // Collapse
    const toggleBtn = screen.getByRole("button", { name: /Today/i });
    fireEvent.click(toggleBtn);
    expect(screen.queryByText("Toggle Test")).not.toBeInTheDocument();

    // Expand again
    fireEvent.click(toggleBtn);
    expect(screen.getByText("Toggle Test")).toBeInTheDocument();
  });

  // data-testid present
  it("has data-testid='negotiation-history' on outermost div", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<NegotiationHistory {...defaultProps} />);
    expect(screen.getByTestId("negotiation-history")).toBeInTheDocument();
  });
});
