import { describe, it, expect } from "vitest";
import * as fc from "fast-check";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 10: Token balance display formatting
 *
 * For any integer token balance value (including negative values),
 * formatTokenDisplay returns "Tokens: X / 100" where X = max(0, balance),
 * ensuring the displayed value is never below zero.
 *
 * Validates: Requirements 7.1, 7.4
 */

// Mock firebase to avoid env var validation on import
vi.mock("../../lib/firebase", () => ({
  db: { type: "firestore", app: { name: "[DEFAULT]" } },
}));

import { formatTokenDisplay } from "../../lib/tokens";

describe("Property 10: Token balance display formatting", () => {
  /**
   * **Validates: Requirements 7.1, 7.4**
   *
   * For any random integer in [-100, 200], formatTokenDisplay(balance)
   * returns "Tokens: X / 100" where X equals Math.max(0, balance)
   * and X is never negative.
   */
  it("returns 'Tokens: X / 100' where X = max(0, balance) for any integer", () => {
    const balanceArb = fc.integer({ min: -100, max: 200 });

    fc.assert(
      fc.property(balanceArb, (balance) => {
        const result = formatTokenDisplay(balance);
        const expected = Math.max(0, balance);

        // Result matches exact expected format
        expect(result).toBe(`Tokens: ${expected} / 100`);

        // Displayed value is never negative
        const match = result.match(/^Tokens: (\d+) \/ 100$/);
        expect(match).not.toBeNull();
        expect(Number(match![1])).toBeGreaterThanOrEqual(0);
      }),
      { numRuns: 200 },
    );
  });
});
