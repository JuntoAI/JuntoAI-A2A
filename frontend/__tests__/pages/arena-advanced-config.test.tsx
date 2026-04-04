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
      role: "recruiter",
      goals: ["Hire talent"],
      model_id: "gemini-3-flash-preview",
      type: "negotiator",
    },
    {
      name: "Candidate",
      role: "candidate",
      goals: ["Get best offer"],
      model_id: "claude-3-5-sonnet",
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

const mockDetailMA: api.ArenaScenario = {
  id: "ma_buyout",
  name: "M&A Buyout",
  description: "Corporate acquisition",
  agents: [
    {
      name: "Buyer CEO",
      role: "buyer",
      goals: ["Acquire company"],
      model_id: "gemini-2.5-pro",
      type: "negotiator",
    },
  ],
  toggles: [],
  negotiation_params: { max_turns: 10 },
  outcome_receipt: {
    equivalent_human_time: "1 month",
    process_label: "M&A Negotiation",
  },
};

const mockModels: api.ModelInfo[] = [
  { model_id: "gemini-3-flash-preview", family: "gemini" },
  { model_id: "claude-3-5-sonnet", family: "claude" },
  { model_id: "gemini-2.5-pro", family: "gemini" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  return render(<ArenaPage />);
}

/** Select a scenario by changing the combobox value and wait for detail to load */
async function selectScenario(scenarioId: string, agentName: string) {
  await act(async () => {
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: scenarioId },
    });
  });
  await waitFor(() => {
    expect(screen.getByText(agentName)).toBeInTheDocument();
  });
}

// ---------------------------------------------------------------------------
// Tests — Arena page advanced config state management (Task 12.2)
// ---------------------------------------------------------------------------

describe("Arena Page — Advanced Config State Management", () => {
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
    vi.mocked(api.fetchAvailableModels).mockResolvedValue(mockModels);
  });

  // ---------------------------------------------------------------------------
  // Req 4.5: Scenario change clears all custom prompts and model overrides
  // ---------------------------------------------------------------------------
  describe("scenario change clears custom prompts and model overrides", () => {
    it("clears customPrompts and modelOverrides when switching scenarios", async () => {
      vi.mocked(api.startNegotiation).mockResolvedValue({
        session_id: "sess-1",
        tokens_remaining: 40,
        max_turns: 15,
      });

      renderPage();
      await waitFor(() => {
        expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
      });

      // Select first scenario
      await selectScenario("talent_war", "Recruiter");

      // Open advanced config for Recruiter and save a custom prompt + model override
      const advancedButtons = screen.getAllByRole("button", { name: /Advanced Config/i });
      await act(async () => {
        fireEvent.click(advancedButtons[0]);
      });

      // Fill in custom prompt
      const textarea = screen.getByPlaceholderText(/Be more aggressive/);
      fireEvent.change(textarea, { target: { value: "Be very firm" } });

      // Select a different model
      const modelSelect = screen.getByLabelText("Model");
      fireEvent.change(modelSelect, { target: { value: "claude-3-5-sonnet" } });

      // Save
      fireEvent.click(screen.getByRole("button", { name: /save/i }));

      // Verify indicator is visible (custom prompt dot)
      expect(screen.getByTestId("custom-prompt-indicator")).toBeInTheDocument();

      // Now switch to a different scenario
      vi.mocked(api.fetchScenarioDetail).mockResolvedValue(mockDetailMA);
      await selectScenario("ma_buyout", "Buyer CEO");

      // The new scenario's agent should NOT have any custom prompt indicator
      expect(screen.queryByTestId("custom-prompt-indicator")).not.toBeInTheDocument();

      // Verify that if we start negotiation, no custom prompts or overrides are sent
      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Start Negotiation/i }),
        );
      });

      await waitFor(() => {
        expect(api.startNegotiation).toHaveBeenCalledWith(
          "test@example.com",
          "ma_buyout",
          [],
          undefined,
          undefined,
          ["buyer"],
          false,
          undefined,
        );
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Req 10.5: API error fallback for model list fetch failure
  // ---------------------------------------------------------------------------
  describe("fetchAvailableModels failure fallback", () => {
    it("renders and works when fetchAvailableModels fails", async () => {
      vi.mocked(api.fetchAvailableModels).mockRejectedValue(
        new Error("Network error"),
      );
      vi.mocked(api.startNegotiation).mockResolvedValue({
        session_id: "sess-2",
        tokens_remaining: 45,
        max_turns: 15,
      });

      renderPage();
      await waitFor(() => {
        expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
      });

      // Select scenario — page should still render fine
      await selectScenario("talent_war", "Recruiter");

      // Agent cards should be visible
      expect(screen.getByText("Recruiter")).toBeInTheDocument();
      expect(screen.getByText("Candidate")).toBeInTheDocument();

      // Start negotiation should still work
      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Start Negotiation/i }),
        );
      });

      await waitFor(() => {
        expect(api.startNegotiation).toHaveBeenCalledWith(
          "test@example.com",
          "talent_war",
          [],
          undefined,
          undefined,
          ["recruiter", "candidate"],
          false,
          undefined,
        );
      });

      expect(mockPush).toHaveBeenCalledWith(
        "/arena/session/sess-2?max_turns=15&scenario=talent_war",
      );
    });
  });
  // ---------------------------------------------------------------------------
  // Req 4.5: Empty custom_prompts/model_overrides produce identical behavior
  // ---------------------------------------------------------------------------
  describe("empty custom_prompts and model_overrides", () => {
    it("calls startNegotiation with undefined for both when no config is set", async () => {
      vi.mocked(api.startNegotiation).mockResolvedValue({
        session_id: "sess-3",
        tokens_remaining: 42,
        max_turns: 15,
      });

      renderPage();
      await waitFor(() => {
        expect(screen.getByText(/The Talent War/)).toBeInTheDocument();
      });

      // Select scenario without configuring any advanced settings
      await selectScenario("talent_war", "Recruiter");

      // Click Initialize without any advanced config
      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Start Negotiation/i }),
        );
      });

      await waitFor(() => {
        expect(api.startNegotiation).toHaveBeenCalledWith(
          "test@example.com",
          "talent_war",
          [],
          undefined,
          undefined,
          ["recruiter", "candidate"],
          false,
          undefined,
        );
      });

      // No custom prompt indicators should be visible
      expect(screen.queryByTestId("custom-prompt-indicator")).not.toBeInTheDocument();
    });
  });
});
