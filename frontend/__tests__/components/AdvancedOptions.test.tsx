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
      role: "Recruiter",
      goals: ["Hire talent"],
      model_id: "gemini-3-flash-preview",
      type: "negotiator",
    },
    {
      name: "Candidate",
      role: "Candidate",
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
    expect(screen.getByRole("heading", { name: "Agents" })).toBeInTheDocument();
  });
}

/** Open the Advanced Config modal for a given agent */
async function openAdvancedConfig(agentName: string) {
  const buttons = screen.getAllByRole("button", { name: /Advanced Config/i });
  let targetBtn: HTMLElement | null = null;
  for (const btn of buttons) {
    const card = btn.closest("div[style]");
    if (card && card.querySelector("h3")?.textContent === agentName) {
      targetBtn = btn;
      break;
    }
  }
  expect(targetBtn).not.toBeNull();
  fireEvent.click(targetBtn!);
  await waitFor(() => {
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
}

/** Select a memory strategy radio button in the open modal */
function selectMemoryStrategy(strategy: string) {
  const radio = document.getElementById(`memory-${strategy}`) as HTMLInputElement;
  fireEvent.click(radio);
}

// ---------------------------------------------------------------------------
// Tests — Per-Agent Memory Strategy in Advanced Config Modal
// ---------------------------------------------------------------------------

describe("Per-Agent Memory Strategy Radio Group", () => {
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

  it("shows memory strategy radio group inside Advanced Config modal", async () => {
    render(<ArenaPage />);
    await selectScenario();
    await openAdvancedConfig("Recruiter");

    const radio = document.getElementById("memory-full_transcript");
    expect(radio).toBeInTheDocument();
  });

  it("defaults the memory strategy to structured in the modal", async () => {
    render(<ArenaPage />);
    await selectScenario();
    await openAdvancedConfig("Recruiter");

    const radio = document.getElementById("memory-structured") as HTMLInputElement;
    expect(radio).toBeChecked();
  });

  it("passes structured_memory_roles for enabled agents only", async () => {
    vi.mocked(api.startNegotiation).mockResolvedValue({
      session_id: "sess-mem-1",
      tokens_remaining: 40,
      max_turns: 15,
    });

    render(<ArenaPage />);
    await selectScenario();

    // Open Recruiter's Advanced Config and select structured memory
    await openAdvancedConfig("Recruiter");
    selectMemoryStrategy("structured");
    fireEvent.click(screen.getByRole("button", { name: /Save/i }));

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
        ["Recruiter", "Candidate"],  // Both agents have structured memory (default)
        false,
        undefined,
      );
    });
  });

  it("shows memory strategy options inside Advanced Config modal", async () => {
    render(<ArenaPage />);
    await selectScenario();
    await openAdvancedConfig("Recruiter");

    expect(document.getElementById("memory-none")).toBeInTheDocument();
    expect(document.getElementById("memory-full_transcript")).toBeInTheDocument();
    expect(document.getElementById("memory-structured")).toBeInTheDocument();
    expect(document.getElementById("memory-structured_milestones")).toBeInTheDocument();
  });

  it("resets memory strategy on scenario change", async () => {
    render(<ArenaPage />);
    await selectScenario();

    // Change Recruiter to "no memory" (non-default)
    await openAdvancedConfig("Recruiter");
    selectMemoryStrategy("none");
    fireEvent.click(screen.getByRole("button", { name: /Save/i }));

    // Verify "No Memory" warning indicator shows on the Recruiter card
    expect(screen.getByText("⚠ No Memory")).toBeInTheDocument();

    // Switch scenario
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

    // "No Memory" indicator should be gone — reset to default (structured)
    expect(screen.queryByText("⚠ No Memory")).not.toBeInTheDocument();
    // Default structured memory indicator should be present
    expect(screen.getByText("✦ Structured Memory")).toBeInTheDocument();
  });
});
