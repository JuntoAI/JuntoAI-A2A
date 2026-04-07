import { describe, it, expect, afterEach } from "vitest";
import * as fc from "fast-check";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 9: UTC date consistency
 *
 * For any JavaScript Date object, getUtcDateString() returns a string
 * in YYYY-MM-DD format representing the UTC date, regardless of the
 * local timezone offset.
 *
 * Validates: Requirements 6.4
 */

// Mock firebase to avoid env var validation on import
vi.mock("../../lib/firebase", () => ({
  db: { type: "firestore", app: { name: "[DEFAULT]" } },
}));

import { getUtcDateString } from "../../lib/tokens";
import { FC_NUM_RUNS } from "../fc-config";

describe("Property 9: UTC date consistency", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  /**
   * **Validates: Requirements 6.4**
   *
   * For any random Date in [2020-01-01, 2030-12-31], pinning system time
   * to that date and calling getUtcDateString() always returns a string
   * matching YYYY-MM-DD format whose components equal the UTC year, month,
   * and day of the generated date.
   */
  it("always returns UTC YYYY-MM-DD for any date", () => {
    const dateArb = fc.date({
      min: new Date("2020-01-01"),
      max: new Date("2030-12-31"),
      noInvalidDate: true,
    });

    fc.assert(
      fc.property(dateArb, (date) => {
        vi.useFakeTimers();
        vi.setSystemTime(date);

        const result = getUtcDateString();

        vi.useRealTimers();

        // Must match YYYY-MM-DD format
        expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);

        // Components must match UTC values of the generated date
        const expectedYear = date.getUTCFullYear();
        const expectedMonth = String(date.getUTCMonth() + 1).padStart(2, "0");
        const expectedDay = String(date.getUTCDate()).padStart(2, "0");
        const expected = `${expectedYear}-${expectedMonth}-${expectedDay}`;

        expect(result).toBe(expected);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
