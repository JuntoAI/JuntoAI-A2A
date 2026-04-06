import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { HealthCheckReport } from "@/components/builder/HealthCheckReport";
import type {
  HealthCheckFinding,
  HealthCheckFullReport,
} from "@/lib/builder/types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const sampleFindings: HealthCheckFinding[] = [
  {
    check_name: "prompt_quality",
    severity: "critical",
    agent_role: "buyer",
    message: "Persona prompt lacks negotiation strategy",
  },
  {
    check_name: "budget_overlap",
    severity: "warning",
    agent_role: null,
    message: "Excessive overlap between budget ranges",
  },
  {
    check_name: "turn_sanity",
    severity: "info",
    agent_role: null,
    message: "Turn order looks good",
  },
];

const sampleReport: HealthCheckFullReport = {
  readiness_score: 75,
  tier: "Needs Work",
  prompt_quality_scores: [
    { role: "buyer", name: "Agent A", prompt_quality_score: 65, findings: ["Lacks strategy"] },
    { role: "seller", name: "Agent B", prompt_quality_score: 85, findings: [] },
  ],
  tension_score: 80,
  budget_overlap_score: 70,
  toggle_effectiveness_score: 60,
  turn_sanity_score: 90,
  stall_risk: { stall_risk_score: 30, risks: [] },
  findings: sampleFindings,
  recommendations: ["Add negotiation strategy to buyer prompt", "Reduce budget overlap"],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HealthCheckReport", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns null when no report, no findings, and not analyzing", () => {
    const { container } = render(
      <HealthCheckReport findings={[]} report={null} isAnalyzing={false} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows loading state while analyzing", () => {
    render(
      <HealthCheckReport findings={[]} report={null} isAnalyzing={true} />,
    );
    expect(screen.getByTestId("health-check-loading")).toBeInTheDocument();
    expect(screen.getByText("Analyzing scenario readiness...")).toBeInTheDocument();
  });

  it("shows progressive findings while loading", () => {
    render(
      <HealthCheckReport
        findings={sampleFindings.slice(0, 1)}
        report={null}
        isAnalyzing={true}
      />,
    );
    expect(screen.getByText("Persona prompt lacks negotiation strategy")).toBeInTheDocument();
  });

  it("renders full report with readiness score", () => {
    render(
      <HealthCheckReport
        findings={sampleFindings}
        report={sampleReport}
        isAnalyzing={false}
      />,
    );
    expect(screen.getByTestId("health-check-report")).toBeInTheDocument();
    expect(screen.getByText("75")).toBeInTheDocument();
  });

  it("displays correct tier badge", () => {
    render(
      <HealthCheckReport
        findings={sampleFindings}
        report={sampleReport}
        isAnalyzing={false}
      />,
    );
    expect(screen.getByTestId("tier-badge")).toHaveTextContent("Needs Work");
  });

  it("displays tier badge for Ready tier", () => {
    const readyReport = { ...sampleReport, readiness_score: 85, tier: "Ready" as const };
    render(
      <HealthCheckReport
        findings={sampleFindings}
        report={readyReport}
        isAnalyzing={false}
      />,
    );
    expect(screen.getByTestId("tier-badge")).toHaveTextContent("Ready");
  });

  it("displays tier badge for Not Ready tier", () => {
    const notReadyReport = { ...sampleReport, readiness_score: 40, tier: "Not Ready" as const };
    render(
      <HealthCheckReport
        findings={sampleFindings}
        report={notReadyReport}
        isAnalyzing={false}
      />,
    );
    expect(screen.getByTestId("tier-badge")).toHaveTextContent("Not Ready");
  });

  it("renders per-agent prompt quality scores", () => {
    render(
      <HealthCheckReport
        findings={sampleFindings}
        report={sampleReport}
        isAnalyzing={false}
      />,
    );
    const agentScores = screen.getAllByTestId("agent-score");
    expect(agentScores).toHaveLength(2);
    expect(screen.getByText("Agent A")).toBeInTheDocument();
    expect(screen.getByText("65/100")).toBeInTheDocument();
    expect(screen.getByText("85/100")).toBeInTheDocument();
  });

  it("renders findings with severity icons", () => {
    render(
      <HealthCheckReport
        findings={sampleFindings}
        report={sampleReport}
        isAnalyzing={false}
      />,
    );
    expect(screen.getAllByTestId("finding-critical")).toHaveLength(1);
    expect(screen.getAllByTestId("finding-warning")).toHaveLength(1);
    expect(screen.getAllByTestId("finding-info")).toHaveLength(1);
  });

  it("renders ordered recommendations", () => {
    render(
      <HealthCheckReport
        findings={sampleFindings}
        report={sampleReport}
        isAnalyzing={false}
      />,
    );
    const recs = screen.getAllByTestId("recommendation");
    expect(recs).toHaveLength(2);
    expect(recs[0]).toHaveTextContent("Add negotiation strategy to buyer prompt");
    expect(recs[1]).toHaveTextContent("Reduce budget overlap");
  });

  it("shows timeout after 60 seconds", () => {
    render(
      <HealthCheckReport
        findings={[]}
        report={null}
        isAnalyzing={true}
        onRetry={vi.fn()}
      />,
    );

    // Advance past timeout — wrap in act to flush React state updates
    act(() => {
      vi.advanceTimersByTime(61_000);
    });

    expect(screen.getByTestId("health-check-timeout")).toBeInTheDocument();
    expect(screen.getByText("Health check timed out")).toBeInTheDocument();
    expect(screen.getByTestId("retry-button")).toBeInTheDocument();
  });

  it("does not show timeout before 60 seconds", () => {
    render(
      <HealthCheckReport
        findings={[]}
        report={null}
        isAnalyzing={true}
      />,
    );

    act(() => {
      vi.advanceTimersByTime(59_000);
    });

    expect(screen.queryByTestId("health-check-timeout")).not.toBeInTheDocument();
  });
});
