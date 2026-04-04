import { describe, it, expect, beforeEach } from "vitest";
import * as fc from "fast-check";
import { renderHook, act, render, screen } from "@testing-library/react";
import { createElement, type ReactNode } from "react";

// Force cloud mode so SessionContext uses sessionStorage-based auth
vi.mock("../../lib/runMode", () => ({ isLocalMode: false }));

import { SessionProvider, useSession } from "../../context/SessionContext";
import { handleNegotiationResponse } from "../../lib/negotiation";

// Mock firebase to avoid env var validation on import
vi.mock("../../lib/firebase", () => ({
  db: { type: "firestore", app: { name: "[DEFAULT]" } },
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/arena",
  useSearchParams: () => new URLSearchParams(),
}));

import StartNegotiationButton from "../../components/StartNegotiationButton";

function wrapper({ children }: { children: ReactNode }) {
  return createElement(SessionProvider, null, children);
}

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 11: Token balance sync from backend
 *
 * For any `tokens_remaining` value returned by the backend
 * POST /api/v1/negotiation/start response, the client-side
 * Token_Balance SHALL be updated to exactly match that value.
 *
 * **Validates: Requirements 7.2**
 */
describe("Property 11: Token balance sync from backend", () => {
  beforeEach(() => {
    sessionStorage.clear();
    document.cookie = "junto_session=; max-age=0; path=/";
  });

  it("client token balance matches tokens_remaining from backend exactly", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 100 }), (tokensRemaining) => {
        sessionStorage.clear();
        document.cookie = "junto_session=; max-age=0; path=/";

        const { result } = renderHook(() => useSession(), { wrapper });

        // Login first to establish an authenticated session
        act(() => {
          result.current.login("test@example.com", 100, "2025-01-01");
        });

        // Simulate backend response via handleNegotiationResponse
        act(() => {
          handleNegotiationResponse(tokensRemaining, result.current.updateTokenBalance);
        });

        // Client state must match the backend value exactly
        expect(result.current.tokenBalance).toBe(tokensRemaining);

        // sessionStorage must also reflect the synced value
        expect(sessionStorage.getItem("junto_token_balance")).toBe(
          String(tokensRemaining),
        );
      }),
      { numRuns: 100 },
    );
  });
});

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 12: Insufficient tokens disables action
 *
 * For any client-side Token_Balance that is less than the expected
 * token cost for an action, the action trigger SHALL be disabled
 * and a message indicating insufficient tokens and the reset time
 * SHALL be displayed.
 *
 * **Validates: Requirements 7.3**
 */
describe("Property 12: Insufficient tokens disables action", () => {
  beforeEach(() => {
    sessionStorage.clear();
    document.cookie = "junto_session=; max-age=0; path=/";
  });

  it("button is disabled and message shown when balance < cost", { timeout: 30000 }, () => {
    fc.assert(
      fc.property(
        fc
          .record({
            balance: fc.integer({ min: 0, max: 99 }),
            cost: fc.integer({ min: 1, max: 100 }),
          })
          .filter(({ balance, cost }) => balance < cost),
        ({ balance, cost }) => {
          sessionStorage.clear();
          document.cookie = "junto_session=; max-age=0; path=/";

          // Pre-set session so the provider picks up the balance
          sessionStorage.setItem("junto_email", "test@example.com");
          sessionStorage.setItem("junto_token_balance", String(balance));
          sessionStorage.setItem("junto_last_reset", "2025-01-01");
          document.cookie = "junto_session=1; SameSite=Strict; path=/";

          const { unmount } = render(
            createElement(
              SessionProvider,
              null,
              createElement(StartNegotiationButton, { cost }),
            ),
          );

          // Button must be disabled
          const button = screen.getByRole("button", {
            name: /initialize a2a protocol/i,
          });
          expect(button).toBeDisabled();

          // Insufficient tokens message must be displayed
          expect(
            screen.getByText("No tokens remaining. Resets at midnight UTC."),
          ).toBeInTheDocument();

          unmount();
        },
      ),
      { numRuns: 100 },
    );
  });
});
