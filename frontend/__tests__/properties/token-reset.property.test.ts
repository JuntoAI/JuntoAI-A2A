import { describe, it, expect, afterEach, beforeEach } from "vitest";
import * as fc from "fast-check";
import { updateDoc, doc } from "firebase/firestore";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 8: Token daily reset logic
 *
 * For any Waitlist_Document where `last_reset_date` is earlier than the
 * current UTC date, authenticating SHALL update `token_balance` to `100`
 * and `last_reset_date` to the current UTC date string, and persist both
 * to Firestore. For any Waitlist_Document where `last_reset_date` equals
 * the current UTC date, authenticating SHALL leave `token_balance` unchanged.
 *
 * **Validates: Requirements 6.1, 6.2, 6.3**
 */

// Mock firebase to avoid env var validation on import
vi.mock("../../lib/firebase", () => ({
  db: { type: "firestore", app: { name: "[DEFAULT]" } },
}));

import { needsReset, resetTokens, getUtcDateString } from "../../lib/tokens";

/** Helper: format a Date as "YYYY-MM-DD" in UTC. */
function toUtcDateString(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Arbitrary for a random date in a reasonable range (filter out invalid dates). */
const dateArb = fc
  .date({ min: new Date("2020-01-01"), max: new Date("2030-12-31") })
  .filter((d) => !isNaN(d.getTime()));

/** Arbitrary for a valid YYYY-MM-DD date string. */
const dateStringArb = fc
  .record({
    year: fc.integer({ min: 2020, max: 2030 }),
    month: fc.integer({ min: 1, max: 12 }),
    day: fc.integer({ min: 1, max: 28 }),
  })
  .map(
    ({ year, month, day }) =>
      `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
  );

describe("Property 8: Token daily reset logic", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.mocked(updateDoc).mockReset();
    vi.mocked(doc).mockReset();
  });

  /**
   * **Validates: Requirements 6.1, 6.2**
   *
   * needsReset returns true when lastResetDate < today UTC,
   * and false when lastResetDate >= today UTC.
   */
  it("needsReset returns true iff lastResetDate < today UTC", { timeout: 30_000 }, () => {
    fc.assert(
      fc.property(dateArb, dateStringArb, (systemDate, lastResetDate) => {
        vi.setSystemTime(systemDate);
        const todayUtc = toUtcDateString(systemDate);

        const result = needsReset(lastResetDate);

        if (lastResetDate < todayUtc) {
          expect(result).toBe(true);
        } else {
          expect(result).toBe(false);
        }
      }),
      { numRuns: 200 },
    );
  });

  /**
   * **Validates: Requirements 6.1, 6.3**
   *
   * resetTokens calls updateDoc with token_balance: 100 and
   * last_reset_date set to the current UTC date string.
   */
  it("resetTokens persists token_balance=100 and last_reset_date=todayUTC to Firestore", { timeout: 30_000 }, async () => {
    await fc.assert(
      fc.asyncProperty(
        dateArb,
        fc.emailAddress().map((e) => e.toLowerCase()),
        async (systemDate, email) => {
          vi.setSystemTime(systemDate);
          vi.mocked(updateDoc).mockResolvedValue(undefined);
          vi.mocked(doc).mockReturnValue({ id: email } as any);

          await resetTokens(email);

          const todayUtc = toUtcDateString(systemDate);

          // updateDoc was called exactly once
          expect(updateDoc).toHaveBeenCalledTimes(1);

          // Verify the payload matches the expected reset values
          expect(updateDoc).toHaveBeenCalledWith(
            expect.anything(),
            {
              token_balance: 100,
              last_reset_date: todayUtc,
            },
          );

          // Clean up for next iteration
          vi.mocked(updateDoc).mockReset();
          vi.mocked(doc).mockReset();
        },
      ),
      { numRuns: 100 },
    );
  });
});
