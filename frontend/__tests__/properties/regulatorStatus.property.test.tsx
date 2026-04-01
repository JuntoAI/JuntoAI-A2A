import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import * as fc from "fast-check";
import MetricsDashboard from "@/components/glassbox/MetricsDashboard";
import ChatPanel from "@/components/glassbox/ChatPanel";
import type { MessageEntry } from "@/lib/glassBoxReducer";

/**
 * Feature: 060_a2a-glass-box-ui, Property 11: Regulator status to color mapping
 *
 * For any regulator status value (CLEAR/WARNING/BLOCKED), the Metrics Dashboard
 * traffic light and Chat Panel system message shall use the correct color.
 *
 * **Validates: Requirements 7.7, 8.3**
 */

const STATUS_TO_DASHBOARD_COLOR: Record<string, string> = {
  CLEAR: "bg-green-500",
  WARNING: "bg-yellow-500",
  BLOCKED: "bg-red-500",
};

const STATUS_TO_CHAT_COLOR: Record<string, string> = {
  CLEAR: "text-green-400",
  WARNING: "text-yellow-400",
  BLOCKED: "text-red-400",
};

const regulatorStatusArb = fc.constantFrom(
  "CLEAR" as const,
  "WARNING" as const,
  "BLOCKED" as const,
);

const safeNameArb = fc.stringMatching(/^[A-Z][a-zA-Z ]{1,19}$/);

describe("Property 11: Regulator status to color mapping", () => {
  it("MetricsDashboard traffic light uses correct color class for each status", () => {
    fc.assert(
      fc.property(regulatorStatusArb, safeNameArb, (status, name) => {
        const regulatorStatuses = { [name]: status };

        const { unmount } = render(
          <MetricsDashboard
            currentOffer={0}
            regulatorStatuses={regulatorStatuses}
            turnNumber={1}
            maxTurns={10}
            tokenBalance={50}
          />,
        );

        const indicator = screen.getByTestId(
          `traffic-light-${status.toLowerCase()}`,
        );
        expect(indicator.className).toContain(STATUS_TO_DASHBOARD_COLOR[status]);

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it("ChatPanel system message uses correct color class for each regulator status", () => {
    fc.assert(
      fc.property(regulatorStatusArb, safeNameArb, (status, name) => {
        const messages: MessageEntry[] = [
          {
            agentName: name,
            publicMessage: "Status update",
            turnNumber: 1,
            regulatorStatus: status,
            timestamp: Date.now(),
          },
        ];

        const { unmount } = render(
          <ChatPanel messages={messages} isConnected={true} />,
        );

        const statusMsg = screen.getByTestId("regulator-status-message");
        expect(statusMsg.className).toContain(STATUS_TO_CHAT_COLOR[status]);

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});
