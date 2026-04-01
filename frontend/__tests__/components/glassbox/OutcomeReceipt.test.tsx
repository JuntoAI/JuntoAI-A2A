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
  finalSummary: { price: "500000", terms: "Net 30" },
  elapsedTimeMs: 12500,
  scenarioOutcomeReceipt: {
    equivalent_human_time: "2-4 weeks",
    process_label: "Enterprise SaaS negotiation",
  },
  scenarioId: "talent_war",
};

describe("OutcomeReceipt", () => {
  it("renders Agreed status with final terms and success styling", () => {
    render(<OutcomeReceipt {...defaultProps} />);

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Agreed");
    expect(screen.getByText("Final Terms")).toBeInTheDocument();
    expect(screen.getByText("price:")).toBeInTheDocument();
    expect(screen.getByText("500000")).toBeInTheDocument();
    expect(screen.getByText("terms:")).toBeInTheDocument();
    expect(screen.getByText("Net 30")).toBeInTheDocument();

    // Success styling — green border
    const card = screen.getByTestId("outcome-heading").closest("div.rounded-lg");
    expect(card?.className).toContain("border-green-500");
    expect(card?.className).toContain("bg-green-50");
  });

  it("renders Blocked status with block reason and warning styling", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        dealStatus="Blocked"
        finalSummary={{ reason: "Regulator blocked the deal" }}
      />,
    );

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Blocked");
    expect(screen.getByText("Block Reason")).toBeInTheDocument();
    expect(screen.getByText("Regulator blocked the deal")).toBeInTheDocument();

    const card = screen.getByTestId("outcome-heading").closest("div.rounded-lg");
    expect(card?.className).toContain("border-yellow-500");
    expect(card?.className).toContain("bg-yellow-50");
  });

  it("renders Failed status with max turns failure message", () => {
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
});
