import { render, screen, fireEvent } from "@testing-library/react";
import { ScenarioSelector } from "@/components/arena/ScenarioSelector";
import type { ScenarioSummary } from "@/lib/api";

const mockScenarios: ScenarioSummary[] = [
  { id: "talent_war", name: "The Talent War", description: "HR negotiation", difficulty: "beginner" },
  { id: "ma_buyout", name: "M&A Buyout", description: "Corporate acquisition", difficulty: "intermediate" },
  { id: "b2b_sales", name: "B2B Sales", description: "SaaS contract", difficulty: "advanced" },
];

describe("ScenarioSelector", () => {
  const defaultProps = {
    scenarios: mockScenarios,
    selectedId: null,
    onSelect: vi.fn(),
    isLoading: false,
    error: null,
  };

  // Req 1.2: placeholder option
  it("renders placeholder 'Select Simulation Environment' when no scenario selected", () => {
    render(<ScenarioSelector {...defaultProps} />);
    const select = screen.getByRole("combobox");
    expect(select).toHaveValue("");
    expect(screen.getByText("Select Simulation Environment")).toBeInTheDocument();
  });

  // Req 1.2: renders scenario options
  it("renders all scenario options from the scenarios prop", () => {
    render(<ScenarioSelector {...defaultProps} />);
    for (const s of mockScenarios) {
      expect(screen.getByText(new RegExp(s.name))).toBeInTheDocument();
    }
    // placeholder + 3 scenarios
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(4);
  });

  // Req 1.5: loading state disables select
  it("disables the select when isLoading is true", () => {
    render(<ScenarioSelector {...defaultProps} isLoading={true} />);
    expect(screen.getByRole("combobox")).toBeDisabled();
  });

  // Req 1.5: not disabled when not loading
  it("enables the select when isLoading is false", () => {
    render(<ScenarioSelector {...defaultProps} isLoading={false} />);
    expect(screen.getByRole("combobox")).not.toBeDisabled();
  });

  // Req 1.4: error message display
  it("displays error message when error prop is set", () => {
    render(
      <ScenarioSelector {...defaultProps} error="Could not load scenarios" />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Could not load scenarios",
    );
  });

  it("does not display error when error prop is null", () => {
    render(<ScenarioSelector {...defaultProps} error={null} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  // Selection fires onSelect
  it("calls onSelect with the scenario id when a scenario is selected", () => {
    const onSelect = vi.fn();
    render(<ScenarioSelector {...defaultProps} onSelect={onSelect} />);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "ma_buyout" },
    });
    expect(onSelect).toHaveBeenCalledWith("ma_buyout");
  });

  // Selecting placeholder does not fire onSelect
  it("does not call onSelect when placeholder is selected", () => {
    const onSelect = vi.fn();
    render(
      <ScenarioSelector
        {...defaultProps}
        selectedId="talent_war"
        onSelect={onSelect}
      />,
    );
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "" },
    });
    expect(onSelect).not.toHaveBeenCalled();
  });

  // Reflects selectedId
  it("reflects the selectedId prop as the current value", () => {
    render(<ScenarioSelector {...defaultProps} selectedId="b2b_sales" />);
    expect(screen.getByRole("combobox")).toHaveValue("b2b_sales");
  });
});
