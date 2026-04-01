import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import type { AgentThoughtEvent, AgentMessageEvent, NegotiationCompleteEvent } from "@/types/sse";
import {
  createInitialState,
  glassBoxReducer,
  type GlassBoxAction,
  type GlassBoxState,
} from "@/lib/glassBoxReducer";

/**
 * Feature: 060_a2a-glass-box-ui, Property 1: Reducer state invariant under event sequences
 *
 * Generate random sequences of GlassBoxAction objects, apply through reducer,
 * verify state invariants hold for any action sequence.
 *
 * **Validates: Requirements 5.3, 5.4, 5.5, 5.6, 6.3, 7.3, 8.2, 8.3, 8.4, 11.2**
 */

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const agentNameArb = fc.string({ minLength: 1, maxLength: 30 });
const turnNumberArb = fc.integer({ min: 1, max: 100 });

/** Arbitrary for AGENT_THOUGHT actions */
const thoughtActionArb: fc.Arbitrary<GlassBoxAction> = fc
  .record({
    agent_name: agentNameArb,
    inner_thought: fc.string({ minLength: 1, maxLength: 200 }),
    turn_number: turnNumberArb,
  })
  .map(
    (payload): GlassBoxAction => ({
      type: "AGENT_THOUGHT",
      payload: { event_type: "agent_thought", ...payload } as AgentThoughtEvent,
    }),
  );

/** Arbitrary for AGENT_MESSAGE actions */
const messageActionArb: fc.Arbitrary<GlassBoxAction> = fc
  .record({
    agent_name: agentNameArb,
    public_message: fc.string({ minLength: 1, maxLength: 200 }),
    turn_number: turnNumberArb,
    proposed_price: fc.option(fc.double({ min: 0.01, max: 1e8, noNaN: true }), {
      nil: undefined,
    }),
    retention_clause_demanded: fc.option(fc.boolean(), { nil: undefined }),
    status: fc.option(
      fc.constantFrom("CLEAR" as const, "WARNING" as const, "BLOCKED" as const),
      { nil: undefined },
    ),
  })
  .map(
    (payload): GlassBoxAction => ({
      type: "AGENT_MESSAGE",
      payload: { event_type: "agent_message", ...payload } as AgentMessageEvent,
    }),
  );

/** Arbitrary for NEGOTIATION_COMPLETE actions */
const completeActionArb: fc.Arbitrary<GlassBoxAction> = fc
  .record({
    deal_status: fc.constantFrom("Agreed" as const, "Blocked" as const, "Failed" as const),
    final_summary: fc.dictionary(
      fc.string({ minLength: 1, maxLength: 20 }),
      fc.oneof(fc.string({ maxLength: 50 }), fc.integer(), fc.boolean()),
    ) as fc.Arbitrary<Record<string, unknown>>,
  })
  .map(
    (payload): GlassBoxAction => ({
      type: "NEGOTIATION_COMPLETE",
      payload: {
        event_type: "negotiation_complete",
        session_id: "test-session",
        ...payload,
      } as NegotiationCompleteEvent,
    }),
  );

/** Arbitrary for SSE_ERROR actions */
const errorActionArb: fc.Arbitrary<GlassBoxAction> = fc
  .string({ minLength: 1, maxLength: 100 })
  .map(
    (message): GlassBoxAction => ({
      type: "SSE_ERROR",
      payload: { message },
    }),
  );

/** Arbitrary for CONNECTION_OPENED actions */
const connectionOpenedArb: fc.Arbitrary<GlassBoxAction> = fc.constant({
  type: "CONNECTION_OPENED" as const,
});

/** Arbitrary for CONNECTION_ERROR actions */
const connectionErrorArb: fc.Arbitrary<GlassBoxAction> = fc
  .string({ minLength: 1, maxLength: 100 })
  .map(
    (message): GlassBoxAction => ({
      type: "CONNECTION_ERROR",
      payload: { message },
    }),
  );

/** Combined action sequence arbitrary per design doc generator strategy */
const actionSequenceArb: fc.Arbitrary<GlassBoxAction[]> = fc.array(
  fc.oneof(
    thoughtActionArb,
    messageActionArb,
    completeActionArb,
    errorActionArb,
    connectionOpenedArb,
    connectionErrorArb,
  ),
  { minLength: 0, maxLength: 50 },
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function applyActions(actions: GlassBoxAction[]): GlassBoxState {
  return actions.reduce(
    (state, action) => glassBoxReducer(state, action),
    createInitialState(15),
  );
}

// ---------------------------------------------------------------------------
// Property tests
// ---------------------------------------------------------------------------

describe("Property 1: Reducer state invariant under event sequences", () => {
  /**
   * **Validates: Requirements 5.3, 6.3**
   *
   * thoughts.length must equal the number of AGENT_THOUGHT actions dispatched.
   */
  it("thoughts.length matches AGENT_THOUGHT count in any action sequence", () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        const state = applyActions(actions);
        const thoughtCount = actions.filter((a) => a.type === "AGENT_THOUGHT").length;
        expect(state.thoughts).toHaveLength(thoughtCount);
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 5.4, 7.3**
   *
   * messages.length must equal the number of AGENT_MESSAGE actions dispatched.
   */
  it("messages.length matches AGENT_MESSAGE count in any action sequence", () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        const state = applyActions(actions);
        const messageCount = actions.filter((a) => a.type === "AGENT_MESSAGE").length;
        expect(state.messages).toHaveLength(messageCount);
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 8.2**
   *
   * currentOffer must match the last proposed_price from AGENT_MESSAGE actions,
   * or 0 if no message had a proposed_price.
   */
  it("currentOffer matches last proposed_price across any action sequence", () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        const state = applyActions(actions);

        const messagesWithPrice = actions.filter(
          (a): a is Extract<GlassBoxAction, { type: "AGENT_MESSAGE" }> =>
            a.type === "AGENT_MESSAGE" && a.payload.proposed_price !== undefined,
        );

        if (messagesWithPrice.length === 0) {
          expect(state.currentOffer).toBe(0);
        } else {
          const lastPrice = messagesWithPrice[messagesWithPrice.length - 1].payload.proposed_price;
          expect(state.currentOffer).toBe(lastPrice);
        }
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 8.3, 8.4**
   *
   * regulatorStatuses must match the last status per agent_name from
   * AGENT_MESSAGE actions that included a status field.
   */
  it("regulatorStatuses matches last status per agent in any action sequence", () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        const state = applyActions(actions);

        // Build expected map: last status per agent_name
        const expected: Record<string, "CLEAR" | "WARNING" | "BLOCKED"> = {};
        for (const action of actions) {
          if (action.type === "AGENT_MESSAGE" && action.payload.status !== undefined) {
            expected[action.payload.agent_name] = action.payload.status;
          }
        }

        expect(state.regulatorStatuses).toEqual(expected);
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 8.4**
   *
   * turnNumber must be the maximum turn_number across all AGENT_THOUGHT
   * and AGENT_MESSAGE events, or 0 if none dispatched.
   */
  it("turnNumber is max across all thought and message events", () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        const state = applyActions(actions);

        const turnNumbers = actions
          .filter((a) => a.type === "AGENT_THOUGHT" || a.type === "AGENT_MESSAGE")
          .map((a) => {
            if (a.type === "AGENT_THOUGHT") return a.payload.turn_number;
            return (a as Extract<GlassBoxAction, { type: "AGENT_MESSAGE" }>).payload.turn_number;
          });

        const expectedMax = turnNumbers.length > 0 ? Math.max(...turnNumbers) : 0;
        expect(state.turnNumber).toBe(expectedMax);
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 5.5, 5.6, 11.2**
   *
   * dealStatus must match the last NEGOTIATION_COMPLETE event's deal_status
   * if one was dispatched, otherwise remain "Negotiating".
   */
  it("dealStatus matches NEGOTIATION_COMPLETE if dispatched", () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        const state = applyActions(actions);

        const completeActions = actions.filter(
          (a): a is Extract<GlassBoxAction, { type: "NEGOTIATION_COMPLETE" }> =>
            a.type === "NEGOTIATION_COMPLETE",
        );

        if (completeActions.length === 0) {
          expect(state.dealStatus).toBe("Negotiating");
        } else {
          const lastComplete = completeActions[completeActions.length - 1];
          expect(state.dealStatus).toBe(lastComplete.payload.deal_status);
        }
      }),
      { numRuns: 100 },
    );
  });
});
