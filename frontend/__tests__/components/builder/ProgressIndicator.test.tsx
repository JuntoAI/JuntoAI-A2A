import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import {
  ProgressIndicator,
  computeProgress,
} from "@/components/builder/ProgressIndicator";
import type { ArenaScenario } from "@/lib/api";

// ---------------------------------------------------------------------------
// Unit tests: percentage calculation
// ---------------------------------------------------------------------------

describe("computeProgress", () => {
  it("returns 0 for empty object", () => {
    expect(computeProgress({})).toBe(0);
  });

  it("returns 14 for 1 of 7 sections", () => {
    expect(computeProgress({ name: "Test" })).toBe(14);
  });

  it("returns 29 for 2 of 7 sections", () => {
    expect(computeProgress({ name: "Test", id: "test-id" })).toBe(29);
  });

  it("returns 100 for all 7 sections populated", () => {
    const full: Partial<ArenaScenario> = {
      id: "test",
      name: "Test",
      description: "Desc",
      agents: [{ name: "A", role: "buyer", goals: ["g"], model_id: "m", type: "negotiator" }],
      toggles: [{ id: "t1", label: "T1", target_agent_role: "buyer" }],
      negotiation_params: { max_turns: 10 },
      outcome_receipt: { equivalent_human_time: "1h", process_label: "P" },
    };
    expect(computeProgress(full)).toBe(100);
  });

  it("does not count empty arrays as populated", () => {
    expect(computeProgress({ agents: [] as never })).toBe(0);
  });

  it("does not count empty strings as populated", () => {
    expect(computeProgress({ name: "" })).toBe(0);
  });

  it("does not count empty objects as populated", () => {
    expect(computeProgress({ negotiation_params: {} as never })).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Component tests
// ---------------------------------------------------------------------------

describe("ProgressIndicator component", () => {
  const onSave = vi.fn();

  it("displays correct percentage", () => {
    render(
      <ProgressIndicator
        scenarioJson={{ name: "Test", id: "x" }}
        isValid={false}
        onSave={onSave}
      />,
    );
    expect(screen.getByText("29%")).toBeInTheDocument();
  });

  it("save button is disabled when not 100% or not valid", () => {
    render(
      <ProgressIndicator
        scenarioJson={{ name: "Test" }}
        isValid={false}
        onSave={onSave}
      />,
    );
    const btn = screen.getByTestId("save-button");
    expect(btn).toBeDisabled();
  });

  it("save button is disabled at 100% but invalid", () => {
    const full: Partial<ArenaScenario> = {
      id: "t", name: "T", description: "D",
      agents: [{ name: "A", role: "r", goals: ["g"], model_id: "m", type: "negotiator" }],
      toggles: [{ id: "t1", label: "T1", target_agent_role: "r" }],
      negotiation_params: { max_turns: 10 },
      outcome_receipt: { equivalent_human_time: "1h", process_label: "P" },
    };
    render(
      <ProgressIndicator scenarioJson={full} isValid={false} onSave={onSave} />,
    );
    expect(screen.getByTestId("save-button")).toBeDisabled();
  });

  it("save button is enabled at 100% and valid", () => {
    const full: Partial<ArenaScenario> = {
      id: "t", name: "T", description: "D",
      agents: [{ name: "A", role: "r", goals: ["g"], model_id: "m", type: "negotiator" }],
      toggles: [{ id: "t1", label: "T1", target_agent_role: "r" }],
      negotiation_params: { max_turns: 10 },
      outcome_receipt: { equivalent_human_time: "1h", process_label: "P" },
    };
    render(
      <ProgressIndicator scenarioJson={full} isValid={true} onSave={onSave} />,
    );
    const btn = screen.getByTestId("save-button");
    expect(btn).not.toBeDisabled();
  });

  it("calls onSave when save button is clicked", () => {
    const full: Partial<ArenaScenario> = {
      id: "t", name: "T", description: "D",
      agents: [{ name: "A", role: "r", goals: ["g"], model_id: "m", type: "negotiator" }],
      toggles: [{ id: "t1", label: "T1", target_agent_role: "r" }],
      negotiation_params: { max_turns: 10 },
      outcome_receipt: { equivalent_human_time: "1h", process_label: "P" },
    };
    render(
      <ProgressIndicator scenarioJson={full} isValid={true} onSave={onSave} />,
    );
    fireEvent.click(screen.getByTestId("save-button"));
    expect(onSave).toHaveBeenCalledOnce();
  });

  it("renders progressbar with correct aria attributes", () => {
    render(
      <ProgressIndicator
        scenarioJson={{ name: "Test", id: "x", description: "D" }}
        isValid={false}
        onSave={onSave}
      />,
    );
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "43");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });
});
