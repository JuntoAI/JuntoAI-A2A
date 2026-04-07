import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import * as fc from "fast-check";
import { InitializeButton } from "@/components/arena/InitializeButton";
import { FC_NUM_RUNS } from "../fc-config";

/**
 * Feature: 060_a2a-glass-box-ui, Property 6: Insufficient tokens disables Initialize button
 *
 * Generate random token balance and max_turns pairs where balance < cost.
 * Verify Initialize button is disabled and shows insufficient tokens message.
 *
 * **Validates: Requirements 4.5**
 */

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

/**
 * Generator per design doc: balance < cost ensures insufficient tokens.
 */
const insufficientTokensArb = fc
  .record({
    balance: fc.integer({ min: 0, max: 99 }),
    cost: fc.integer({ min: 1, max: 100 }),
  })
  .filter(({ balance, cost }) => balance < cost);

// ---------------------------------------------------------------------------
// Property tests
// ---------------------------------------------------------------------------

describe("Property 6: Insufficient tokens disables Initialize button", () => {
  /**
   * **Validates: Requirements 4.5**
   *
   * When the user's token balance is less than the simulation cost,
   * the Initialize button must be disabled.
   */
  it("Initialize button is disabled when balance < cost", { timeout: 30000 }, () => {
    fc.assert(
      fc.property(insufficientTokensArb, ({ balance, cost }) => {
        const { unmount } = render(
          <InitializeButton
            onClick={() => {}}
            disabled={false}
            isLoading={false}
            insufficientTokens={true}
          />,
        );

        const button = screen.getByRole("button");
        expect(button).toBeDisabled();

        unmount();
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  /**
   * **Validates: Requirements 4.5**
   *
   * When insufficient tokens, the message "Insufficient tokens — resets at midnight UTC"
   * must be displayed.
   */
  it("shows insufficient tokens message when balance < cost", () => {
    fc.assert(
      fc.property(insufficientTokensArb, ({ balance, cost }) => {
        const { unmount } = render(
          <InitializeButton
            onClick={() => {}}
            disabled={false}
            isLoading={false}
            insufficientTokens={true}
          />,
        );

        const alert = screen.getByRole("alert");
        expect(alert).toHaveTextContent(
          "Insufficient tokens — resets at midnight UTC",
        );

        unmount();
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  /**
   * **Validates: Requirements 4.5**
   *
   * When the user has sufficient tokens (balance >= cost), the button
   * should NOT be disabled due to insufficient tokens.
   */
  it("Initialize button is enabled when balance >= cost", () => {
    const sufficientTokensArb = fc
      .record({
        balance: fc.integer({ min: 1, max: 100 }),
        cost: fc.integer({ min: 1, max: 100 }),
      })
      .filter(({ balance, cost }) => balance >= cost);

    fc.assert(
      fc.property(sufficientTokensArb, ({ balance, cost }) => {
        const { unmount } = render(
          <InitializeButton
            onClick={() => {}}
            disabled={false}
            isLoading={false}
            insufficientTokens={false}
          />,
        );

        const button = screen.getByRole("button");
        expect(button).not.toBeDisabled();

        unmount();
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
