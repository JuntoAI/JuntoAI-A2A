import { describe, it, expect, beforeEach } from "vitest";
import * as fc from "fast-check";
import { render, within, fireEvent, cleanup } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { setDoc } from "firebase/firestore";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 1: Invalid email rejection
 *
 * For any string that is empty, contains only whitespace, or does not
 * conform to a standard email format (missing `@`, missing domain, etc.),
 * submitting it through the WaitlistForm SHALL be rejected with an inline
 * error message, and no Firestore write SHALL occur.
 *
 * **Validates: Requirements 3.2, 3.3**
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

// Mock waitlist module — joinWaitlist should never be called for invalid emails
const mockJoinWaitlist = vi.fn();
vi.mock("../../lib/waitlist", () => ({
  joinWaitlist: (...args: unknown[]) => mockJoinWaitlist(...args),
}));

// Mock tokens module
vi.mock("../../lib/tokens", () => ({
  needsReset: vi.fn(() => false),
  resetTokens: vi.fn(),
}));

import { SessionProvider } from "../../context/SessionContext";
import WaitlistForm from "../../components/WaitlistForm";
import { FC_NUM_RUNS } from "../fc-config";

/** The regex used by WaitlistForm for validation */
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function Wrapper({ children }: { children: ReactNode }) {
  return createElement(SessionProvider, null, children);
}

/**
 * Arbitrary that generates various categories of invalid email strings:
 * - Empty string
 * - Whitespace-only strings
 * - Strings missing '@'
 * - Strings with '@' but missing domain dot (e.g. "a@b")
 */
const invalidEmailArb = fc.oneof(
  // Empty string
  fc.constant(""),
  // Whitespace only
  fc.integer({ min: 1, max: 10 }).map((n) => " ".repeat(n)),
  // Missing @ entirely
  fc
    .string({ minLength: 1, maxLength: 20 })
    .filter((s) => !s.includes("@")),
  // Has @ but no dot in domain part (e.g. "a@b")
  fc
    .tuple(
      fc
        .integer({ min: 1, max: 8 })
        .chain((len) =>
          fc
            .array(fc.constantFrom("a", "b", "c", "1", "2"), {
              minLength: len,
              maxLength: len,
            })
            .map((arr) => arr.join("")),
        ),
      fc
        .integer({ min: 1, max: 8 })
        .chain((len) =>
          fc
            .array(fc.constantFrom("x", "y", "z", "1"), {
              minLength: len,
              maxLength: len,
            })
            .map((arr) => arr.join("")),
        ),
    )
    .map(([local, domain]) => `${local}@${domain}`)
    .filter((s) => !EMAIL_REGEX.test(s)),
);

describe("Property 1: Invalid email rejection", () => {
  beforeEach(() => {
    sessionStorage.clear();
    document.cookie = "junto_session=; max-age=0; path=/";
  });

  /**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any randomly generated invalid email string (empty, whitespace,
   * missing @, missing domain), submitting the form SHALL:
   * 1. Display the inline error "Please enter a valid email address."
   * 2. NOT call joinWaitlist (no Firestore write)
   * 3. NOT navigate away
   */
  it("rejects all invalid emails with inline error and no Firestore write", { timeout: 30_000 }, async () => {
    await fc.assert(
      fc.asyncProperty(invalidEmailArb, async (invalidEmail) => {
        // Clean slate for each iteration
        cleanup();
        mockJoinWaitlist.mockReset();
        mockPush.mockReset();
        vi.mocked(setDoc).mockReset();

        const { container } = render(createElement(WaitlistForm), {
          wrapper: Wrapper,
        });
        const view = within(container);

        // Find the email input
        const input = view.getByLabelText("Email address");

        // Set the invalid email value
        fireEvent.change(input, { target: { value: invalidEmail } });

        // Submit the form via the form element directly
        const form = container.querySelector("form")!;
        fireEvent.submit(form);

        // 1. Error message is displayed synchronously (validation is sync)
        const errorMsg = view.getByRole("alert");
        expect(errorMsg).toHaveTextContent(
          "Please enter a valid email address.",
        );

        // 2. joinWaitlist was NOT called — no Firestore write
        expect(mockJoinWaitlist).not.toHaveBeenCalled();

        // 3. setDoc was NOT called directly either
        expect(setDoc).not.toHaveBeenCalled();

        // 4. No navigation occurred
        expect(mockPush).not.toHaveBeenCalled();

        // Clean up DOM for next iteration
        cleanup();
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
