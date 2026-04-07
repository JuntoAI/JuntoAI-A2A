import { describe, it, expect, afterEach } from "vitest";
import * as fc from "fast-check";
import { getDoc, setDoc } from "firebase/firestore";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 3: Idempotent re-submission
 *
 * For any email that already has a Waitlist_Document in Firestore,
 * re-submitting that email through joinWaitlist SHALL not overwrite
 * or modify the existing document's signed_up_at, token_balance,
 * or last_reset_date fields.
 *
 * **Validates: Requirements 3.5**
 */

// Mock firebase to avoid env var validation on import
vi.mock("../../lib/firebase", () => ({
  getDb: vi.fn(() => ({ type: "firestore", app: { name: "[DEFAULT]" } })),
}));

import { joinWaitlist, type WaitlistDocument } from "../../lib/waitlist";
import { FC_NUM_RUNS } from "../fc-config";

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

/** Arbitrary for an existing WaitlistDocument with random token_balance and last_reset_date. */
const existingDocArb = fc
  .record({
    email: fc.emailAddress(),
    token_balance: fc.integer({ min: 0, max: 100 }),
    last_reset_date: dateStringArb,
  })
  .map((fields) => ({
    email: fields.email.toLowerCase().trim(),
    signed_up_at: { seconds: Date.now() / 1000, nanoseconds: 0 },
    token_balance: fields.token_balance,
    last_reset_date: fields.last_reset_date,
  }));

describe("Property 3: Idempotent re-submission", () => {
  afterEach(() => {
    vi.mocked(getDoc).mockReset();
    vi.mocked(setDoc).mockReset();
  });

  /**
   * **Validates: Requirements 3.5**
   *
   * For any existing WaitlistDocument with random token_balance (0-100)
   * and random last_reset_date, re-submitting the same email returns
   * the original document unchanged and does NOT call setDoc.
   */
  it("preserves existing document fields and skips Firestore write on re-submission", async () => {
    await fc.assert(
      fc.asyncProperty(existingDocArb, async (existingDoc) => {
        // Mock getDoc to return the existing document
        vi.mocked(getDoc).mockResolvedValue({
          exists: () => true,
          data: () => existingDoc,
        } as any);
        vi.mocked(setDoc).mockResolvedValue(undefined);

        const result = await joinWaitlist(existingDoc.email);

        // 1. Returned document matches the existing document exactly
        expect(result).toEqual(existingDoc);

        // 2. setDoc was NOT called — no write to Firestore
        expect(setDoc).not.toHaveBeenCalled();

        // 3. token_balance preserved from existing doc
        expect(result.token_balance).toBe(existingDoc.token_balance);

        // 4. last_reset_date preserved from existing doc
        expect(result.last_reset_date).toBe(existingDoc.last_reset_date);

        // Clean up for next iteration
        vi.mocked(getDoc).mockReset();
        vi.mocked(setDoc).mockReset();
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
