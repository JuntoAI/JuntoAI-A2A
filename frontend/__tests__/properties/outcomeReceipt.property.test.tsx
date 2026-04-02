import { describe, it, expect, vi } from "vitest";
import { render, within } from "@testing-library/react";
import * as fc from "fast-check";
import OutcomeReceipt from "@/components/glassbox/OutcomeReceipt";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

/**
 * Feature: 060_a2a-glass-box-ui, Property 8: Outcome Receipt renders appropriate content per deal status
 *
 * For any negotiation_complete event with deal_status of "Agreed", "Blocked", or "Failed",
 * the Outcome Receipt shall render:
 *   (a) for Agreed — the outcome text and structured deal metrics
 *   (b) for Blocked — the blocked_by agent and reason text
 *   (c) for Failed — a failure message (custom reason or default max turns message)
 *
 * **Validates: Requirements 10.1, 10.2, 10.3**
 */

// Avoid consecutive spaces — DOM normalizes them, breaking toHaveTextContent
const safeStringArb = fc.stringMatching(/^[A-Z][a-zA-Z0-9]+(?: [a-zA-Z0-9]+){0,4}$/);
const positiveIntArb = fc.integer({ min: 1, max: 999999 });
const turnsArb = fc.integer({ min: 1, max: 50 });
const warningsArb = fc.integer({ min: 1, max: 10 });

const dealStatusArb = fc.constantFrom("Agreed" as const, "Blocked" as const, "Failed" as const);

describe("Property 8: Outcome Receipt renders appropriate content per deal status", () => {
  it("Agreed status renders outcome text when provided", () => {
    fc.assert(
      fc.property(safeStringArb, (outcome) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Agreed"
            finalSummary={{ outcome }}
            elapsedTimeMs={10000}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const view = within(container);
        expect(view.getByTestId("outcome-heading")).toHaveTextContent("Deal Agreed");
        expect(view.getByTestId("outcome-content")).toHaveTextContent(outcome);

        unmount();
      }),
      { numRuns: 50 },
    );
  });

  it("Agreed status renders current_offer as formatted Final Price", () => {
    fc.assert(
      fc.property(positiveIntArb, (offer) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Agreed"
            finalSummary={{ current_offer: offer }}
            elapsedTimeMs={10000}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const content = within(container).getByTestId("outcome-content");
        expect(content).toHaveTextContent("Final Price:");
        expect(content).toHaveTextContent(`$${offer.toLocaleString()}`);

        unmount();
      }),
      { numRuns: 50 },
    );
  });

  it("Blocked status renders reason text when provided", () => {
    fc.assert(
      fc.property(safeStringArb, (reason) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Blocked"
            finalSummary={{ reason }}
            elapsedTimeMs={10000}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const view = within(container);
        expect(view.getByTestId("outcome-heading")).toHaveTextContent("Deal Blocked");
        expect(view.getByTestId("outcome-content")).toHaveTextContent(reason);

        unmount();
      }),
      { numRuns: 50 },
    );
  });

  it("Blocked status renders blocked_by agent name when provided", () => {
    fc.assert(
      fc.property(safeStringArb, safeStringArb, (blockedBy, reason) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Blocked"
            finalSummary={{ blocked_by: blockedBy, reason }}
            elapsedTimeMs={10000}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const content = within(container).getByTestId("outcome-content");
        expect(content).toHaveTextContent(`Blocked by: ${blockedBy}`);

        unmount();
      }),
      { numRuns: 50 },
    );
  });

  it("Failed status renders default max turns message when no reason provided", () => {
    fc.assert(
      fc.property(positiveIntArb, (elapsedMs) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Failed"
            finalSummary={{}}
            elapsedTimeMs={elapsedMs}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const view = within(container);
        expect(view.getByTestId("outcome-heading")).toHaveTextContent("Negotiation Failed");
        expect(view.getByTestId("outcome-content")).toHaveTextContent(
          "Negotiation reached maximum turns without agreement",
        );

        unmount();
      }),
      { numRuns: 50 },
    );
  });

  it("Failed status renders custom reason when provided", () => {
    fc.assert(
      fc.property(safeStringArb, (reason) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Failed"
            finalSummary={{ reason }}
            elapsedTimeMs={10000}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const content = within(container).getByTestId("outcome-content");
        expect(content).toHaveTextContent(reason);
        expect(content.textContent).not.toContain(
          "Negotiation reached maximum turns without agreement",
        );

        unmount();
      }),
      { numRuns: 50 },
    );
  });

  it("renders correct heading for any deal status", () => {
    fc.assert(
      fc.property(dealStatusArb, (status) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus={status}
            finalSummary={status === "Blocked" ? { reason: "test" } : {}}
            elapsedTimeMs={10000}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const heading = within(container).getByTestId("outcome-heading");

        if (status === "Agreed") {
          expect(heading).toHaveTextContent("Deal Agreed");
        } else if (status === "Blocked") {
          expect(heading).toHaveTextContent("Deal Blocked");
        } else {
          expect(heading).toHaveTextContent("Negotiation Failed");
        }

        unmount();
      }),
      { numRuns: 50 },
    );
  });
});
