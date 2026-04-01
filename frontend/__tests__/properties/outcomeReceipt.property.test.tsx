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
 *   (a) for Agreed — the final terms from final_summary
 *   (b) for Blocked — the block reason from final_summary
 *   (c) for Failed — a failure message indicating max turns reached
 *
 * **Validates: Requirements 10.1, 10.2, 10.3**
 */

// Use alphanumeric strings without trailing spaces to avoid text normalization issues
const safeKeyArb = fc.stringMatching(/^[a-z][a-z0-9]{1,9}$/);
const safeValueArb = fc.stringMatching(/^[A-Z][a-zA-Z0-9]{1,14}$/);

const dealStatusArb = fc.constantFrom("Agreed" as const, "Blocked" as const, "Failed" as const);

// Ensure unique keys to avoid duplicate text in DOM
const finalSummaryArb = fc.uniqueArray(
  fc.tuple(safeKeyArb, safeValueArb),
  { minLength: 1, maxLength: 4, selector: ([k]) => k },
).map((pairs) => Object.fromEntries(pairs));

describe("Property 8: Outcome Receipt renders appropriate content per deal status", () => {
  it("Agreed status renders final terms from finalSummary", () => {
    fc.assert(
      fc.property(finalSummaryArb, (summary) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Agreed"
            finalSummary={summary}
            elapsedTimeMs={10000}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const view = within(container);
        expect(view.getByTestId("outcome-heading")).toHaveTextContent("Deal Agreed");

        // The content section should contain all keys and values
        const content = view.getByTestId("outcome-content");
        for (const [key, value] of Object.entries(summary)) {
          expect(content).toHaveTextContent(key);
          expect(content).toHaveTextContent(String(value));
        }

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it("Blocked status renders block reason from finalSummary", () => {
    fc.assert(
      fc.property(safeValueArb, (reason) => {
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

        const content = view.getByTestId("outcome-content");
        expect(content).toHaveTextContent("Block Reason");
        expect(content).toHaveTextContent(reason);

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it("Failed status renders max turns failure message", () => {
    fc.assert(
      fc.property(finalSummaryArb, (summary) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Failed"
            finalSummary={summary}
            elapsedTimeMs={10000}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const view = within(container);
        expect(view.getByTestId("outcome-heading")).toHaveTextContent("Negotiation Failed");

        const content = view.getByTestId("outcome-content");
        expect(content).toHaveTextContent(
          "Negotiation reached maximum turns without agreement",
        );

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it("renders appropriate heading for any random deal status", () => {
    fc.assert(
      fc.property(dealStatusArb, finalSummaryArb, (status, summary) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus={status}
            finalSummary={status === "Blocked" ? { reason: "Blocked", ...summary } : summary}
            elapsedTimeMs={10000}
            scenarioOutcomeReceipt={null}
            scenarioId={null}
          />,
        );

        const view = within(container);
        const heading = view.getByTestId("outcome-heading");

        if (status === "Agreed") {
          expect(heading).toHaveTextContent("Deal Agreed");
        } else if (status === "Blocked") {
          expect(heading).toHaveTextContent("Deal Blocked");
        } else {
          expect(heading).toHaveTextContent("Negotiation Failed");
        }

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});
