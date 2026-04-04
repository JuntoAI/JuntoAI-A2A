import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks — must be declared before imports that use them
// ---------------------------------------------------------------------------

const mockPush = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => mockSearchParams,
}));

const mockUpdateTokenBalance = vi.fn();
let mockSessionState = {
  email: "test@example.com",
  tokenBalance: 50,
  lastResetDate: "2025-01-01",
  isAuthenticated: true,
  login: vi.fn(),
  logout: vi.fn(),
  updateTokenBalance: mockUpdateTokenBalance,
};

vi.mock("@/context/SessionContext", () => ({
  useSession: () => mockSessionState,
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  fetchScenarios: vi.fn(),
  fetchScenarioDetail: vi.fn(),
  fetchAvailableModels: vi.fn(),
  startNegotiation: vi.fn(),
  TokenLimitError: class TokenLimitError extends Error {
    constructor(message: string) {
      super(message);
      this.name = "TokenLimitError";
    }
  },
}));

// Import the component under test AFTER mocks
import ArenaPage from "@/app/(protected)/arena/page";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockScenarios: api.ScenarioSummary[] = [
  { id: "talent_war", name: "The Talent War", description: "HR negotiation", difficulty: "beginner" },
  { id: "ma_buyout", name: "M&A Buyout", description: "Corporate acquisition", difficulty: "intermediate" },
];

const mockDetail: api.ArenaScenario = {
  id: "talent_war",
  name: "The Talent War",
  description: "HR negotiation",
  agents: [
    {
      name: "Recruiter",
      role: "negotiator",
      goals: ["Hire talent"],
      model_id: "gemini-3-flash-preview",
      type: "negotiator",
    },
    {
      name: "Candidate",
      role: "negotiator",
      goals: ["Get best offer"],
      model_id: "claude-3.5-sonnet",
      type: "negotiator",
    },
  ],
  toggles: [
    { id: "competing_offer", label: "Competing Offer" },
    { id: "remote_pref", label: "Remote Preference" },
  ],
  negotiation_params: { max_turns: 15 },
  outcome_receipt: {
    equivalent_human_time: "2 weeks",
    process_label: "Salary Negotiation",
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  return render(<ArenaPage />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Arena Control Panel Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSessionState = {
      email: "test@example.com",
      tokenBalance: 50,
      lastResetDate: "2025-01-01",
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      updateTokenBalance: mockUpdateTokenBalance,
    };
    // Reset search params
    mockSearchParams.delete("scenario");
    vi.mocked(api.fetchScenarios).mockResolvedValue(mockScenarios);
    vi.mocked(api.fetchScenarioDetail).mockResolvedValue(mockDetail);
    vi.mocked(api.fetchAvailableModels).mockResolvedValue([]);
  });

  // Req 1.1: scenarios fetched and rendered on mount
  it("fetches scenarios on mount and renders them in the selector", async () => {
    renderPage();
    await waitFor(() => {
      expect(api.fetchScenarios).toHaveBeenCalledOnce();
    });
    await waitFor(() => {
      expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
      expect(screen.getByText(/M&A Buyout/)).toBeInTheDocument();
    });
  });

  // Req 1.3, 2.1, 3.1: scenario selection fetches detail and renders agent cards + toggles
  it("fetches detail on scenario select and renders agent cards and toggles", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.change(screen.getByRole("combobox"), {
        target: { value: "talent_war" },
      });
    });

    await waitFor(() => {
      expect(api.fetchScenarioDetail).toHaveBeenCalledWith("talent_war", "test@example.com");
    });

    await waitFor(() => {
      // Agent cards
      expect(screen.getByText("Recruiter")).toBeInTheDocument();
      expect(screen.getByText("Candidate")).toBeInTheDocument();
      // Toggles
      expect(screen.getByText("Competing Offer")).toBeInTheDocument();
      expect(screen.getByText("Remote Preference")).toBeInTheDocument();
    });
  });

  // Req 3.5: toggles reset on scenario switch
  it("resets toggles when a different scenario is selected", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
    });

    // Select first scenario
    await act(async () => {
      fireEvent.change(screen.getByRole("combobox"), {
        target: { value: "talent_war" },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Competing Offer")).toBeInTheDocument();
    });

    // Check a toggle
    const checkbox = screen.getByLabelText("Competing Offer");
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();

    // Switch scenario — detail mock returns same structure for simplicity
    const detail2: api.ArenaScenario = {
      ...mockDetail,
      id: "ma_buyout",
      toggles: [{ id: "due_diligence", label: "Due Diligence" }],
    };
    vi.mocked(api.fetchScenarioDetail).mockResolvedValue(detail2);

    await act(async () => {
      fireEvent.change(screen.getByRole("combobox"), {
        target: { value: "ma_buyout" },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Due Diligence")).toBeInTheDocument();
    });

    // New toggle should be unchecked
    const newCheckbox = screen.getByLabelText("Due Diligence");
    expect(newCheckbox).not.toBeChecked();
  });

  // Req 4.3: Initialize button calls startNegotiation with correct payload
  it("calls startNegotiation with email, scenarioId, and activeToggles", async () => {
    vi.mocked(api.startNegotiation).mockResolvedValue({
      session_id: "sess-123",
      tokens_remaining: 35,
      max_turns: 15,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
    });

    // Select scenario
    await act(async () => {
      fireEvent.change(screen.getByRole("combobox"), {
        target: { value: "talent_war" },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Competing Offer")).toBeInTheDocument();
    });

    // Check a toggle
    fireEvent.click(screen.getByLabelText("Competing Offer"));

    // Click Initialize
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /Start Negotiation/i }),
      );
    });

    await waitFor(() => {
      expect(api.startNegotiation).toHaveBeenCalledWith(
        "test@example.com",
        "talent_war",
        ["competing_offer"],
        undefined,
        undefined,
        ["negotiator", "negotiator"],
        false,
        undefined,
      );
    });

    // Verify navigation
    expect(mockPush).toHaveBeenCalledWith(
      "/arena/session/sess-123?max_turns=15&scenario=talent_war",
    );
    // Verify token balance update
    expect(mockUpdateTokenBalance).toHaveBeenCalledWith(35);
  });

  // Req 4.6: HTTP 429 shows token limit message and syncs balance to 0
  it("shows token limit message on HTTP 429 and syncs balance to 0", async () => {
    vi.mocked(api.startNegotiation).mockRejectedValue(
      new api.TokenLimitError("Token limit reached"),
    );

    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.change(screen.getByRole("combobox"), {
        target: { value: "talent_war" },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Recruiter")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /Start Negotiation/i }),
      );
    });

    await waitFor(() => {
      expect(
        screen.getByText("Token limit reached. Resets at midnight UTC."),
      ).toBeInTheDocument();
    });

    expect(mockUpdateTokenBalance).toHaveBeenCalledWith(0);
    expect(mockPush).not.toHaveBeenCalled();
  });

  // Req 4.7, 11.5: other API errors display error detail
  it("displays error detail from non-429 API errors", async () => {
    vi.mocked(api.startNegotiation).mockRejectedValue(
      new Error("Internal server error"),
    );

    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.change(screen.getByRole("combobox"), {
        target: { value: "talent_war" },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Recruiter")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /Start Negotiation/i }),
      );
    });

    await waitFor(() => {
      expect(
        screen.getByText("Internal server error"),
      ).toBeInTheDocument();
    });
  });

  // Req 10.6: pre-selection from URL query param
  it("pre-selects scenario from URL query param", async () => {
    mockSearchParams.set("scenario", "talent_war");

    renderPage();

    await waitFor(() => {
      expect(api.fetchScenarioDetail).toHaveBeenCalledWith("talent_war", "test@example.com");
    });

    await waitFor(() => {
      expect(screen.getByText("Recruiter")).toBeInTheDocument();
    });
  });

  // Req 4.2: Initialize button disabled when no scenario selected
  it("disables Initialize button when no scenario is selected", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
    });

    const button = screen.getByRole("button", {
      name: /Start Negotiation/i,
    });
    expect(button).toBeDisabled();
  });

  // Req 1.4: scenario fetch error
  it("shows error when scenario fetch fails", async () => {
    vi.mocked(api.fetchScenarios).mockRejectedValue(
      new Error("Network error"),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });
});
