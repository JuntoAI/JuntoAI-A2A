import { render, screen, fireEvent } from "@testing-library/react";
import { ScenarioSelector } from "@/components/arena/ScenarioSelector";
import type { ScenarioSummary } from "@/lib/api";

const mockScenarios: ScenarioSummary[] = [
  { id: "talent_war", name: "The Talent War", description: "HR negotiation", difficulty: "beginner" },
  { id: "ma_buyout", name: "M&A Buyout", description: "Corporate acquisition", difficulty: "intermediate" },
  { id: "b2b_sales", name: "B2B Sales", description: "SaaS contract", difficulty: "advanced" },
];

const mockCustomScenarios: ScenarioSummary[] = [
  { id: "custom_1", name: "My Custom Scenario", description: "Custom desc", difficulty: "intermediate" },
  { id: "custom_2", name: "Another Custom", description: "Another desc", difficulty: "beginner" },
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

  // --- New tests for custom scenarios and Build Your Own ---

  // Req 1.3: "My Scenarios" group renders with custom scenarios
  it("renders 'My Scenarios' optgroup when customScenarios are provided", () => {
    render(
      <ScenarioSelector
        {...defaultProps}
        customScenarios={mockCustomScenarios}
      />,
    );
    const optgroup = screen.getByRole("group", { name: "My Scenarios" });
    expect(optgroup).toBeInTheDocument();
    expect(screen.getByText("My Custom Scenario")).toBeInTheDocument();
    expect(screen.getByText("Another Custom")).toBeInTheDocument();
  });

  // Req 1.3: empty custom scenarios hides "My Scenarios" group
  it("does not render 'My Scenarios' optgroup when customScenarios is empty", () => {
    render(
      <ScenarioSelector {...defaultProps} customScenarios={[]} />,
    );
    expect(screen.queryByRole("group", { name: "My Scenarios" })).not.toBeInTheDocument();
  });

  // Backward compat: no customScenarios prop at all
  it("does not render 'My Scenarios' optgroup when customScenarios prop is omitted", () => {
    render(<ScenarioSelector {...defaultProps} />);
    expect(screen.queryByRole("group", { name: "My Scenarios" })).not.toBeInTheDocument();
  });

  // Req 1.1: "Build Your Own Scenario" option renders
  it("renders 'Build Your Own Scenario' option", () => {
    render(<ScenarioSelector {...defaultProps} />);
    expect(screen.getByText(/Build Your Own Scenario/)).toBeInTheDocument();
  });

  // Req 1.2: "Build Your Own" triggers onBuildOwn callback
  it("calls onBuildOwn when 'Build Your Own Scenario' is selected", () => {
    const onBuildOwn = vi.fn();
    const onSelect = vi.fn();
    render(
      <ScenarioSelector
        {...defaultProps}
        onSelect={onSelect}
        onBuildOwn={onBuildOwn}
      />,
    );
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "__build_your_own__" },
    });
    expect(onBuildOwn).toHaveBeenCalledTimes(1);
    expect(onSelect).not.toHaveBeenCalled();
  });

  // Custom scenario selection triggers onSelect with the custom scenario ID
  it("calls onSelect with custom scenario ID when a custom scenario is selected", () => {
    const onSelect = vi.fn();
    render(
      <ScenarioSelector
        {...defaultProps}
        onSelect={onSelect}
        customScenarios={mockCustomScenarios}
      />,
    );
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "custom_1" },
    });
    expect(onSelect).toHaveBeenCalledWith("custom_1");
  });

  // Backward compat: works without onBuildOwn (no crash)
  it("does not crash when Build Your Own is selected without onBuildOwn callback", () => {
    render(<ScenarioSelector {...defaultProps} />);
    // Should not throw
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "__build_your_own__" },
    });
  });
});
