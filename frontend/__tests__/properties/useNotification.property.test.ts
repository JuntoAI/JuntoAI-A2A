import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fc from "fast-check";
import { FC_NUM_RUNS } from "../fc-config";
import { renderHook } from "@testing-library/react";
import { useNotification } from "@/hooks/useNotification";

/**
 * Feature: 290_negotiation-completion-notification, Property 1: Visibility gate
 * Feature: 290_negotiation-completion-notification, Property 3: Deduplication
 *
 * Property 1: For any terminal deal status and any finalSummary, when permission
 * is "granted", a browser notification is displayed if and only if
 * `document.hidden` is `true`.
 *
 * Property 3: For any session ID and any sequence of terminal state transitions,
 * the notification service SHALL construct at most one `Notification` instance
 * for that session ID.
 *
 * **Validates: Requirements 2.1, 2.2, 5.1, 5.2**
 */

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const terminalStatusArb = fc.constantFrom(
  "Agreed" as const,
  "Blocked" as const,
  "Failed" as const,
);

const finalSummaryArb = fc.dictionary(
  fc.string({ minLength: 1, maxLength: 20 }),
  fc.oneof(fc.string({ maxLength: 50 }), fc.integer(), fc.boolean()),
) as fc.Arbitrary<Record<string, unknown>>;

const sessionIdArb = fc.string({ minLength: 1, maxLength: 40 });

// ---------------------------------------------------------------------------
// Mock setup
// ---------------------------------------------------------------------------

let notificationInstances: Array<{ title: string; options: NotificationOptions; close: ReturnType<typeof vi.fn>; onclick: (() => void) | null }>;
let originalNotification: typeof globalThis.Notification;
let hiddenDescriptor: PropertyDescriptor | undefined;

beforeEach(() => {
  notificationInstances = [];

  // Save originals
  originalNotification = globalThis.Notification;
  hiddenDescriptor = Object.getOwnPropertyDescriptor(document, "hidden");

  // Mock Notification constructor
  const MockNotification = vi.fn().mockImplementation(function (
    this: { title: string; close: () => void; onclick: (() => void) | null },
    title: string,
    options: NotificationOptions,
  ) {
    const instance = {
      title,
      options,
      close: vi.fn(),
      onclick: null,
    };
    notificationInstances.push(instance);
    return instance;
  }) as unknown as typeof Notification;

  MockNotification.permission = "granted";
  MockNotification.requestPermission = vi.fn().mockResolvedValue("granted");

  Object.defineProperty(globalThis, "Notification", {
    value: MockNotification,
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  // Restore originals
  Object.defineProperty(globalThis, "Notification", {
    value: originalNotification,
    writable: true,
    configurable: true,
  });

  if (hiddenDescriptor) {
    Object.defineProperty(document, "hidden", hiddenDescriptor);
  } else {
    // Reset to jsdom default
    Object.defineProperty(document, "hidden", {
      value: true,
      writable: true,
      configurable: true,
    });
  }

  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setDocumentHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", {
    value: hidden,
    writable: true,
    configurable: true,
  });
}

// ---------------------------------------------------------------------------
// Property 1: Visibility gate
// ---------------------------------------------------------------------------

describe("Property 1: Visibility gate", () => {
  it("notification is constructed iff document.hidden is true (permission granted, terminal status)", () => {
    fc.assert(
      fc.property(
        terminalStatusArb,
        finalSummaryArb,
        fc.boolean(),
        (dealStatus, finalSummary, hidden) => {
          // Reset state between iterations
          notificationInstances = [];
          (Notification as unknown as ReturnType<typeof vi.fn>).mockClear();

          setDocumentHidden(hidden);

          const { unmount } = renderHook(() =>
            useNotification({
              sessionId: "prop1-session",
              dealStatus,
              finalSummary,
            }),
          );

          if (hidden) {
            expect(notificationInstances.length).toBe(1);
          } else {
            expect(notificationInstances.length).toBe(0);
          }

          unmount();
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 3: Deduplication — at most one notification per session
// ---------------------------------------------------------------------------

describe("Property 3: Deduplication — at most one notification per session", () => {
  it("at most one Notification is constructed for any sequence of terminal statuses with the same session ID", () => {
    fc.assert(
      fc.property(
        sessionIdArb,
        fc.array(terminalStatusArb, { minLength: 1, maxLength: 10 }),
        finalSummaryArb,
        (sessionId, statuses, finalSummary) => {
          // Reset state between iterations
          notificationInstances = [];
          (Notification as unknown as ReturnType<typeof vi.fn>).mockClear();

          setDocumentHidden(true);

          // Render with the first status, then rerender with each subsequent status
          const { rerender, unmount } = renderHook(
            ({ dealStatus }: { dealStatus: "Agreed" | "Blocked" | "Failed" }) =>
              useNotification({
                sessionId,
                dealStatus,
                finalSummary,
              }),
            { initialProps: { dealStatus: statuses[0] } },
          );

          for (let i = 1; i < statuses.length; i++) {
            rerender({ dealStatus: statuses[i] });
          }

          expect(notificationInstances.length).toBeLessThanOrEqual(1);

          unmount();
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
