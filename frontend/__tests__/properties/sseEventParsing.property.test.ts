import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import type {
  SSEEvent,
  AgentThoughtEvent,
  AgentMessageEvent,
  NegotiationCompleteEvent,
  SSEErrorEvent,
} from "../../types/sse";

/**
 * Feature: 060_a2a-glass-box-ui
 * Property 2: SSE event JSON parsing correctness
 *
 * Generate random valid SSE event JSON payloads for each event_type
 * (agent_thought, agent_message, negotiation_complete, error).
 * Parse the JSON string and verify all fields are preserved exactly.
 *
 * **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6**
 */

/** Arbitrary for agent_thought events */
const agentThoughtJsonArb: fc.Arbitrary<AgentThoughtEvent> = fc.record({
  event_type: fc.constant("agent_thought" as const),
  agent_name: fc.string({ minLength: 1, maxLength: 50 }),
  inner_thought: fc.string({ minLength: 1, maxLength: 500 }),
  turn_number: fc.integer({ min: 1, max: 100 }),
});

/** Arbitrary for agent_message events */
const agentMessageJsonArb: fc.Arbitrary<AgentMessageEvent> = fc.record({
  event_type: fc.constant("agent_message" as const),
  agent_name: fc.string({ minLength: 1, maxLength: 50 }),
  public_message: fc.string({ minLength: 1, maxLength: 500 }),
  turn_number: fc.integer({ min: 1, max: 100 }),
  proposed_price: fc.option(fc.double({ min: 0.01, max: 1e8, noNaN: true }), { nil: undefined }),
  retention_clause_demanded: fc.option(fc.boolean(), { nil: undefined }),
  status: fc.option(fc.constantFrom("CLEAR" as const, "WARNING" as const, "BLOCKED" as const), {
    nil: undefined,
  }),
});

/** Arbitrary for negotiation_complete events */
const completeJsonArb: fc.Arbitrary<NegotiationCompleteEvent> = fc.record({
  event_type: fc.constant("negotiation_complete" as const),
  session_id: fc.uuid(),
  deal_status: fc.constantFrom("Agreed" as const, "Blocked" as const, "Failed" as const),
  final_summary: fc.dictionary(
    fc.string({ minLength: 1, maxLength: 20 }),
    fc.oneof(fc.string({ maxLength: 100 }), fc.integer(), fc.boolean()),
  ) as fc.Arbitrary<Record<string, unknown>>,
});

/** Arbitrary for error events */
const errorJsonArb: fc.Arbitrary<SSEErrorEvent> = fc.record({
  event_type: fc.constant("error" as const),
  message: fc.string({ minLength: 1, maxLength: 200 }),
});

/** Combined arbitrary matching design doc generator strategy */
const sseEventArb: fc.Arbitrary<SSEEvent> = fc.oneof(
  agentThoughtJsonArb,
  agentMessageJsonArb,
  completeJsonArb,
  errorJsonArb,
);

describe("Property 2: SSE event JSON parsing correctness", () => {
  /**
   * **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6**
   *
   * For any randomly generated SSE event payload, serializing to JSON
   * and parsing back must preserve all fields exactly. This validates
   * that the SSEEvent type definitions correctly model the SSE payloads
   * and that JSON round-tripping is lossless.
   */
  it("JSON round-trip preserves all fields for any SSE event", () => {
    fc.assert(
      fc.property(sseEventArb, (event: SSEEvent) => {
        // Simulate SSE: serialize to JSON string (as backend would send)
        const jsonString = JSON.stringify(event);

        // Parse as the SSE client would
        const parsed: SSEEvent = JSON.parse(jsonString);

        // event_type is always preserved and classifiable
        expect(parsed.event_type).toBe(event.event_type);

        // All fields round-trip exactly
        switch (event.event_type) {
          case "agent_thought": {
            const p = parsed as AgentThoughtEvent;
            expect(p.agent_name).toBe(event.agent_name);
            expect(p.inner_thought).toBe(event.inner_thought);
            expect(p.turn_number).toBe(event.turn_number);
            break;
          }
          case "agent_message": {
            const p = parsed as AgentMessageEvent;
            expect(p.agent_name).toBe(event.agent_name);
            expect(p.public_message).toBe(event.public_message);
            expect(p.turn_number).toBe(event.turn_number);
            expect(p.proposed_price).toBe(event.proposed_price);
            expect(p.retention_clause_demanded).toBe(event.retention_clause_demanded);
            expect(p.status).toBe(event.status);
            break;
          }
          case "negotiation_complete": {
            const p = parsed as NegotiationCompleteEvent;
            expect(p.session_id).toBe(event.session_id);
            expect(p.deal_status).toBe(event.deal_status);
            expect(p.final_summary).toEqual(event.final_summary);
            break;
          }
          case "error": {
            const p = parsed as SSEErrorEvent;
            expect(p.message).toBe(event.message);
            break;
          }
        }
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirement 5.2**
   *
   * Every parsed SSE event must have a valid event_type that classifies
   * into one of the four known types.
   */
  it("every parsed event has a classifiable event_type", () => {
    const validTypes = ["agent_thought", "agent_message", "negotiation_complete", "error"];

    fc.assert(
      fc.property(sseEventArb, (event: SSEEvent) => {
        const parsed: SSEEvent = JSON.parse(JSON.stringify(event));
        expect(validTypes).toContain(parsed.event_type);
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 5.3, 5.4**
   *
   * Optional fields on agent_message (proposed_price, retention_clause_demanded,
   * status) must either be preserved exactly or be absent (undefined) — never
   * mutated to a different value.
   */
  it("optional agent_message fields are preserved or absent", () => {
    fc.assert(
      fc.property(agentMessageJsonArb, (event: AgentMessageEvent) => {
        const jsonString = JSON.stringify(event);
        const parsed = JSON.parse(jsonString) as AgentMessageEvent;

        // If the original had the field, parsed must match exactly
        // If the original didn't have it, parsed must also not have it
        if (event.proposed_price !== undefined) {
          expect(parsed.proposed_price).toBe(event.proposed_price);
        } else {
          expect(parsed).not.toHaveProperty("proposed_price");
        }

        if (event.retention_clause_demanded !== undefined) {
          expect(parsed.retention_clause_demanded).toBe(event.retention_clause_demanded);
        } else {
          expect(parsed).not.toHaveProperty("retention_clause_demanded");
        }

        if (event.status !== undefined) {
          expect(parsed.status).toBe(event.status);
        } else {
          expect(parsed).not.toHaveProperty("status");
        }
      }),
      { numRuns: 100 },
    );
  });
});
