import { render, screen, fireEvent } from "@testing-library/react";
import { ScenarioSelector } from "@/components/arena/ScenarioSelector";
import type { ScenarioSummary } from "@/lib/api";

const mockScenarios: ScenarioSummary[] = [
  { id: "talent_war", name: "The Talent War", description: "HR negotiation", difficulty: "beginner", category: "Corporate" },
  { id: "ma_buyout", name: "M&A Buyout", description: "Corporate acquisition", difficulty: "intermediate", category: "Corporate" },
  { id: "b2b_sales", name: "B2B Sales", description: "SaaS contract", difficulty: "advanced", category: "Corporate" },
];

const mockCustomScenarios: ScenarioSummary[] = [
  { id: "custom_1", name: "My Custom Scenario", description: "Custom desc", difficulty: "intermediate", category: "General" },
  { id: "custom_2", name: "Another Custom", description: "Another desc", difficulty: "beginner", category: "General" },
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

// ---------------------------------------------------------------------------
// Category Grouping Tests (Req 6.7, 6.8, 6.9, 6.10)
// ---------------------------------------------------------------------------

const multiCategoryScenarios: ScenarioSummary[] = [
  { id: "saas_negotiation", name: "SaaS Negotiation", description: "SaaS deal", difficulty: "intermediate", category: "Sales" },
  { id: "renewal_churn", name: "Renewal Churn Save", description: "Churn save", difficulty: "intermediate", category: "Sales" },
  { id: "talent_war", name: "The Talent War", description: "HR negotiation", difficulty: "beginner", category: "Corporate" },
  { id: "ma_buyout", name: "M&A Buyout", description: "Acquisition", difficulty: "advanced", category: "Corporate" },
  { id: "family_curfew", name: "Family Curfew", description: "Curfew negotiation", difficulty: "beginner", category: "Everyday" },
  { id: "misc_scenario", name: "Misc Scenario", description: "General scenario", difficulty: "fun", category: "General" },
];

describe("ScenarioSelector — Category Grouping", () => {
  const baseProps = {
    scenarios: multiCategoryScenarios,
    selectedId: null,
    onSelect: vi.fn(),
    isLoading: false,
    error: null,
  };

  // Req 6.7: optgroup elements rendered with correct labels
  it("renders <optgroup> elements for each category", () => {
    render(<ScenarioSelector {...baseProps} />);
    expect(screen.getByRole("group", { name: "Sales" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Corporate" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Everyday" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "General" })).toBeInTheDocument();
  });

  // Req 6.8: scenarios within each group retain [Difficulty] prefix
  it("scenarios within groups retain [Difficulty] prefix", () => {
    render(<ScenarioSelector {...baseProps} />);
    expect(screen.getByText("[Intermediate] SaaS Negotiation")).toBeInTheDocument();
    expect(screen.getByText("[Intermediate] Renewal Churn Save")).toBeInTheDocument();
    expect(screen.getByText("[Beginner] The Talent War")).toBeInTheDocument();
    expect(screen.getByText("[Advanced] M&A Buyout")).toBeInTheDocument();
    expect(screen.getByText("[Beginner] Family Curfew")).toBeInTheDocument();
    expect(screen.getByText("[Fun] Misc Scenario")).toBeInTheDocument();
  });

  // Req 6.9: groups sorted alphabetically with "General" last
  it("sorts category groups alphabetically with 'General' last", () => {
    const { container } = render(<ScenarioSelector {...baseProps} />);
    const optgroups = container.querySelectorAll("optgroup");
    const labels = Array.from(optgroups).map((og) => og.getAttribute("label"));

    // "Corporate", "Everyday", "Sales" alphabetically, then "General" last
    const categoryLabels = labels.filter(
      (l) => l !== "My Scenarios",
    );
    expect(categoryLabels[0]).toBe("Corporate");
    expect(categoryLabels[1]).toBe("Everyday");
    expect(categoryLabels[2]).toBe("Sales");
    expect(categoryLabels[categoryLabels.length - 1]).toBe("General");
  });

  // Req 6.10: "My Scenarios" and "Build Your Own" remain at the bottom
  it("'My Scenarios' and 'Build Your Own' remain at the bottom after category groups", () => {
    const customScenarios: ScenarioSummary[] = [
      { id: "custom_1", name: "My Custom", description: "Custom", difficulty: "beginner", category: "General" },
    ];
    const { container } = render(
      <ScenarioSelector {...baseProps} customScenarios={customScenarios} />,
    );
    const optgroups = container.querySelectorAll("optgroup");
    const labels = Array.from(optgroups).map((og) => og.getAttribute("label"));

    // "My Scenarios" should be the last optgroup
    expect(labels[labels.length - 1]).toBe("My Scenarios");

    // "Build Your Own Scenario" should appear after all optgroups
    const select = container.querySelector("select")!;
    const allOptions = Array.from(select.querySelectorAll("option"));
    const buildOwnOption = allOptions.find((o) =>
      o.textContent?.includes("Build Your Own Scenario"),
    );
    expect(buildOwnOption).toBeDefined();

    // Verify Build Your Own is the last non-disabled option
    const lastOption = allOptions[allOptions.length - 1];
    expect(lastOption.textContent).toContain("Build Your Own Scenario");
  });
});

// ---------------------------------------------------------------------------
// Edit Button Tests (Req 7.1, 7.7)
// ---------------------------------------------------------------------------

describe("ScenarioSelector — Edit Button", () => {
  const baseProps = {
    scenarios: mockScenarios,
    selectedId: null,
    onSelect: vi.fn(),
    isLoading: false,
    error: null,
  };

  // Req 7.1: edit button visible when custom scenario selected + onEditCustom provided
  it("shows edit button when a custom scenario is selected and onEditCustom is provided", () => {
    render(
      <ScenarioSelector
        {...baseProps}
        customScenarios={mockCustomScenarios}
        selectedId="custom_1"
        onEditCustom={vi.fn()}
      />,
    );
    expect(
      screen.getByLabelText("Edit custom scenario: My Custom Scenario"),
    ).toBeInTheDocument();
  });

  // Req 7.7: edit button hidden for built-in scenarios
  it("does NOT show edit button when a built-in scenario is selected", () => {
    render(
      <ScenarioSelector
        {...baseProps}
        customScenarios={mockCustomScenarios}
        selectedId="talent_war"
        onEditCustom={vi.fn()}
      />,
    );
    expect(
      screen.queryByLabelText(/Edit custom scenario/),
    ).not.toBeInTheDocument();
  });

  // Req 7.7: edit button hidden when nothing selected
  it("does NOT show edit button when no scenario is selected", () => {
    render(
      <ScenarioSelector
        {...baseProps}
        customScenarios={mockCustomScenarios}
        selectedId={null}
        onEditCustom={vi.fn()}
      />,
    );
    expect(
      screen.queryByLabelText(/Edit custom scenario/),
    ).not.toBeInTheDocument();
  });

  // Edit button hidden when onEditCustom is not provided
  it("does NOT show edit button when onEditCustom prop is not provided", () => {
    render(
      <ScenarioSelector
        {...baseProps}
        customScenarios={mockCustomScenarios}
        selectedId="custom_1"
      />,
    );
    expect(
      screen.queryByLabelText(/Edit custom scenario/),
    ).not.toBeInTheDocument();
  });

  // Req 7.1: clicking edit calls onEditCustom with scenario ID and name
  it("calls onEditCustom with scenario ID and name when clicked", () => {
    const onEditCustom = vi.fn();
    render(
      <ScenarioSelector
        {...baseProps}
        customScenarios={mockCustomScenarios}
        selectedId="custom_1"
        onEditCustom={onEditCustom}
      />,
    );
    fireEvent.click(
      screen.getByLabelText("Edit custom scenario: My Custom Scenario"),
    );
    expect(onEditCustom).toHaveBeenCalledTimes(1);
    expect(onEditCustom).toHaveBeenCalledWith("custom_1", "My Custom Scenario");
  });

  // Edit button disabled during delete operation
  it("disables edit button when isDeleting is true", () => {
    render(
      <ScenarioSelector
        {...baseProps}
        customScenarios={mockCustomScenarios}
        selectedId="custom_1"
        onEditCustom={vi.fn()}
        isDeleting={true}
      />,
    );
    expect(
      screen.getByLabelText("Edit custom scenario: My Custom Scenario"),
    ).toBeDisabled();
  });
});
