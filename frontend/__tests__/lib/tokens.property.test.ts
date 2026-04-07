// Feature: user-profile-token-upgrade, Property 13: Token display format
import { describe, it, expect } from "vitest";
import * as fc from "fast-check";

vi.mock("../../lib/firebase", () => ({
  getDb: vi.fn(() => ({ type: "firestore", app: { name: "[DEFAULT]" } })),
}));

import { formatTokenDisplay } from "../../lib/tokens";
import { FC_NUM_RUNS } from "../fc-config";

describe("Property 13: Token display format", () => {
  /**
   * **Validates: Requirements 8.1, 8.2, 8.3**
   *
   * For any token balance and daily limit pair, formatTokenDisplay
   * returns "Tokens: {clamped_balance} / {dailyLimit}" where
   * clamped_balance = max(0, balance).
   */
  it("returns 'Tokens: {clamped_balance} / {dailyLimit}' for any balance/limit pair", () => {
    const balanceArb = fc.integer({ min: -200, max: 500 });
    const dailyLimitArb = fc.integer({ min: 1, max: 1000 });

    fc.assert(
      fc.property(balanceArb, dailyLimitArb, (balance, dailyLimit) => {
        const result = formatTokenDisplay(balance, dailyLimit);
        const clampedBalance = Math.max(0, balance);

        expect(result).toBe(`Tokens: ${clampedBalance} / ${dailyLimit}`);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
