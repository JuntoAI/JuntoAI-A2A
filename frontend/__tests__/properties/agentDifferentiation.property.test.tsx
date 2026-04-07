import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import * as fc from "fast-check";
import ChatPanel from "@/components/glassbox/ChatPanel";
import type { MessageEntry } from "@/lib/glassBoxReducer";
import { FC_NUM_RUNS } from "../fc-config";

/**
 * Feature: 060_a2a-glass-box-ui, Property 10: Agent visual differentiation
 *
 * For any two agents with different indices, the Chat Panel shall use
 * distinct colors for their messages.
 *
 * **Validates: Requirements 2.3, 7.4**
 */

const AGENT_COLOR_PALETTE = [
  "#007BFF",
  "#00E676",
  "#FF6B6B",
  "#FFD93D",
  "#6C5CE7",
  "#A29BFE",
  "#FD79A8",
  "#00CEC9",
];

describe("Property 10: Agent visual differentiation", () => {
  it("assigns distinct CSS colors to agents with different indices", () => {
    // Generate pairs of distinct indices within the palette range
    const distinctPairArb = fc
      .tuple(
        fc.integer({ min: 0, max: AGENT_COLOR_PALETTE.length - 1 }),
        fc.integer({ min: 0, max: AGENT_COLOR_PALETTE.length - 1 }),
      )
      .filter(([a, b]) => a !== b);

    fc.assert(
      fc.property(distinctPairArb, ([indexA, indexB]) => {
        const agentA = `Agent_${indexA}`;
        const agentB = `Agent_${indexB}`;

        const messages: MessageEntry[] = [
          {
            agentName: agentA,
            publicMessage: "Message from A",
            turnNumber: 1,
            timestamp: 1,
          },
          {
            agentName: agentB,
            publicMessage: "Message from B",
            turnNumber: 2,
            timestamp: 2,
          },
        ];

        const { unmount } = render(
          <ChatPanel messages={messages} isConnected={true} />,
        );

        const labelA = screen.getByText(agentA);
        const labelB = screen.getByText(agentB);

        // Both should have inline color styles
        expect(labelA.style.color).toBeTruthy();
        expect(labelB.style.color).toBeTruthy();

        // Colors must be different for different agent indices
        // The ChatPanel assigns colors by first-appearance order (map index),
        // so agent A gets index 0, agent B gets index 1 — always distinct.
        expect(labelA.style.color).not.toBe(labelB.style.color);

        unmount();
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
