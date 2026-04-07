import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { createElement } from "react";
import * as fc from "fast-check";
import { AdvancedConfigModal } from "@/components/arena/AdvancedConfigModal";
import type { AdvancedConfigModalProps } from "@/components/arena/AdvancedConfigModal";
import type { ModelInfo } from "@/lib/api";
import { FC_NUM_RUNS } from "../fc-config";

/**
 * Feature: agent-advanced-config, Property 13: Config save-and-reload round-trip
 *
 * For any agent role, custom prompt string (≤500 chars), and model override
 * selection, saving the configuration and re-opening the modal should
 * pre-populate the textarea with the saved custom prompt and pre-select the
 * saved model override in the dropdown.
 *
 * **Validates: Requirements 4.3, 4.4, 4.6, 4.7**
 */

const MAX_PROMPT_LENGTH = 500;

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
 * Generate a list of unique models (≥2), a default model from that list,
 * a custom prompt (≤500 chars), and a selected model index for the override.
 */
const roundTripArb = fc
  .array(modelInfoArb, { minLength: 2, maxLength: 8 })
  .chain((rawModels) => {
    const seen = new Set<string>();
    const models: ModelInfo[] = [];
    for (const m of rawModels) {
      if (!seen.has(m.model_id)) {
        seen.add(m.model_id);
        models.push(m);
      }
    }
    // Need at least 2 unique models to test override vs default
    if (models.length < 2) {
      models.push({ model_id: "fallback-model1", family: "fallback" });
    }

    return fc.record({
      models: fc.constant(models),
      defaultIdx: fc.integer({ min: 0, max: models.length - 1 }),
      selectedIdx: fc.integer({ min: 0, max: models.length - 1 }),
      customPrompt: fc.string({ minLength: 0, maxLength: MAX_PROMPT_LENGTH }),
    });
  })
  .map(({ models, defaultIdx, selectedIdx, customPrompt }) => ({
    models,
    defaultModelId: models[defaultIdx].model_id,
    selectedModelId: models[selectedIdx].model_id,
    customPrompt,
  }));

describe("Property 13: Config save-and-reload round-trip", () => {
  /**
   * **Validates: Requirements 4.3, 4.4, 4.6, 4.7**
   *
   * 1. Render modal with empty initial values
   * 2. Set custom prompt and model selection
   * 3. Click Save → capture saved values via onSave callback
   * 4. Re-render modal with saved values as initial values
   * 5. Assert textarea contains the saved custom prompt
   * 6. Assert model selector shows the saved model override
   */
  it("saved config values are correctly pre-populated when modal re-opens", { timeout: 30_000 }, () => {
    fc.assert(
      fc.property(
        roundTripArb,
        ({ models, defaultModelId, selectedModelId, customPrompt }) => {
          // --- Phase 1: Render, configure, and save ---
          let savedPrompt: string | undefined;
          let savedModelOverride: string | null | undefined;

          const onSave = vi.fn(
            (prompt: string, modelOverride: string | null) => {
              savedPrompt = prompt;
              savedModelOverride = modelOverride;
            },
          );

          const initialProps: AdvancedConfigModalProps = {
            isOpen: true,
            agentName: "Agent",
            agentRole: "Role",
            defaultModelId,
            availableModels: models,
            initialCustomPrompt: "",
            initialModelOverride: null,
            onSave,
            onCancel: vi.fn(),
          };

          const { unmount: unmount1 } = render(
            createElement(AdvancedConfigModal, initialProps),
          );

          // Set custom prompt
          const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
          fireEvent.change(textarea, { target: { value: customPrompt } });

          // Set model selection
          const select = screen.getByRole("combobox") as HTMLSelectElement;
          fireEvent.change(select, { target: { value: selectedModelId } });

          // Click Save
          const saveButton = screen.getByRole("button", { name: /save/i });
          fireEvent.click(saveButton);

          expect(onSave).toHaveBeenCalledOnce();
          unmount1();

          // --- Phase 2: Re-render with saved values, assert pre-population ---
          const expectedModelOverride =
            selectedModelId === defaultModelId ? null : selectedModelId;
          expect(savedModelOverride).toBe(expectedModelOverride);

          const reloadProps: AdvancedConfigModalProps = {
            isOpen: true,
            agentName: "Agent",
            agentRole: "Role",
            defaultModelId,
            availableModels: models,
            initialCustomPrompt: savedPrompt!,
            initialModelOverride: savedModelOverride!,
            onSave: vi.fn(),
            onCancel: vi.fn(),
          };

          const { unmount: unmount2 } = render(
            createElement(AdvancedConfigModal, reloadProps),
          );

          // Assert textarea is pre-populated with saved prompt
          const reloadedTextarea = screen.getByRole(
            "textbox",
          ) as HTMLTextAreaElement;
          expect(reloadedTextarea.value).toBe(savedPrompt);

          // Assert model selector shows the saved selection
          const reloadedSelect = screen.getByRole(
            "combobox",
          ) as HTMLSelectElement;
          // When override is null, the component defaults to defaultModelId
          const expectedSelectedValue =
            savedModelOverride ?? defaultModelId;
          expect(reloadedSelect.value).toBe(expectedSelectedValue);

          unmount2();
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
