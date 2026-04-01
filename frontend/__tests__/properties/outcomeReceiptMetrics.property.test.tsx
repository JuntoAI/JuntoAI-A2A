import { describe, it, expect, vi } from "vitest";
import { render, within } from "@testing-library/react";
import * as fc from "fast-check";
import OutcomeReceipt from "@/components/glassbox/OutcomeReceipt";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

/**
 * Feature: 060_a2a-glass-box-ui, Property 9: Outcome Receipt displays both metric groups
 *
 * For any elapsed time value (in milliseconds) and for any scenario outcome_receipt config
 * containing equivalent_human_time and process_label, the Outcome Receipt shall display:
 *   (a) the measured elapsed time formatted as seconds
 *   (b) the scenario-estimated metrics with a visual label distinguishing them as estimates
 *
 * **Validates: Requirements 10.4**
 */

// No trailing whitespace — use strict alphanumeric patterns
const safeStringArb = fc.stringMatching(/^[a-zA-Z][a-zA-Z0-9]{0,19}$/);

const elapsedTimeMsArb = fc.integer({ min: 1000, max: 300000 });

const outcomeReceiptConfigArb = fc.record({
  equivalent_human_time: safeStringArb,
  process_label: safeStringArb,
});

describe("Property 9: Outcome Receipt displays both metric groups", () => {
  it("displays measured elapsed time formatted as seconds", () => {
    fc.assert(
      fc.property(elapsedTimeMsArb, outcomeReceiptConfigArb, (elapsedMs, config) => {
        const expectedSeconds = Math.round(elapsedMs / 1000);

        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Agreed"
            finalSummary={{ result: "done" }}
            elapsedTimeMs={elapsedMs}
            scenarioOutcomeReceipt={config}
            scenarioId={null}
          />,
        );

        const view = within(container);
        const measured = view.getByTestId("measured-metrics");
        expect(measured).toHaveTextContent(`Time Elapsed: ${expectedSeconds}s`);

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it("displays scenario-estimated metrics with Industry Estimate label", () => {
    fc.assert(
      fc.property(elapsedTimeMsArb, outcomeReceiptConfigArb, (elapsedMs, config) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Agreed"
            finalSummary={{ result: "done" }}
            elapsedTimeMs={elapsedMs}
            scenarioOutcomeReceipt={config}
            scenarioId={null}
          />,
        );

        const view = within(container);
        const estimated = view.getByTestId("estimated-metrics");

        // Check the label exists
        expect(estimated).toHaveTextContent("Industry Estimate");

        // Check equivalent human time and process label are present
        // Use the estimated container's text content to verify
        const textContent = estimated.textContent ?? "";
        expect(textContent).toContain(config.equivalent_human_time);
        expect(textContent).toContain(config.process_label);

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it("both metric groups are present simultaneously", () => {
    fc.assert(
      fc.property(elapsedTimeMsArb, outcomeReceiptConfigArb, (elapsedMs, config) => {
        const { unmount, container } = render(
          <OutcomeReceipt
            dealStatus="Blocked"
            finalSummary={{ reason: "blocked" }}
            elapsedTimeMs={elapsedMs}
            scenarioOutcomeReceipt={config}
            scenarioId={null}
          />,
        );

        const view = within(container);
        expect(view.getByTestId("measured-metrics")).toBeInTheDocument();
        expect(view.getByTestId("estimated-metrics")).toBeInTheDocument();

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});
