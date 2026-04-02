import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import OutcomeReceipt from "@/components/glassbox/OutcomeReceipt";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

beforeEach(() => {
  mockPush.mockClear();
});

const defaultProps = {
  dealStatus: "Agreed" as const,
  finalSummary: {
    outcome: "Deal closed successfully",
    current_offer: 500000,
    turns_completed: 6,
    total_warnings: 1,
  },
  elapsedTimeMs: 12500,
  scenarioOutcomeReceipt: {
    equivalent_human_time: "2-4 weeks",
    process_label: "Enterprise SaaS negotiation",
  },
  scenarioId: "talent_war",
};

describe("OutcomeReceipt", () => {
  it("renders Agreed status with structured deal data and success styling", () => {
    render(<OutcomeReceipt {...defaultProps} />);

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Agreed");

    const content = screen.getByTestId("outcome-content");
    expect(content).toHaveTextContent("Deal closed successfully");
    expect(content).toHaveTextContent("Final Price:");
    expect(content).toHaveTextContent("$500,000");
    expect(content).toHaveTextContent("Turns: 6");
    expect(content).toHaveTextContent("Warnings: 1");

    // Success styling — green border
    const card = screen.getByTestId("outcome-heading").closest("div.rounded-lg");
    expect(card?.className).toContain("border-green-500");
    expect(card?.className).toContain("bg-green-50");
  });

  it("renders Agreed status without optional fields when absent", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        finalSummary={{}}
      />,
    );

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Agreed");
    const content = screen.getByTestId("outcome-content");
    expect(content).not.toHaveTextContent("Final Price:");
    expect(content).not.toHaveTextContent("Turns:");
    expect(content).not.toHaveTextContent("Warnings:");
  });

  it("renders Blocked status with blocked_by, reason, and warning styling", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        dealStatus="Blocked"
        finalSummary={{
          blocked_by: "EU Regulator",
          reason: "Regulator blocked the deal",
          current_offer: 300000,
          total_warnings: 3,
        }}
      />,
    );

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Blocked");

    const content = screen.getByTestId("outcome-content");
    expect(content).toHaveTextContent("Blocked by: EU Regulator");
    expect(content).toHaveTextContent("Regulator blocked the deal");
    expect(content).toHaveTextContent("Last Offer: $300,000");
    expect(content).toHaveTextContent("Total Warnings: 3");

    const card = screen.getByTestId("outcome-heading").closest("div.rounded-lg");
    expect(card?.className).toContain("border-yellow-500");
    expect(card?.className).toContain("bg-yellow-50");
  });

  it("renders Blocked status without optional blocked_by field", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        dealStatus="Blocked"
        finalSummary={{ reason: "Compliance violation" }}
      />,
    );

    const content = screen.getByTestId("outcome-content");
    expect(content).not.toHaveTextContent("Blocked by:");
    expect(content).toHaveTextContent("Compliance violation");
  });

  it("renders Failed status with default max turns message", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        dealStatus="Failed"
        finalSummary={{}}
      />,
    );

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Negotiation Failed");
    expect(
      screen.getByText("Negotiation reached maximum turns without agreement"),
    ).toBeInTheDocument();

    const card = screen.getByTestId("outcome-heading").closest("div.rounded-lg");
    expect(card?.className).toContain("border-gray-400");
    expect(card?.className).toContain("bg-gray-50");
  });

  it("renders Failed status with custom reason when provided", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        dealStatus="Failed"
        finalSummary={{ reason: "Parties walked away", current_offer: 100000, total_warnings: 2 }}
      />,
    );

    const content = screen.getByTestId("outcome-content");
    expect(content).toHaveTextContent("Parties walked away");
    expect(content).not.toHaveTextContent("Negotiation reached maximum turns");
    expect(content).toHaveTextContent("Last Offer: $100,000");
    expect(content).toHaveTextContent("Warnings: 2");
  });

  it("displays both measured and estimated ROI metric groups", () => {
    render(<OutcomeReceipt {...defaultProps} />);

    // Measured
    const measured = screen.getByTestId("measured-metrics");
    expect(measured).toHaveTextContent("Time Elapsed: 13s");

    // Estimated
    const estimated = screen.getByTestId("estimated-metrics");
    expect(estimated).toHaveTextContent("Industry Estimate");
    expect(estimated).toHaveTextContent("Equivalent Human Time: 2-4 weeks");
    expect(estimated).toHaveTextContent("Enterprise SaaS negotiation");
  });

  it("displays ai_tokens_used when present in finalSummary", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        finalSummary={{ ...defaultProps.finalSummary, ai_tokens_used: 12345 }}
      />,
    );

    const measured = screen.getByTestId("measured-metrics");
    expect(measured).toHaveTextContent("AI Tokens Used: 12,345");
  });

  it("hides estimated metrics when scenarioOutcomeReceipt is null", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        scenarioOutcomeReceipt={null}
      />,
    );

    expect(screen.queryByTestId("estimated-metrics")).not.toBeInTheDocument();
  });

  it('"Run Another Scenario" navigates to /arena', () => {
    render(<OutcomeReceipt {...defaultProps} />);

    fireEvent.click(screen.getByTestId("run-another-btn"));
    expect(mockPush).toHaveBeenCalledWith("/arena");
  });

  it('"Reset with Different Variables" navigates to /arena?scenario={id}', () => {
    render(<OutcomeReceipt {...defaultProps} />);

    fireEvent.click(screen.getByTestId("reset-variables-btn"));
    expect(mockPush).toHaveBeenCalledWith("/arena?scenario=talent_war");
  });

  it('"Reset with Different Variables" navigates to /arena when scenarioId is null', () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        scenarioId={null}
      />,
    );

    fireEvent.click(screen.getByTestId("reset-variables-btn"));
    expect(mockPush).toHaveBeenCalledWith("/arena");
  });
});
