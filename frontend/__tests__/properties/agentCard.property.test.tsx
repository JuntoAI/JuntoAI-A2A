import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import * as fc from "fast-check";
import { AgentCard } from "@/components/arena/AgentCard";
import { FC_NUM_RUNS } from "../fc-config";

/**
 * Feature: 060_a2a-glass-box-ui, Property 4: Agent Card displays all required fields
 *
 * Generate random agent definitions with random name, role, goals, model_id.
 * Render AgentCard, verify all fields present in output.
 *
 * **Validates: Requirements 2.2**
 */

// ---------------------------------------------------------------------------
// Arbitraries — safe strings that render cleanly in HTML
// ---------------------------------------------------------------------------

const safeStringArb = fc.stringMatching(/^[a-zA-Z][a-zA-Z0-9 ]{0,29}$/);

const agentArb = fc.record({
  name: safeStringArb,
  role: safeStringArb,
  goals: fc.array(safeStringArb, { minLength: 1, maxLength: 5 }),
  modelId: safeStringArb,
});

// ---------------------------------------------------------------------------
// Property tests
// ---------------------------------------------------------------------------

describe("Property 4: Agent Card displays all required fields", () => {
  /**
   * **Validates: Requirements 2.2**
   *
   * For any randomly generated agent definition, the AgentCard must render
   * the agent's name, role, all goals, and model_id in the DOM.
   */
  it("AgentCard renders name, role, all goals, and modelId for any agent", () => {
    fc.assert(
      fc.property(
        agentArb,
        fc.integer({ min: 0, max: 7 }),
        (agent, index) => {
          const { unmount, container } = render(
            <AgentCard
              name={agent.name}
              role={agent.role}
              goals={agent.goals}
              modelId={agent.modelId}
              index={index}
            />,
          );

          const html = container.innerHTML;

          // Name must be present
          expect(html).toContain(agent.name);

          // Role must be present
          expect(html).toContain(agent.role);

          // Every goal must be present (rendered as "• {goal}")
          for (const goal of agent.goals) {
            expect(html).toContain(goal);
          }

          // Model ID must be present (rendered as "Model: {modelId}")
          expect(html).toContain(`Model: ${agent.modelId}`);

          unmount();
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
