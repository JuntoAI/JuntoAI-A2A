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
  toggles: [{ id: "competing_offer", label: "Competing Offer" }],
  negotiation_params: { max_turns: 15 },
  outcome_receipt: {
    equivalent_human_time: "2 weeks",
    process_label: "Salary Negotiation",
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Select a scenario and wait for detail to render */
async function selectScenario(scenarioId = "talent_war") {
  await waitFor(() => {
    expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
  });
  await act(async () => {
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: scenarioId },
    });
  });
  await waitFor(() => {
    expect(screen.getByText("Recruiter")).toBeInTheDocument();
  });
}

// ---------------------------------------------------------------------------
// Tests — Advanced Options Section (Req 3.2, 3.4, 3.5, 4.1)
// ---------------------------------------------------------------------------

describe("Advanced Options Section", () => {
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
    mockSearchParams.delete("scenario");
    vi.mocked(api.fetchScenarios).mockResolvedValue(mockScenarios);
    vi.mocked(api.fetchScenarioDetail).mockResolvedValue(mockDetail);
    vi.mocked(api.fetchAvailableModels).mockResolvedValue([]);
  });

  // Req 3.2: Section renders collapsed by default
  it("renders Advanced Options collapsed by default — toggle not visible", async () => {
    render(<ArenaPage />);
    await selectScenario();

    // The section header should be present
    expect(screen.getByText("Advanced Options")).toBeInTheDocument();

    // The toggle checkbox should NOT be visible when collapsed
    expect(screen.queryByLabelText(/Structured Agent Memory/i)).not.toBeInTheDocument();
  });

  // Req 3.2: Clicking expands the section and shows the toggle
  it("expands section on click and shows the structured memory toggle", async () => {
    render(<ArenaPage />);
    await selectScenario();

    // Click to expand
    fireEvent.click(screen.getByText("Advanced Options"));

    // Toggle should now be visible
    expect(screen.getByLabelText(/Structured Agent Memory/i)).toBeInTheDocument();
  });

  // Req 3.4: Toggle defaults to off
  it("defaults the structured memory toggle to off (unchecked)", async () => {
    render(<ArenaPage />);
    await selectScenario();

    fireEvent.click(screen.getByText("Advanced Options"));

    const toggle = screen.getByLabelText(/Structured Agent Memory/i);
    expect(toggle).not.toBeChecked();
  });

  // Req 4.1: startNegotiation called with structured_memory_enabled=true
  it("passes structured_memory_enabled=true when toggle is on", async () => {
    vi.mocked(api.startNegotiation).mockResolvedValue({
      session_id: "sess-mem-1",
      tokens_remaining: 40,
      max_turns: 15,
    });

    render(<ArenaPage />);
    await selectScenario();

    // Expand and enable the toggle
    fireEvent.click(screen.getByText("Advanced Options"));
    fireEvent.click(screen.getByLabelText(/Structured Agent Memory/i));

    // Start negotiation
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Start Negotiation/i }));
    });

    await waitFor(() => {
      expect(api.startNegotiation).toHaveBeenCalledWith(
        "test@example.com",
        "talent_war",
        [],
        undefined,
        undefined,
        true,
      );
    });
  });

  // Req 3.5: Toggle resets on scenario change
  it("resets structured memory toggle to off when switching scenarios", async () => {
    render(<ArenaPage />);
    await selectScenario();

    // Expand and enable the toggle
    fireEvent.click(screen.getByText("Advanced Options"));
    fireEvent.click(screen.getByLabelText(/Structured Agent Memory/i));
    expect(screen.getByLabelText(/Structured Agent Memory/i)).toBeChecked();

    // Switch to a different scenario
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

    // The section may still be expanded from before, or collapsed.
    // Ensure it's expanded so we can inspect the toggle.
    const advancedBtn = screen.getByRole("button", { name: /Advanced Options/ });
    if (advancedBtn.getAttribute("aria-expanded") !== "true") {
      fireEvent.click(advancedBtn);
    }

    // Toggle should be reset to off
    const toggle = screen.getByLabelText(/Structured Agent Memory/i);
    expect(toggle).not.toBeChecked();
  });
});
