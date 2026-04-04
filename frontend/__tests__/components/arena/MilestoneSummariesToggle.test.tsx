import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  MilestoneSummariesToggle,
  type MilestoneSummariesToggleProps,
} from "@/components/arena/MilestoneSummariesToggle";

// ---------------------------------------------------------------------------
// Mocks for ArenaPage integration tests
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

async function enableStructuredMemoryForAgent(agentName: string) {
  await openAdvancedConfig(agentName);
  // Use the specific ID to avoid matching the milestone toggle's dependency hint text
  const toggle = document.getElementById("structured-memory-toggle") as HTMLInputElement;
  fireEvent.click(toggle);
  fireEvent.click(screen.getByRole("button", { name: /Save/i }));
  await waitFor(() => {
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
}

// ---------------------------------------------------------------------------
// Unit tests for MilestoneSummariesToggle component
// ---------------------------------------------------------------------------

describe("MilestoneSummariesToggle (unit)", () => {
  const defaultProps: MilestoneSummariesToggleProps = {
    enabled: false,
    structuredMemoryEnabled: true,
    onChange: vi.fn(),
  };

  it("renders with correct description text", () => {
    render(<MilestoneSummariesToggle {...defaultProps} />);
    expect(screen.getByText("Milestone Summaries")).toBeInTheDocument();
    expect(
      screen.getByText(/Generate periodic strategic summaries to compress negotiation history/),
    ).toBeInTheDocument();
  });

  it("defaults to unchecked", () => {
    render(<MilestoneSummariesToggle {...defaultProps} />);
    const checkbox = screen.getByLabelText(/Milestone Summaries/i);
    expect(checkbox).not.toBeChecked();
  });

  it("is disabled when structured memory is off", () => {
    render(
      <MilestoneSummariesToggle
        {...defaultProps}
        structuredMemoryEnabled={false}
      />,
    );
    const checkbox = screen.getByLabelText(/Milestone Summaries/i);
    expect(checkbox).toBeDisabled();
  });

  it("shows dependency hint when structured memory is off", () => {
    render(
      <MilestoneSummariesToggle
        {...defaultProps}
        structuredMemoryEnabled={false}
      />,
    );
    expect(screen.getByTestId("dependency-hint")).toBeInTheDocument();
    expect(
      screen.getByText(/Requires Structured Agent Memory/),
    ).toBeInTheDocument();
  });

  it("is enabled and interactive when structured memory is on", () => {
    render(
      <MilestoneSummariesToggle
        {...defaultProps}
        structuredMemoryEnabled={true}
      />,
    );
    const checkbox = screen.getByLabelText(/Milestone Summaries/i);
    expect(checkbox).not.toBeDisabled();
  });

  it("does not show dependency hint when structured memory is on", () => {
    render(
      <MilestoneSummariesToggle
        {...defaultProps}
        structuredMemoryEnabled={true}
      />,
    );
    expect(screen.queryByTestId("dependency-hint")).not.toBeInTheDocument();
  });

  it("calls onChange when toggled", () => {
    const onChange = vi.fn();
    render(
      <MilestoneSummariesToggle
        {...defaultProps}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByLabelText(/Milestone Summaries/i));
    expect(onChange).toHaveBeenCalledWith(true);
  });
});

// ---------------------------------------------------------------------------
// Integration tests with ArenaPage
// ---------------------------------------------------------------------------

describe("MilestoneSummariesToggle (integration with ArenaPage)", () => {
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

  it("shows milestone summaries toggle inside Advanced Config modal", async () => {
    render(<ArenaPage />);
    await selectScenario();
    await openAdvancedConfig("Recruiter");
    const toggle = document.getElementById("milestone-summaries-toggle");
    expect(toggle).toBeInTheDocument();
  });

  it("milestone toggle is disabled when structured memory is off in modal", async () => {
    render(<ArenaPage />);
    await selectScenario();
    await openAdvancedConfig("Recruiter");
    const toggle = document.getElementById("milestone-summaries-toggle") as HTMLInputElement;
    expect(toggle).toBeDisabled();
    expect(screen.getByTestId("milestone-dependency-hint")).toBeInTheDocument();
  });

  it("milestone toggle becomes enabled after enabling structured memory in same modal", async () => {
    render(<ArenaPage />);
    await selectScenario();
    await openAdvancedConfig("Recruiter");

    // Enable structured memory first
    const memToggle = document.getElementById("structured-memory-toggle") as HTMLInputElement;
    fireEvent.click(memToggle);

    // Save to persist structured memory, then reopen
    fireEvent.click(screen.getByRole("button", { name: /Save/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    await openAdvancedConfig("Recruiter");
    const msToggle = document.getElementById("milestone-summaries-toggle") as HTMLInputElement;
    expect(msToggle).not.toBeDisabled();
  });

  it("enabling milestone summaries in modal is reflected when reopening", async () => {
    render(<ArenaPage />);
    await selectScenario();

    // Enable structured memory for Recruiter first
    await enableStructuredMemoryForAgent("Recruiter");

    // Reopen and enable milestone summaries
    await openAdvancedConfig("Recruiter");
    const msToggle = document.getElementById("milestone-summaries-toggle") as HTMLInputElement;
    fireEvent.click(msToggle);

    // Close and reopen — milestone should still be checked
    fireEvent.click(screen.getByRole("button", { name: /Save/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    await openAdvancedConfig("Recruiter");
    const msToggle2 = document.getElementById("milestone-summaries-toggle") as HTMLInputElement;
    expect(msToggle2).toBeChecked();
  });

  it("shows milestone summaries indicator on agent card when enabled", async () => {
    render(<ArenaPage />);
    await selectScenario();

    // Enable structured memory for Recruiter
    await enableStructuredMemoryForAgent("Recruiter");

    // Enable milestone summaries
    await openAdvancedConfig("Recruiter");
    const msToggle = document.getElementById("milestone-summaries-toggle") as HTMLInputElement;
    fireEvent.click(msToggle);
    fireEvent.click(screen.getByRole("button", { name: /Save/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // Recruiter card should show the indicator (has structured memory)
    expect(screen.getByText("✦ Milestone Summaries")).toBeInTheDocument();
  });

  it("scenario change resets milestone summaries", async () => {
    render(<ArenaPage />);
    await selectScenario();

    // Enable structured memory and milestone summaries
    await enableStructuredMemoryForAgent("Recruiter");
    await openAdvancedConfig("Recruiter");
    const msToggle = document.getElementById("milestone-summaries-toggle") as HTMLInputElement;
    fireEvent.click(msToggle);
    fireEvent.click(screen.getByRole("button", { name: /Save/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

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

    // Milestone indicator should be gone
    expect(screen.queryByText("✦ Milestone Summaries")).not.toBeInTheDocument();
  });
});
