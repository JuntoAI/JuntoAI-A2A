import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { FC_NUM_RUNS } from "../fc-config";
import { buildNotificationContent } from "@/lib/notificationContent";

/**
 * Feature: 290_negotiation-completion-notification, Property 2: Status-specific content mapping
 *
 * For any terminal deal status and any finalSummary containing the corresponding
 * field (`current_offer` for Agreed, `blocked_by` for Blocked, `reason` for Failed),
 * `buildNotificationContent` SHALL return a title matching the status label and a
 * body containing the field value.
 *
 * **Validates: Requirements 2.3, 2.4, 2.5, 2.6, 2.7**
 */

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const terminalStatusArb = fc.constantFrom(
  "Agreed" as const,
  "Blocked" as const,
  "Failed" as const,
);

const TITLE_MAP: Record<string, string> = {
  Agreed: "Deal Agreed",
  Blocked: "Deal Blocked",
  Failed: "Negotiation Failed",
};

const FALLBACK_BODY: Record<string, string> = {
  Agreed: "Your negotiation reached an agreement.",
  Blocked: "Your negotiation was blocked.",
  Failed: "Negotiation ended without agreement.",
};

/** Non-null, non-undefined string value for summary fields */
const fieldValueArb = fc.string({ minLength: 1, maxLength: 100 });

// ---------------------------------------------------------------------------
// Property tests
// ---------------------------------------------------------------------------

describe("Property 2: Status-specific content mapping", () => {
  it("title matches the status label for any terminal status", () => {
    fc.assert(
      fc.property(terminalStatusArb, (status) => {
        const result = buildNotificationContent(status, {});
        expect(result.title).toBe(TITLE_MAP[status]);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("body contains current_offer value when Agreed and field is present", () => {
    fc.assert(
      fc.property(fieldValueArb, (offer) => {
        const result = buildNotificationContent("Agreed", { current_offer: offer });
        expect(result.body).toContain(offer);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("body contains blocked_by value when Blocked and field is present", () => {
    fc.assert(
      fc.property(fieldValueArb, (blockedBy) => {
        const result = buildNotificationContent("Blocked", { blocked_by: blockedBy });
        expect(result.body).toContain(blockedBy);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("body contains reason value when Failed and field is present", () => {
    fc.assert(
      fc.property(fieldValueArb, (reason) => {
        const result = buildNotificationContent("Failed", { reason });
        expect(result.body).toContain(reason);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("body falls back to default when the corresponding field is missing", () => {
    fc.assert(
      fc.property(terminalStatusArb, (status) => {
        const result = buildNotificationContent(status, {});
        expect(result.body).toBe(FALLBACK_BODY[status]);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("body falls back to default when the corresponding field is null", () => {
    fc.assert(
      fc.property(terminalStatusArb, (status) => {
        const fieldKey =
          status === "Agreed" ? "current_offer" :
          status === "Blocked" ? "blocked_by" :
          "reason";
        const result = buildNotificationContent(status, { [fieldKey]: null });
        expect(result.body).toBe(FALLBACK_BODY[status]);
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
