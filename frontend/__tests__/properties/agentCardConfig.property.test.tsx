import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import * as fc from "fast-check";
import { AgentCard } from "@/components/arena/AgentCard";
import type { AgentCardProps } from "@/components/arena/AgentCard";
import { FC_NUM_RUNS } from "../fc-config";

/**
 * Feature: agent-advanced-config, Property 11: Agent card visual indicators reflect configuration state
 *
 * For any agent card, when `hasCustomPrompt` is true, a visual indicator
 * (dot/badge) should be present in the rendered output. When `modelOverride`
 * is non-null, the displayed model text should show the overridden model name
 * instead of the default, with "(override)" text.
 *
 * **Validates: Requirements 1.4, 1.5**
 */

const ALPHA = "abcdefghijklmnopqrstuvwxyz";
const ALPHANUM = "abcdefghijklmnopqrstuvwxyz0123456789";

function charSetString(chars: string, min: number, max: number) {
  return fc
    .array(fc.integer({ min: 0, max: chars.length - 1 }), {
      minLength: min,
      maxLength: max,
    })
    .map((indices) => indices.map((i) => chars[i]).join(""));
}

/** Generate a model_id-like string: "prefix-suffix" */
const modelIdArb = fc
  .record({
    prefix: charSetString(ALPHA, 2, 8),
    suffix: charSetString(ALPHANUM, 1, 10),
  })
  .map(({ prefix, suffix }) => `${prefix}-${suffix}`);

/** Generate a full set of AgentCard props with random config state */
const agentCardConfigArb = fc.record({
  hasCustomPrompt: fc.boolean(),
  modelOverride: fc.oneof(fc.constant(null), modelIdArb),
  defaultModelId: modelIdArb,
  agentName: charSetString(ALPHA, 2, 12),
  agentRole: charSetString(ALPHA, 2, 10),
});

describe("Property 11: Agent card visual indicators reflect configuration state", () => {
  /**
   * **Validates: Requirements 1.4**
   *
   * When hasCustomPrompt is true, the custom-prompt-indicator element must
   * be present. When false, it must be absent.
   */
  it("custom prompt indicator presence matches hasCustomPrompt prop", () => {
    fc.assert(
      fc.property(
        agentCardConfigArb,
        ({ hasCustomPrompt, modelOverride, defaultModelId, agentName, agentRole }) => {
          const props: AgentCardProps = {
            name: agentName,
            role: agentRole,
            goals: ["Goal 1"],
            modelId: defaultModelId,
            index: 0,
            hasCustomPrompt,
            modelOverride,
            onAdvancedConfig: vi.fn(),
          };

          const { unmount } = render(createElement(AgentCard, props));

          const indicator = screen.queryByTestId("custom-prompt-indicator");

          if (hasCustomPrompt) {
            expect(indicator).not.toBeNull();
          } else {
            expect(indicator).toBeNull();
          }

          unmount();
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });

  /**
   * **Validates: Requirements 1.5**
   *
   * When modelOverride is non-null, "(override)" text must be present and
   * the override model name must be displayed. When null, "(override)" must
   * be absent and the default model name must be displayed.
   */
  it("model override indicator and text reflect modelOverride prop", () => {
    fc.assert(
      fc.property(
        agentCardConfigArb,
        ({ hasCustomPrompt, modelOverride, defaultModelId, agentName, agentRole }) => {
          const props: AgentCardProps = {
            name: agentName,
            role: agentRole,
            goals: ["Goal 1"],
            modelId: defaultModelId,
            index: 0,
            hasCustomPrompt,
            modelOverride,
            onAdvancedConfig: vi.fn(),
          };

          const { unmount, container } = render(createElement(AgentCard, props));

          const overrideText = screen.queryByText("(override)");

          if (modelOverride !== null) {
            // "(override)" text must be present
            expect(overrideText).not.toBeNull();
            // The overridden model name must appear in the document
            expect(container.textContent).toContain(modelOverride);
          } else {
            // "(override)" text must be absent
            expect(overrideText).toBeNull();
            // The default model name must appear
            expect(container.textContent).toContain(defaultModelId);
          }

          unmount();
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
