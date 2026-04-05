import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fc from "fast-check";
import { getDoc, setDoc } from "firebase/firestore";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 2: New waitlist document structure
 *
 * For any valid email address, when a new Waitlist_Document is created,
 * the document SHALL have: `email` equal to the input normalized to
 * lowercase, `token_balance` equal to 20 (Tier 1 default), and `last_reset_date` equal
 * to the current UTC date in YYYY-MM-DD format.
 *
 * Validates: Requirements 3.4, 5.1, 5.2, 6.1
 */

// Mock firebase to avoid env var validation on import
vi.mock("../../lib/firebase", () => ({
  getDb: vi.fn(() => ({ type: "firestore", app: { name: "[DEFAULT]" } })),
}));

import { joinWaitlist } from "../../lib/waitlist";

describe("Property 2: New waitlist document structure", () => {
  const FIXED_DATE = new Date("2025-06-15T14:30:00.000Z");
  const EXPECTED_DATE_STR = "2025-06-15";

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(FIXED_DATE);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.mocked(getDoc).mockReset();
    vi.mocked(setDoc).mockReset();
  });

  /**
   * **Validates: Requirements 3.4, 5.1, 5.2**
   *
   * For any random valid email, calling joinWaitlist produces a document
   * with email normalized to lowercase, token_balance === 20 (Tier 1), and
   * last_reset_date matching today's UTC date string.
   */
  it("creates document with correct email, token_balance, and last_reset_date for any valid email", async () => {
    await fc.assert(
      fc.asyncProperty(fc.emailAddress(), async (email) => {
        // Fresh mock state for each iteration
        vi.mocked(getDoc).mockResolvedValue({
          exists: () => false,
          data: () => undefined,
        } as any);
        vi.mocked(setDoc).mockResolvedValue(undefined);

        const result = await joinWaitlist(email);
        const normalizedEmail = email.toLowerCase().trim();

        // 1. email is normalized to lowercase
        expect(result.email).toBe(normalizedEmail);

        // 2. token_balance is exactly 20 (Tier 1 default)
        expect(result.token_balance).toBe(20);

        // 3. last_reset_date matches today's UTC date
        expect(result.last_reset_date).toBe(EXPECTED_DATE_STR);

        // 4. setDoc was called with the correct document data
        expect(setDoc).toHaveBeenCalledTimes(1);
        const writtenDoc = vi.mocked(setDoc).mock.calls[0][1];
        expect(writtenDoc).toMatchObject({
          email: normalizedEmail,
          token_balance: 20,
          last_reset_date: EXPECTED_DATE_STR,
        });

        // Clean up for next iteration
        vi.mocked(getDoc).mockReset();
        vi.mocked(setDoc).mockReset();
      }),
      { numRuns: 100 },
    );
  });
});
