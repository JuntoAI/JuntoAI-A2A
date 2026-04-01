import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import * as fc from "fast-check";
import ChatPanel from "@/components/glassbox/ChatPanel";
import type { MessageEntry } from "@/lib/glassBoxReducer";

/**
 * Feature: 060_a2a-glass-box-ui, Property 12: Proposed price rendering in Chat Panel
 *
 * For any agent_message event containing a proposed_price, the Chat Panel
 * shall render the price as a visually highlighted element.
 *
 * **Validates: Requirements 7.6**
 */

const safeNameArb = fc.stringMatching(/^[A-Z][a-zA-Z]{1,14}$/);
const safeMessageArb = fc.stringMatching(/^[a-zA-Z][a-zA-Z0-9 ]{0,29}$/);
const priceArb = fc.integer({ min: 1, max: 10_000_000 });

describe("Property 12: Proposed price rendering in Chat Panel", () => {
  it("renders proposed price as a highlighted badge for every agent_message with proposed_price", () => {
    fc.assert(
      fc.property(
        safeNameArb,
        safeMessageArb,
        priceArb,
        (agentName, publicMessage, proposedPrice) => {
          const messages: MessageEntry[] = [
            {
              agentName,
              publicMessage,
              turnNumber: 1,
              proposedPrice,
              timestamp: Date.now(),
            },
          ];

          const { unmount } = render(
            <ChatPanel messages={messages} isConnected={true} />,
          );

          // The proposed price badge must be present
          const badge = screen.getByTestId("proposed-price-badge");
          expect(badge).toBeInTheDocument();

          // Badge must contain the formatted price value
          const formattedPrice = proposedPrice.toLocaleString();
          expect(badge.textContent).toContain(formattedPrice);

          // Badge should have highlight styling (blue background)
          expect(badge.className).toContain("bg-blue-100");
          expect(badge.className).toContain("text-blue-800");

          unmount();
        },
      ),
      { numRuns: 100 },
    );
  });
});
