import { describe, it, expect, beforeEach } from "vitest";
import * as fc from "fast-check";
import { render, within, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 5: Error display on Firestore failure
 *
 * For any Firestore operation failure (network error, permission denied,
 * service unavailable), the WaitlistForm SHALL display a user-facing error
 * message and SHALL NOT set session state or navigate away from the landing page.
 *
 * **Validates: Requirements 3.7**
 */

// Mock firebase to avoid env var validation on import
vi.mock("../../lib/firebase", () => ({
  db: { type: "firestore", app: { name: "[DEFAULT]" } },
}));

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

// Mock waitlist module — joinWaitlist will reject with various error types
const mockJoinWaitlist = vi.fn();
vi.mock("../../lib/waitlist", () => ({
  joinWaitlist: (...args: unknown[]) => mockJoinWaitlist(...args),
}));

// Mock tokens module
vi.mock("../../lib/tokens", () => ({
  needsReset: vi.fn(() => false),
  resetTokens: vi.fn(),
}));

// Mock auth module — checkEmail returns no password by default
vi.mock("../../lib/auth", () => ({
  checkEmail: vi.fn(() => Promise.resolve({ has_password: false })),
  loginWithPassword: vi.fn(),
  loginWithGoogle: vi.fn(),
}));

// Mock profile module
vi.mock("../../lib/profile", () => ({
  getProfile: vi.fn(() => Promise.resolve({ tier: 1, daily_limit: 20 })),
}));

import { SessionProvider } from "../../context/SessionContext";
import WaitlistForm from "../../components/WaitlistForm";
import { FC_NUM_RUNS } from "../fc-config";

function Wrapper({ children }: { children: ReactNode }) {
  return createElement(SessionProvider, null, children);
}

/**
 * Arbitrary that generates Firestore error types:
 * - network: network connectivity failure
 * - permission-denied: Firestore security rules rejection
 * - unavailable: Firestore service unavailable
 * - unknown: unexpected/unclassified error
 */
const firestoreErrorTypeArb = fc.oneof(
  fc.constant("network"),
  fc.constant("permission-denied"),
  fc.constant("unavailable"),
  fc.constant("unknown"),
);

describe("Property 5: Error display on Firestore failure", () => {
  beforeEach(() => {
    sessionStorage.clear();
    document.cookie = "junto_session=; max-age=0; path=/";
  });

  /**
   * **Validates: Requirements 3.7**
   *
   * For any randomly generated Firestore error type, submitting a valid
   * email when joinWaitlist rejects SHALL:
   * 1. Display the error message "Something went wrong. Please try again."
   * 2. NOT navigate away (mockPush not called)
   * 3. NOT set session state (sessionStorage remains empty)
   */
  it(
    "displays error message on Firestore failure and does not navigate or set session",
    { timeout: 30_000 },
    async () => {
      await fc.assert(
        fc.asyncProperty(firestoreErrorTypeArb, async (errorType) => {
          // Clean slate for each iteration
          cleanup();
          mockJoinWaitlist.mockReset();
          mockPush.mockReset();

          // Configure joinWaitlist to reject with the generated error type
          mockJoinWaitlist.mockRejectedValue(
            new Error(`Firestore error: ${errorType}`),
          );

          const { container } = render(createElement(WaitlistForm), {
            wrapper: Wrapper,
          });
          const view = within(container);

          // Enter a valid email
          const input = view.getByLabelText("Email address");
          fireEvent.change(input, { target: { value: "test@example.com" } });

          // Submit the form
          const form = container.querySelector("form")!;
          fireEvent.submit(form);

          // Wait for the async error to appear (joinWaitlist is called after checkEmail resolves)
          await waitFor(() => {
            expect(mockJoinWaitlist).toHaveBeenCalledWith("test@example.com");
            const errorMsg = view.getByRole("alert");
            expect(errorMsg).toHaveTextContent(
              "Something went wrong. Please try again.",
            );
          });

          // No navigation occurred
          expect(mockPush).not.toHaveBeenCalled();

          // Session state was not set (sessionStorage should be empty)
          expect(sessionStorage.getItem("junto_email")).toBeNull();
          expect(sessionStorage.getItem("junto_token_balance")).toBeNull();
          expect(sessionStorage.getItem("junto_last_reset")).toBeNull();

          // Clean up DOM for next iteration
          cleanup();
        }),
        { numRuns: FC_NUM_RUNS },
      );
    },
  );
});
