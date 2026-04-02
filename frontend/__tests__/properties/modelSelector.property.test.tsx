import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import * as fc from "fast-check";
import { AdvancedConfigModal } from "@/components/arena/AdvancedConfigModal";
import type { AdvancedConfigModalProps } from "@/components/arena/AdvancedConfigModal";
import type { ModelInfo } from "@/lib/api";

/**
 * Feature: agent-advanced-config, Property 12: Model selector default ordering and labeling
 *
 * For any available models list and default model_id, the Model_Selector
 * dropdown should display the default model as the first option with a
 * "(default)" suffix, and all models should display their family as a
 * secondary label.
 *
 * **Validates: Requirements 2.5, 10.2, 10.3, 10.4**
 */

const ALPHA = "abcdefghijklmnopqrstuvwxyz";
const ALPHANUM = "abcdefghijklmnopqrstuvwxyz0123456789";

/** Generate a string of given length range from a character set. */
function charSetString(chars: string, min: number, max: number) {
  return fc
    .array(fc.integer({ min: 0, max: chars.length - 1 }), {
      minLength: min,
      maxLength: max,
    })
    .map((indices) => indices.map((i) => chars[i]).join(""));
}

/** Arbitrary that generates a valid ModelInfo with a unique model_id. */
const modelInfoArb = fc
  .record({
    prefix: charSetString(ALPHA, 2, 8),
    suffix: charSetString(ALPHANUM, 1, 10),
    family: charSetString(ALPHA, 2, 8),
  })
  .map(({ prefix, suffix, family }) => ({
    model_id: `${prefix}-${suffix}`,
    family,
  }));

/**
 * Generate a non-empty list of ModelInfo objects with unique model_ids,
 * plus a defaultModelId picked from that list.
 */
const modelsWithDefaultArb = fc
  .array(modelInfoArb, { minLength: 1, maxLength: 10 })
  .chain((rawModels) => {
    // Deduplicate by model_id
    const seen = new Set<string>();
    const models: ModelInfo[] = [];
    for (const m of rawModels) {
      if (!seen.has(m.model_id)) {
        seen.add(m.model_id);
        models.push(m);
      }
    }
    // Pick one index as the default
    return fc.record({
      models: fc.constant(models),
      defaultIdx: fc.integer({ min: 0, max: models.length - 1 }),
    });
  })
  .map(({ models, defaultIdx }) => ({
    models,
    defaultModelId: models[defaultIdx].model_id,
  }));

describe("Property 12: Model selector default ordering and labeling", () => {
  /**
   * **Validates: Requirements 2.5, 10.4**
   *
   * The default model must be the first option in the select and must
   * have " (default)" appended to its label text.
   */
  it("default model is the first option with '(default)' suffix", () => {
    fc.assert(
      fc.property(modelsWithDefaultArb, ({ models, defaultModelId }) => {
        const props: AdvancedConfigModalProps = {
          isOpen: true,
          agentName: "Agent",
          agentRole: "Role",
          defaultModelId,
          availableModels: models,
          initialCustomPrompt: "",
          initialModelOverride: null,
          onSave: vi.fn(),
          onCancel: vi.fn(),
        };

        const { unmount } = render(createElement(AdvancedConfigModal, props));

        const select = screen.getByRole("combobox") as HTMLSelectElement;
        const options = Array.from(select.options);

        // First option must correspond to the default model
        const firstOption = options[0];
        expect(firstOption.value).toBe(defaultModelId);

        // First option text must end with "(default)"
        expect(firstOption.textContent).toContain("(default)");

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 10.2, 10.3**
   *
   * Every option must display the family label in parentheses, matching
   * the format: "{model_id} ({family})" (plus optional " (default)").
   */
  it("all options show the family label in parentheses", () => {
    fc.assert(
      fc.property(modelsWithDefaultArb, ({ models, defaultModelId }) => {
        const props: AdvancedConfigModalProps = {
          isOpen: true,
          agentName: "Agent",
          agentRole: "Role",
          defaultModelId,
          availableModels: models,
          initialCustomPrompt: "",
          initialModelOverride: null,
          onSave: vi.fn(),
          onCancel: vi.fn(),
        };

        const { unmount } = render(createElement(AdvancedConfigModal, props));

        const select = screen.getByRole("combobox") as HTMLSelectElement;
        const options = Array.from(select.options);

        // Every model in the list must have a corresponding option with family
        for (const model of models) {
          const option = options.find((o) => o.value === model.model_id);
          expect(option).toBeDefined();

          // Option text must contain "({family})"
          const expectedFamilyLabel = `(${model.family})`;
          expect(option!.textContent).toContain(expectedFamilyLabel);

          // Option text must start with the model_id
          expect(option!.textContent).toContain(model.model_id);
        }

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 2.5, 10.4**
   *
   * The default model must be pre-selected in the dropdown when no
   * initialModelOverride is provided.
   */
  it("default model is pre-selected when no override is set", () => {
    fc.assert(
      fc.property(modelsWithDefaultArb, ({ models, defaultModelId }) => {
        const props: AdvancedConfigModalProps = {
          isOpen: true,
          agentName: "Agent",
          agentRole: "Role",
          defaultModelId,
          availableModels: models,
          initialCustomPrompt: "",
          initialModelOverride: null,
          onSave: vi.fn(),
          onCancel: vi.fn(),
        };

        const { unmount } = render(createElement(AdvancedConfigModal, props));

        const select = screen.getByRole("combobox") as HTMLSelectElement;

        // The selected value must be the default model
        expect(select.value).toBe(defaultModelId);

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 2.5**
   *
   * Only the default model option should have the "(default)" suffix.
   * Non-default models must NOT have it.
   */
  it("only the default model has the '(default)' suffix", () => {
    fc.assert(
      fc.property(modelsWithDefaultArb, ({ models, defaultModelId }) => {
        const props: AdvancedConfigModalProps = {
          isOpen: true,
          agentName: "Agent",
          agentRole: "Role",
          defaultModelId,
          availableModels: models,
          initialCustomPrompt: "",
          initialModelOverride: null,
          onSave: vi.fn(),
          onCancel: vi.fn(),
        };

        const { unmount } = render(createElement(AdvancedConfigModal, props));

        const select = screen.getByRole("combobox") as HTMLSelectElement;
        const options = Array.from(select.options);

        for (const option of options) {
          if (option.value === defaultModelId) {
            expect(option.textContent).toContain("(default)");
          } else {
            expect(option.textContent).not.toContain("(default)");
          }
        }

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});
