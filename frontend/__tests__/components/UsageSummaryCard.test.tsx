import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import OutcomeReceipt from "@/components/glassbox/OutcomeReceipt";
import UsageSummaryCard from "@/components/glassbox/UsageSummaryCard";
import type { UsageSummary } from "@/types/sse";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const sampleSummary: UsageSummary = {
  per_persona: [
    {
      agent_role: "Buyer",
      agent_type: "negotiator",
      model_id: "gemini-2.5-flash",
      total_input_tokens: 100,
      total_output_tokens: 50,
      total_tokens: 150,
      call_count: 2,
      error_count: 0,
      avg_latency_ms: 200,
      tokens_per_message: 75,
    },
  ],
  per_model: [
    {
      model_id: "gemini-2.5-flash",
      total_input_tokens: 100,
      total_output_tokens: 50,
      total_tokens: 150,
      call_count: 2,
      error_count: 0,
      avg_latency_ms: 200,
      tokens_per_message: 75,
    },
  ],
  total_input_tokens: 100,
  total_output_tokens: 50,
  total_tokens: 150,
  total_calls: 2,
  total_errors: 0,
  avg_latency_ms: 200,
  negotiation_duration_ms: 12345,
};

const receiptProps = {
  dealStatus: "Agreed" as const,
  finalSummary: { outcome: "Deal closed" },
  elapsedTimeMs: 10000,
  scenarioOutcomeReceipt: null,
  scenarioId: null,
};

describe("UsageSummaryCard", () => {
  // --- Tests 1-2: via OutcomeReceipt (conditional rendering) ---

  it("section not rendered when usage_summary absent", () => {
    render(<OutcomeReceipt {...receiptProps} />);
    expect(screen.queryByTestId("usage-summary-section")).not.toBeInTheDocument();
  });

  it("section not rendered when total_calls is 0", () => {
    render(
      <OutcomeReceipt
        {...receiptProps}
        finalSummary={{ ...receiptProps.finalSummary, usage_summary: { ...sampleSummary, total_calls: 0 } }}
      />,
    );
    expect(screen.queryByTestId("usage-summary-section")).not.toBeInTheDocument();
  });

  // --- Tests 3-7: render UsageSummaryCard directly ---

  it("collapsed by default", () => {
    render(<UsageSummaryCard usageSummary={sampleSummary} />);
    expect(screen.getByTestId("usage-summary-toggle")).toBeInTheDocument();
    // Tables should NOT be visible when collapsed
    expect(screen.queryByText("Per Persona")).not.toBeInTheDocument();
    expect(screen.queryByText("Per Model")).not.toBeInTheDocument();
  });

  it("toggle expands section", () => {
    render(<UsageSummaryCard usageSummary={sampleSummary} />);
    fireEvent.click(screen.getByTestId("usage-summary-toggle"));
    expect(screen.getByText("Per Persona")).toBeInTheDocument();
    expect(screen.getByText("Per Model")).toBeInTheDocument();
  });

  it("errors count hidden when 0", () => {
    render(<UsageSummaryCard usageSummary={{ ...sampleSummary, total_errors: 0 }} />);
    fireEvent.click(screen.getByTestId("usage-summary-toggle"));
    expect(screen.queryByText("Errors:")).not.toBeInTheDocument();
  });

  it("errors count shown when > 0", () => {
    render(<UsageSummaryCard usageSummary={{ ...sampleSummary, total_errors: 5 }} />);
    fireEvent.click(screen.getByTestId("usage-summary-toggle"));
    expect(screen.getByText("Errors:")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("duration formatted as seconds with 1 decimal", () => {
    render(<UsageSummaryCard usageSummary={{ ...sampleSummary, negotiation_duration_ms: 12345 }} />);
    fireEvent.click(screen.getByTestId("usage-summary-toggle"));
    expect(screen.getByText("12.3s")).toBeInTheDocument();
  });
});
