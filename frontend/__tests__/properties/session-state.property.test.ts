import { describe, it, expect, beforeEach } from "vitest";
import * as fc from "fast-check";
import { renderHook, act } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { SessionProvider, useSession } from "../../context/SessionContext";
import { FC_NUM_RUNS } from "../fc-config";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 4: Session state loaded on auth
 *
 * For any successful waitlist submission (new or returning user),
 * the client-side session state SHALL contain the authenticated email
 * and the token_balance and last_reset_date values from the Firestore
 * Waitlist_Document.
 *
 * **Validates: Requirements 3.6, 5.4**
 */

function wrapper({ children }: { children: ReactNode }) {
  return createElement(SessionProvider, null, children);
}

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

/** Arbitrary for random session data simulating Firestore state. */
const sessionDataArb = fc.record({
  email: fc.emailAddress(),
  tokenBalance: fc.integer({ min: 0, max: 100 }),
  lastResetDate: dateStringArb,
});

describe("Property 4: Session state loaded on auth", () => {
  beforeEach(() => {
    sessionStorage.clear();
    document.cookie = "junto_session=; max-age=0; path=/";
  });

  /**
   * **Validates: Requirements 3.6, 5.4**
   *
   * For any random valid email with random Firestore state (token_balance 0-100,
   * valid YYYY-MM-DD last_reset_date), after calling login() the session state
   * SHALL match the provided values exactly and isAuthenticated SHALL be true.
   */
  it("session state matches Firestore values after login", async () => {
    await fc.assert(
      fc.asyncProperty(sessionDataArb, async ({ email, tokenBalance, lastResetDate }) => {
        // Clear state between iterations
        sessionStorage.clear();
        document.cookie = "junto_session=; max-age=0; path=/";

        const { result } = renderHook(() => useSession(), { wrapper });

        // Simulate auth: call login with Firestore document values
        act(() => {
          result.current.login(email, tokenBalance, lastResetDate);
        });

        // 1. Session email matches the authenticated email
        expect(result.current.email).toBe(email);

        // 2. Session tokenBalance matches Firestore token_balance
        expect(result.current.tokenBalance).toBe(tokenBalance);

        // 3. Session lastResetDate matches Firestore last_reset_date
        expect(result.current.lastResetDate).toBe(lastResetDate);

        // 4. isAuthenticated is true after login
        expect(result.current.isAuthenticated).toBe(true);

        // 5. sessionStorage contains the correct persisted values
        expect(sessionStorage.getItem("junto_email")).toBe(email);
        expect(sessionStorage.getItem("junto_token_balance")).toBe(String(tokenBalance));
        expect(sessionStorage.getItem("junto_last_reset")).toBe(lastResetDate);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
