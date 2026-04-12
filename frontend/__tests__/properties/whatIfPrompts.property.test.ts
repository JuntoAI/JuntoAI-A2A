import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { FC_NUM_RUNS } from "../fc-config";
import {
  generateWhatIfPrompts,
  buildDeepLinkUrl,
} from "@/lib/whatIfPrompts";
import type { ToggleDefinition, AgentDefinition } from "@/lib/api";
import type { PromptGeneratorInput } from "@/lib/whatIfPrompts";

// ---------------------------------------------------------------------------
// Shared arbitraries
// ---------------------------------------------------------------------------

const toggleIdArb = fc.stringMatching(/^[a-z][a-z0-9_]{1,12}$/);
const labelArb = fc.stringMatching(/^[A-Z][a-zA-Z ]{2,20}$/);
const roleArb = fc.stringMatching(/^[a-z][a-z_]{1,10}$/);
const agentNameArb = fc.stringMatching(/^[A-Z][a-z]{1,8}$/);

/** Generate a toggle definition with a given role. */
function toggleDefArb(role?: fc.Arbitrary<string>): fc.Arbitrary<ToggleDefinition> {
  return fc.record({
    id: toggleIdArb,
    label: labelArb,
    target_agent_role: role ?? roleArb,
  });
}

/** Generate an agent definition for a given role. */
function agentDefForRole(role: string): AgentDefinition {
  return {
    name: role.charAt(0).toUpperCase() + role.slice(1),
    role,
    goals: ["goal"],
    model_id: "gemini-3-flash-preview",
    type: "negotiator",
  };
}

/** Build a full PromptGeneratorInput from toggles, active subset, agents, and deal status. */
function buildInput(
  toggles: ToggleDefinition[],
  activeToggleIds: string[],
  agents: AgentDefinition[],
  dealStatus: "Agreed" | "Blocked" | "Failed" = "Blocked",
  finalSummary: Record<string, unknown> = {},
): PromptGeneratorInput {
  return {
    toggles,
    activeToggleIds,
    agents,
    dealStatus,
    finalSummary,
    scenarioId: "test_scenario",
  };
}

/** Deduplicate toggle IDs so each toggle has a unique id. */
function deduplicateToggles(toggles: ToggleDefinition[]): ToggleDefinition[] {
  const seen = new Set<string>();
  return toggles.filter((t) => {
    if (seen.has(t.id)) return false;
    seen.add(t.id);
    return true;
  });
}

/** Build agents array covering all unique roles in the toggles. */
function agentsForToggles(toggles: ToggleDefinition[]): AgentDefinition[] {
  const roles = new Set(toggles.map((t) => t.target_agent_role));
  return Array.from(roles).map(agentDefForRole);
}

const dealStatusArb = fc.constantFrom<"Agreed" | "Blocked" | "Failed">(
  "Agreed",
  "Blocked",
  "Failed",
);

// ---------------------------------------------------------------------------
// Feature: 260_what-if-prompts
// ---------------------------------------------------------------------------

describe("Feature: 260_what-if-prompts", () => {

  // -------------------------------------------------------------------------
  // Property 1: Inactive toggle computation is correct
  // -------------------------------------------------------------------------

  /**
   * **Validates: Requirements 1.1, 1.2**
   *
   * For any set of toggle definitions and any subset of active toggle IDs,
   * generateWhatIfPrompts produces prompts only for toggles NOT in the active
   * set, and the count matches the inactive toggle count (capped at 3).
   */
  it("Property 1: Inactive toggle computation is correct", () => {
    const togglesWithActiveArb = fc
      .array(toggleDefArb(), { minLength: 1, maxLength: 8 })
      .map(deduplicateToggles)
      .filter((t) => t.length >= 1)
      .chain((toggles) =>
        fc.subarray(toggles.map((t) => t.id), { minLength: 0 }).map((activeIds) => ({
          toggles,
          activeIds,
        })),
      );

    fc.assert(
      fc.property(togglesWithActiveArb, ({ toggles, activeIds }) => {
        const agents = agentsForToggles(toggles);
        const input = buildInput(toggles, activeIds, agents);
        const prompts = generateWhatIfPrompts(input);

        const inactiveToggles = toggles.filter(
          (t) => !activeIds.includes(t.id),
        );

        // If all toggles are active, we get the baseline prompt
        if (inactiveToggles.length === 0) {
          expect(prompts).toHaveLength(1);
          expect(prompts[0].toggleIds).toEqual([]);
          return;
        }

        // All returned prompts reference only inactive toggles
        for (const p of prompts) {
          for (const tid of p.toggleIds) {
            expect(activeIds).not.toContain(tid);
          }
        }

        // Count matches inactive count, capped at 3
        const expectedCount = Math.min(inactiveToggles.length, 3);
        expect(prompts.length).toBe(expectedCount);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  // -------------------------------------------------------------------------
  // Property 2: Prompt text contains toggle label and resolved agent name
  // -------------------------------------------------------------------------

  /**
   * **Validates: Requirements 1.3, 5.4**
   *
   * For any inactive toggle with a valid target_agent_role mapping to a
   * scenario agent, the generated prompt text contains the toggle's label
   * and the prompt's targetAgentName matches the agent whose role equals
   * the toggle's target_agent_role.
   */
  it("Property 2: Prompt text contains toggle label and resolved agent name", () => {
    fc.assert(
      fc.property(
        fc
          .array(toggleDefArb(), { minLength: 1, maxLength: 6 })
          .map(deduplicateToggles)
          .filter((t) => t.length >= 1),
        dealStatusArb,
        (toggles, dealStatus) => {
          const agents = agentsForToggles(toggles);
          // All toggles inactive → guaranteed prompts
          const input = buildInput(toggles, [], agents, dealStatus, {
            current_offer: 100,
            turns_completed: 5,
          });
          const prompts = generateWhatIfPrompts(input);

          for (const prompt of prompts) {
            // Each prompt references exactly one toggle
            expect(prompt.toggleIds).toHaveLength(1);
            const toggleId = prompt.toggleIds[0];
            const toggle = toggles.find((t) => t.id === toggleId)!;

            // Text contains the toggle label
            expect(prompt.text).toContain(toggle.label);

            // targetAgentName matches the agent whose role equals toggle's target_agent_role
            const expectedAgent = agents.find(
              (a) => a.role === toggle.target_agent_role,
            )!;
            expect(prompt.targetAgentName).toBe(expectedAgent.name);
          }
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });

  // -------------------------------------------------------------------------
  // Property 3: All-active scenario produces baseline prompt
  // -------------------------------------------------------------------------

  /**
   * **Validates: Requirements 1.4, 5.5**
   *
   * For any scenario where activeToggleIds contains every toggle ID,
   * generateWhatIfPrompts returns exactly one prompt with empty toggleIds.
   */
  it("Property 3: All-active scenario produces baseline prompt", () => {
    fc.assert(
      fc.property(
        fc
          .array(toggleDefArb(), { minLength: 1, maxLength: 8 })
          .map(deduplicateToggles)
          .filter((t) => t.length >= 1),
        dealStatusArb,
        (toggles, dealStatus) => {
          const agents = agentsForToggles(toggles);
          const allIds = toggles.map((t) => t.id);
          const input = buildInput(toggles, allIds, agents, dealStatus);
          const prompts = generateWhatIfPrompts(input);

          expect(prompts).toHaveLength(1);
          expect(prompts[0].toggleIds).toEqual([]);
          // Baseline text should mention "all variables active"
          expect(prompts[0].text).toContain("all variables active");
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });

  // -------------------------------------------------------------------------
  // Property 4: Output length never exceeds 3
  // -------------------------------------------------------------------------

  /**
   * **Validates: Requirements 1.5**
   *
   * For any valid PromptGeneratorInput, the length of the returned array
   * is at most 3.
   */
  it("Property 4: Output length never exceeds 3", () => {
    const togglesWithActiveArb = fc
      .array(toggleDefArb(), { minLength: 0, maxLength: 10 })
      .map(deduplicateToggles)
      .chain((toggles) =>
        fc.subarray(toggles.map((t) => t.id), { minLength: 0 }).map((activeIds) => ({
          toggles,
          activeIds,
        })),
      );

    fc.assert(
      fc.property(togglesWithActiveArb, dealStatusArb, ({ toggles, activeIds }, dealStatus) => {
        const agents = agentsForToggles(toggles);
        const input = buildInput(toggles, activeIds, agents, dealStatus, {
          current_offer: 50,
          turns_completed: 3,
        });
        const prompts = generateWhatIfPrompts(input);
        expect(prompts.length).toBeLessThanOrEqual(3);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  // -------------------------------------------------------------------------
  // Property 5: Role diversity maximization
  // -------------------------------------------------------------------------

  /**
   * **Validates: Requirements 1.6**
   *
   * For any scenario with >3 inactive toggles, the 3 selected prompts
   * cover at least min(3, uniqueRoleCount) distinct target_agent_role values.
   */
  it("Property 5: Role diversity maximization", () => {
    // Generate toggles targeting at least 2 distinct roles, with >3 total
    const multiRoleTogglesArb = fc
      .record({
        roles: fc.array(roleArb, { minLength: 2, maxLength: 5 }).chain((roles) => {
          const uniqueRoles = [...new Set(roles)];
          return uniqueRoles.length >= 2
            ? fc.constant(uniqueRoles)
            : fc.constant(["role_a", "role_b"]);
        }),
        countPerRole: fc.integer({ min: 1, max: 3 }),
      })
      .chain(({ roles, countPerRole }) => {
        // Create toggles spread across roles
        const toggles: ToggleDefinition[] = [];
        let idx = 0;
        for (const role of roles) {
          for (let i = 0; i < countPerRole; i++) {
            toggles.push({
              id: `t_${idx++}`,
              label: `Toggle ${idx}`,
              target_agent_role: role,
            });
          }
        }
        return fc.constant(toggles);
      })
      .filter((toggles) => toggles.length > 3);

    fc.assert(
      fc.property(multiRoleTogglesArb, (toggles) => {
        const agents = agentsForToggles(toggles);
        // All toggles inactive
        const input = buildInput(toggles, [], agents);
        const prompts = generateWhatIfPrompts(input);

        expect(prompts).toHaveLength(3);

        // Count distinct roles in selected prompts
        const selectedRoles = new Set<string>();
        for (const p of prompts) {
          const tid = p.toggleIds[0];
          const toggle = toggles.find((t) => t.id === tid)!;
          selectedRoles.add(toggle.target_agent_role);
        }

        const uniqueRoleCount = new Set(
          toggles.map((t) => t.target_agent_role),
        ).size;
        const expectedMinRoles = Math.min(3, uniqueRoleCount);
        expect(selectedRoles.size).toBeGreaterThanOrEqual(expectedMinRoles);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  // -------------------------------------------------------------------------
  // Property 6: Deal-status-specific prompt content
  // -------------------------------------------------------------------------

  /**
   * **Validates: Requirements 5.1, 5.2, 5.3**
   *
   * Agreed outcomes with current_offer > 0 → prompt text contains the offer value.
   * Blocked outcomes → prompt text references block.
   * Failed outcomes with turns_completed → prompt text references turn count.
   */
  describe("Property 6: Deal-status-specific prompt content", () => {
    const singleToggleWithAgent = () => {
      const role = "seller";
      const toggle: ToggleDefinition = {
        id: "t1",
        label: "Secret Offer",
        target_agent_role: role,
      };
      const agent = agentDefForRole(role);
      return { toggle, agent };
    };

    it("Agreed outcome with current_offer > 0 includes offer value in text", () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 999999 }),
          (offerValue) => {
            const { toggle, agent } = singleToggleWithAgent();
            const input = buildInput(
              [toggle],
              [],
              [agent],
              "Agreed",
              { current_offer: offerValue },
            );
            const prompts = generateWhatIfPrompts(input);
            expect(prompts).toHaveLength(1);
            expect(prompts[0].text).toContain(String(offerValue));
          },
        ),
        { numRuns: FC_NUM_RUNS },
      );
    });

    it("Blocked outcome references block in text", () => {
      fc.assert(
        fc.property(
          fc.constant(null), // no variable input needed, but we run 100 times for consistency
          () => {
            const { toggle, agent } = singleToggleWithAgent();
            const input = buildInput([toggle], [], [agent], "Blocked", {});
            const prompts = generateWhatIfPrompts(input);
            expect(prompts).toHaveLength(1);
            expect(prompts[0].text.toLowerCase()).toContain("block");
          },
        ),
        { numRuns: FC_NUM_RUNS },
      );
    });

    it("Failed outcome with turns_completed references turn count in text", () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 100 }),
          (turnsCompleted) => {
            const { toggle, agent } = singleToggleWithAgent();
            const input = buildInput(
              [toggle],
              [],
              [agent],
              "Failed",
              { turns_completed: turnsCompleted },
            );
            const prompts = generateWhatIfPrompts(input);
            expect(prompts).toHaveLength(1);
            expect(prompts[0].text).toContain(String(turnsCompleted));
          },
        ),
        { numRuns: FC_NUM_RUNS },
      );
    });
  });

  // -------------------------------------------------------------------------
  // Property 7: Deep-link URL round-trip
  // -------------------------------------------------------------------------

  /**
   * **Validates: Requirements 3.1, 3.2**
   *
   * For any scenario ID and any list of toggle IDs, parsing the URL produced
   * by buildDeepLinkUrl yields the original scenario ID and toggle ID list.
   */
  it("Property 7: Deep-link URL round-trip", () => {
    const scenarioIdArb = fc.stringMatching(/^[a-zA-Z][a-zA-Z0-9_]{1,20}$/);
    const toggleIdsArb = fc.array(toggleIdArb, { minLength: 0, maxLength: 6 });

    fc.assert(
      fc.property(scenarioIdArb, toggleIdsArb, (scenarioId, toggleIds) => {
        // Deduplicate toggle IDs
        const uniqueIds = [...new Set(toggleIds)];
        const url = buildDeepLinkUrl(scenarioId, uniqueIds);

        // Parse the URL
        const parsed = new URL(url, "http://localhost");
        const parsedScenario = parsed.searchParams.get("scenario");
        expect(parsedScenario).toBe(scenarioId);

        if (uniqueIds.length === 0) {
          // No toggles param when empty
          expect(parsed.searchParams.has("toggles")).toBe(false);
        } else {
          const parsedToggles = parsed.searchParams.get("toggles")!.split(",");
          expect(parsedToggles).toEqual(uniqueIds);
        }
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
