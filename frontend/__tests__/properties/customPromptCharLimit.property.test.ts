import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { createElement } from "react";
import * as fc from "fast-check";
import { AdvancedConfigModal } from "@/components/arena/AdvancedConfigModal";
import type { AdvancedConfigModalProps } from "@/components/arena/AdvancedConfigModal";

/**
 * Feature: agent-advanced-config, Property 8: Custom prompt character limit enforcement in textarea
 *
 * For any input string, the custom prompt textarea should never contain more
 * than 500 characters. The displayed character counter should always equal the
 * current length of the textarea content. Pasting text that would exceed 500
 * characters should result in truncation to exactly 500 characters.
 *
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
 */

const MAX_PROMPT_LENGTH = 500;

const defaultProps: AdvancedConfigModalProps = {
  isOpen: true,
  agentName: "TestAgent",
  agentRole: "Tester",
  defaultModelId: "gemini-3-flash-preview",
  availableModels: [
    { model_id: "gemini-3-flash-preview", family: "gemini" },
    { model_id: "claude-3-5-sonnet", family: "claude" },
  ],
  initialCustomPrompt: "",
  initialModelOverride: null,
  onSave: vi.fn(),
  onCancel: vi.fn(),
};

describe("Property 8: Custom prompt character limit enforcement in textarea", () => {
  /**
   * **Validates: Requirements 3.1, 3.2, 3.3**
   *
   * For any random string typed into the textarea via onChange, the textarea
   * value must never exceed 500 characters and the counter must match.
   */
  it("textarea value never exceeds 500 chars after onChange and counter matches length", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 0, maxLength: 1200 }),
        (input) => {
          const { unmount } = render(
            createElement(AdvancedConfigModal, { ...defaultProps }),
          );

          const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;

          // Simulate typing by firing onChange with the generated string
          fireEvent.change(textarea, { target: { value: input } });

          // Textarea value must never exceed 500 chars
          expect(textarea.value.length).toBeLessThanOrEqual(MAX_PROMPT_LENGTH);

          // The expected length after truncation
          const expectedLength = Math.min(input.length, MAX_PROMPT_LENGTH);
          expect(textarea.value.length).toBe(expectedLength);

          // Character counter must match the actual textarea length
          const counterText = screen.getByText(
            `${textarea.value.length} / ${MAX_PROMPT_LENGTH}`,
          );
          expect(counterText).toBeInTheDocument();

          unmount();
        },
      ),
      { numRuns: 30 },
    );
  });

  /**
   * **Validates: Requirements 3.1, 3.4**
   *
   * Pasting text that exceeds 500 characters must result in truncation
   * to exactly 500 characters, and the counter must reflect the truncated length.
   */
  it("pasted text exceeding 500 chars is truncated and counter matches", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 501, maxLength: 1500 }),
        (pastedText) => {
          const { unmount } = render(
            createElement(AdvancedConfigModal, { ...defaultProps }),
          );

          const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;

          // Simulate paste event
          const clipboardData = {
            getData: () => pastedText,
          };
          fireEvent.paste(textarea, { clipboardData });

          // After paste, textarea must be truncated to exactly 500 chars
          expect(textarea.value.length).toBeLessThanOrEqual(MAX_PROMPT_LENGTH);
          expect(textarea.value).toBe(pastedText.slice(0, MAX_PROMPT_LENGTH));

          // Counter must match
          const counterText = screen.getByText(
            `${textarea.value.length} / ${MAX_PROMPT_LENGTH}`,
          );
          expect(counterText).toBeInTheDocument();

          unmount();
        },
      ),
      { numRuns: 30 },
    );
  });

  /**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For strings at or under the limit, the textarea must contain the
   * full input and the counter must match exactly.
   */
  it("strings within limit are preserved in full with matching counter", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 0, maxLength: MAX_PROMPT_LENGTH }),
        (input) => {
          const { unmount } = render(
            createElement(AdvancedConfigModal, { ...defaultProps }),
          );

          const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;

          fireEvent.change(textarea, { target: { value: input } });

          // Value should be preserved exactly
          expect(textarea.value).toBe(input);
          expect(textarea.value.length).toBe(input.length);

          // Counter must match
          const counterText = screen.getByText(
            `${input.length} / ${MAX_PROMPT_LENGTH}`,
          );
          expect(counterText).toBeInTheDocument();

          unmount();
        },
      ),
      { numRuns: 30 },
    );
  });
});
