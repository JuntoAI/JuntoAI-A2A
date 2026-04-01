import { render, screen } from "@testing-library/react";
import MetricsDashboard from "@/components/glassbox/MetricsDashboard";

const defaultProps = {
  currentOffer: 250000,
  regulatorStatuses: {} as Record<string, "CLEAR" | "WARNING" | "BLOCKED">,
  turnNumber: 3,
  maxTurns: 15,
  tokenBalance: 85,
};

describe("MetricsDashboard", () => {
  it("renders Current Offer formatted as currency", () => {
    render(<MetricsDashboard {...defaultProps} />);

    const offer = screen.getByTestId("current-offer");
    expect(offer.textContent).toBe("$250,000");
  });

  it('renders Turn Counter as "Turn: X / Y"', () => {
    render(<MetricsDashboard {...defaultProps} />);

    const counter = screen.getByTestId("turn-counter");
    expect(counter.textContent).toBe("Turn: 3 / 15");
  });

  it('renders Token Balance as "Tokens: X / 100"', () => {
    render(<MetricsDashboard {...defaultProps} />);

    const balance = screen.getByTestId("token-balance");
    expect(balance.textContent).toBe("Tokens: 85 / 100");
  });

  it("renders regulator traffic lights with correct color classes", () => {
    const regulatorStatuses: Record<string, "CLEAR" | "WARNING" | "BLOCKED"> = {
      "EU Regulator": "CLEAR",
      "SEC Regulator": "WARNING",
      "HR Compliance": "BLOCKED",
    };
    render(
      <MetricsDashboard {...defaultProps} regulatorStatuses={regulatorStatuses} />,
    );

    const lights = screen.getAllByTestId("regulator-traffic-light");
    expect(lights).toHaveLength(3);

    // Verify specific color indicators exist
    expect(screen.getByTestId("traffic-light-clear")).toBeInTheDocument();
    expect(screen.getByTestId("traffic-light-clear").className).toContain("bg-green-500");

    expect(screen.getByTestId("traffic-light-warning")).toBeInTheDocument();
    expect(screen.getByTestId("traffic-light-warning").className).toContain("bg-yellow-500");

    expect(screen.getByTestId("traffic-light-blocked")).toBeInTheDocument();
    expect(screen.getByTestId("traffic-light-blocked").className).toContain("bg-red-500");
  });

  it("renders no traffic lights when regulatorStatuses is empty", () => {
    render(<MetricsDashboard {...defaultProps} regulatorStatuses={{}} />);

    expect(screen.queryByTestId("regulator-traffic-light")).not.toBeInTheDocument();
  });
});
