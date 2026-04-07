import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import * as fc from "fast-check";
import { ScenarioSelector } from "@/components/arena/ScenarioSelector";
import { AgentCard } from "@/components/arena/AgentCard";
import { InformationToggle } from "@/components/arena/InformationToggle";

/**
 * Feature: 060_a2a-glass-box-ui, Property 3: Scenario selection renders correct component counts
 *
 * Generate random scenario objects with varying agent/toggle counts.
 * Render ScenarioSelector with the scenarios, verify option count matches.
 * Render AgentCards for each agent, verify card count matches.
 * Render InformationToggles for each toggle, verify toggle count matches.
 *
 * **Validates: Requirements 1.3, 2.1, 3.1**
 */

// ---------------------------------------------------------------------------
// Arbitraries — safe strings that render cleanly in HTML
// ---------------------------------------------------------------------------

const safeStringArb = fc.stringMatching(/^[a-zA-Z][a-zA-Z0-9 ]{0,29}$/);

const agentArb = fc.record({
  name: safeStringArb,
  role: safeStringArb,
  goals: fc.array(safeStringArb, { minLength: 1, maxLength: 3 }),
  modelId: safeStringArb,
});

const toggleArb = fc.record({
  id: fc.stringMatching(/^[a-z][a-z0-9_]{0,19}$/),
  label: safeStringArb,
});

const scenarioArb = fc.record({
  agents: fc.array(agentArb, { minLength: 2, maxLength: 6 }),
  toggles: fc.array(toggleArb, { minLength: 1, maxLength: 5 }),
});

// ---------------------------------------------------------------------------
// Property tests
// ---------------------------------------------------------------------------

describe("Property 3: Scenario selection renders correct component counts", () => {
  /**
   * **Validates: Requirement 1.3**
   *
   * ScenarioSelector option count must equal scenarios.length + 1 (placeholder).
   */
  it("ScenarioSelector renders one option per scenario plus placeholder", { timeout: 30000 }, () => {
    const difficultyArb = fc.constantFrom("beginner", "intermediate", "advanced", "fun") as fc.Arbitrary<"beginner" | "intermediate" | "advanced" | "fun">;

    const scenarioSummaryArb = fc.array(
      fc.record({
        id: fc.stringMatching(/^[a-z][a-z0-9_]{2,14}$/),
        name: safeStringArb,
        description: safeStringArb,
        difficulty: difficultyArb,
      }),
      { minLength: 1, maxLength: 6 },
    );

    fc.assert(
      fc.property(scenarioSummaryArb, (scenarios) => {
        const { unmount } = render(
          <ScenarioSelector
            scenarios={scenarios}
            selectedId={null}
            onSelect={() => {}}
            isLoading={false}
            error={null}
          />,
        );

        const options = screen.getAllByRole("option");
        // +1 placeholder + scenarios + 1 disabled divider + 1 "Build Your Own"
        expect(options).toHaveLength(scenarios.length + 3);

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirement 2.1**
   *
   * Rendering one AgentCard per agent in the scenario must produce
   * exactly agents.length cards.
   */
  it("renders exactly one AgentCard per agent in the scenario", { timeout: 30000 }, () => {
    fc.assert(
      fc.property(scenarioArb, (scenario) => {
        const { unmount, container } = render(
          <div>
            {scenario.agents.map((agent, i) => (
              <AgentCard
                key={i}
                name={agent.name}
                role={agent.role}
                goals={agent.goals}
                modelId={agent.modelId}
                index={i}
              />
            ))}
          </div>,
        );

        // Each AgentCard renders a "Model: ..." text
        const modelTexts = container.querySelectorAll("p");
        const modelLabels = Array.from(modelTexts).filter((p) =>
          p.textContent?.startsWith("Model:"),
        );
        expect(modelLabels).toHaveLength(scenario.agents.length);

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirement 3.1**
   *
   * Rendering one InformationToggle per toggle in the scenario must produce
   * exactly toggles.length checkboxes.
   */
  it("renders exactly one InformationToggle per toggle in the scenario", { timeout: 30000 }, () => {
    fc.assert(
      fc.property(scenarioArb, (scenario) => {
        const { unmount } = render(
          <div>
            {scenario.toggles.map((toggle) => (
              <InformationToggle
                key={toggle.id}
                id={toggle.id}
                label={toggle.label}
                checked={false}
                onChange={() => {}}
              />
            ))}
          </div>,
        );

        const checkboxes = screen.getAllByRole("checkbox");
        expect(checkboxes).toHaveLength(scenario.toggles.length);

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});
