import { describe, it, expect } from "vitest";
import {
  createInitialState,
  glassBoxReducer,
  type GlassBoxState,
} from "@/lib/glassBoxReducer";

// ---------------------------------------------------------------------------
// createInitialState
// ---------------------------------------------------------------------------

describe("createInitialState", () => {
  it("returns correct defaults for a given maxTurns", () => {
    const state = createInitialState(15);

    expect(state).toEqual({
      thoughts: [],
      messages: [],
      currentOffer: 0,
      regulatorStatuses: {},
      turnNumber: 0,
      maxTurns: 15,
      dealStatus: "Negotiating",
      isEvaluating: false,
      finalSummary: null,
      error: null,
      isConnected: false,
    });
  });

  it("respects different maxTurns values", () => {
    expect(createInitialState(5).maxTurns).toBe(5);
    expect(createInitialState(100).maxTurns).toBe(100);
  });
});

// ---------------------------------------------------------------------------
// AGENT_THOUGHT
// ---------------------------------------------------------------------------

describe("AGENT_THOUGHT", () => {
  it("appends to thoughts array", () => {
    const state = createInitialState(10);
    const next = glassBoxReducer(state, {
      type: "AGENT_THOUGHT",
      payload: {
        event_type: "agent_thought",
        agent_name: "Buyer",
        inner_thought: "I should lowball first.",
        turn_number: 1,
      },
    });

    expect(next.thoughts).toHaveLength(1);
    expect(next.thoughts[0].agentName).toBe("Buyer");
    expect(next.thoughts[0].innerThought).toBe("I should lowball first.");
    expect(next.thoughts[0].turnNumber).toBe(1);
    expect(next.thoughts[0].timestamp).toBeGreaterThan(0);
  });

  it("preserves existing thoughts when appending", () => {
    let state = createInitialState(10);
    state = glassBoxReducer(state, {
      type: "AGENT_THOUGHT",
      payload: {
        event_type: "agent_thought",
        agent_name: "Buyer",
        inner_thought: "First thought",
        turn_number: 1,
      },
    });
    state = glassBoxReducer(state, {
      type: "AGENT_THOUGHT",
      payload: {
        event_type: "agent_thought",
        agent_name: "Seller",
        inner_thought: "Second thought",
        turn_number: 2,
      },
    });

    expect(state.thoughts).toHaveLength(2);
    expect(state.thoughts[0].agentName).toBe("Buyer");
    expect(state.thoughts[1].agentName).toBe("Seller");
  });
});

// ---------------------------------------------------------------------------
// AGENT_MESSAGE — currentOffer
// ---------------------------------------------------------------------------

describe("AGENT_MESSAGE", () => {
  it("appends to messages array", () => {
    const state = createInitialState(10);
    const next = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "Seller",
        public_message: "I propose $500k.",
        turn_number: 1,
        proposed_price: 500000,
      },
    });

    expect(next.messages).toHaveLength(1);
    expect(next.messages[0].agentName).toBe("Seller");
    expect(next.messages[0].publicMessage).toBe("I propose $500k.");
    expect(next.messages[0].proposedPrice).toBe(500000);
  });

  it("updates currentOffer when proposed_price is present", () => {
    const state = createInitialState(10);
    const next = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "Buyer",
        public_message: "Counter at $400k.",
        turn_number: 2,
        proposed_price: 400000,
      },
    });

    expect(next.currentOffer).toBe(400000);
  });

  it("does NOT change currentOffer when proposed_price is absent", () => {
    let state = createInitialState(10);
    state = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "Buyer",
        public_message: "Offer $300k.",
        turn_number: 1,
        proposed_price: 300000,
      },
    });
    state = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "Seller",
        public_message: "Let me think about it.",
        turn_number: 2,
      },
    });

    expect(state.currentOffer).toBe(300000);
  });

  it("updates regulatorStatuses when status is present", () => {
    const state = createInitialState(10);
    const next = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "EU Regulator",
        public_message: "Compliance warning issued.",
        turn_number: 3,
        status: "WARNING",
      },
    });

    expect(next.regulatorStatuses).toEqual({ "EU Regulator": "WARNING" });
  });

  it("tracks multiple regulators independently", () => {
    let state = createInitialState(10);
    state = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "EU Regulator",
        public_message: "Clear.",
        turn_number: 1,
        status: "CLEAR",
      },
    });
    state = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "HR Compliance",
        public_message: "Warning.",
        turn_number: 2,
        status: "WARNING",
      },
    });

    expect(state.regulatorStatuses).toEqual({
      "EU Regulator": "CLEAR",
      "HR Compliance": "WARNING",
    });
  });

  it("does NOT change regulatorStatuses when status is absent", () => {
    let state = createInitialState(10);
    state = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "EU Regulator",
        public_message: "Clear.",
        turn_number: 1,
        status: "CLEAR",
      },
    });
    state = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "Buyer",
        public_message: "Just chatting.",
        turn_number: 2,
      },
    });

    expect(state.regulatorStatuses).toEqual({ "EU Regulator": "CLEAR" });
  });

  it("includes retentionClauseDemanded when present", () => {
    const state = createInitialState(10);
    const next = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "Seller",
        public_message: "I demand retention.",
        turn_number: 1,
        retention_clause_demanded: true,
      },
    });

    expect(next.messages[0].retentionClauseDemanded).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// NEGOTIATION_COMPLETE
// ---------------------------------------------------------------------------

describe("NEGOTIATION_COMPLETE", () => {
  it("sets dealStatus and finalSummary, isConnected=false, isEvaluating=false", () => {
    let state = createInitialState(10);
    state = { ...state, isConnected: true, isEvaluating: true };

    const next = glassBoxReducer(state, {
      type: "NEGOTIATION_COMPLETE",
      payload: {
        event_type: "negotiation_complete",
        session_id: "sess-123",
        deal_status: "Agreed",
        final_summary: { price: 450000, terms: "2-year retention" },
      },
    });

    expect(next.dealStatus).toBe("Agreed");
    expect(next.finalSummary).toEqual({ price: 450000, terms: "2-year retention" });
    expect(next.isConnected).toBe(false);
    expect(next.isEvaluating).toBe(false);
  });

  it("handles Blocked status", () => {
    const state = createInitialState(10);
    const next = glassBoxReducer(state, {
      type: "NEGOTIATION_COMPLETE",
      payload: {
        event_type: "negotiation_complete",
        session_id: "sess-456",
        deal_status: "Blocked",
        final_summary: { reason: "Regulator blocked the deal" },
      },
    });

    expect(next.dealStatus).toBe("Blocked");
  });

  it("handles Failed status", () => {
    const state = createInitialState(10);
    const next = glassBoxReducer(state, {
      type: "NEGOTIATION_COMPLETE",
      payload: {
        event_type: "negotiation_complete",
        session_id: "sess-789",
        deal_status: "Failed",
        final_summary: {},
      },
    });

    expect(next.dealStatus).toBe("Failed");
  });
});

// ---------------------------------------------------------------------------
// EVALUATION_INTERVIEW
// ---------------------------------------------------------------------------

describe("EVALUATION_INTERVIEW", () => {
  it("sets isEvaluating=true", () => {
    const state = createInitialState(10);
    const next = glassBoxReducer(state, {
      type: "EVALUATION_INTERVIEW",
      payload: {
        event_type: "evaluation_interview",
        agent_name: "Buyer",
        turn_number: 1,
        status: "interviewing",
      },
    });

    expect(next.isEvaluating).toBe(true);
  });

  it("keeps isEvaluating=true on subsequent interview events", () => {
    let state = createInitialState(10);
    state = glassBoxReducer(state, {
      type: "EVALUATION_INTERVIEW",
      payload: {
        event_type: "evaluation_interview",
        agent_name: "Buyer",
        turn_number: 1,
        status: "interviewing",
      },
    });
    state = glassBoxReducer(state, {
      type: "EVALUATION_INTERVIEW",
      payload: {
        event_type: "evaluation_interview",
        agent_name: "Buyer",
        turn_number: 1,
        status: "complete",
        satisfaction_rating: 7,
        felt_respected: true,
        is_win_win: true,
      },
    });

    expect(state.isEvaluating).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// SSE_ERROR
// ---------------------------------------------------------------------------

describe("SSE_ERROR", () => {
  it("sets error and isConnected=false", () => {
    let state = createInitialState(10);
    state = { ...state, isConnected: true };

    const next = glassBoxReducer(state, {
      type: "SSE_ERROR",
      payload: { message: "Stream interrupted" },
    });

    expect(next.error).toBe("Stream interrupted");
    expect(next.isConnected).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// CONNECTION_OPENED
// ---------------------------------------------------------------------------

describe("CONNECTION_OPENED", () => {
  it("sets isConnected=true and clears error", () => {
    let state = createInitialState(10);
    state = { ...state, error: "Previous error", isConnected: false };

    const next = glassBoxReducer(state, { type: "CONNECTION_OPENED" });

    expect(next.isConnected).toBe(true);
    expect(next.error).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// turnNumber tracking
// ---------------------------------------------------------------------------

describe("turnNumber tracking", () => {
  it("tracks max turn across thought and message events", () => {
    let state = createInitialState(10);

    // Turn 3 thought
    state = glassBoxReducer(state, {
      type: "AGENT_THOUGHT",
      payload: {
        event_type: "agent_thought",
        agent_name: "Buyer",
        inner_thought: "Thinking...",
        turn_number: 3,
      },
    });
    expect(state.turnNumber).toBe(3);

    // Turn 1 message (lower) — should NOT decrease
    state = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "Seller",
        public_message: "Hello.",
        turn_number: 1,
      },
    });
    expect(state.turnNumber).toBe(3);

    // Turn 5 message (higher) — should increase
    state = glassBoxReducer(state, {
      type: "AGENT_MESSAGE",
      payload: {
        event_type: "agent_message",
        agent_name: "Buyer",
        public_message: "Counter.",
        turn_number: 5,
        proposed_price: 100000,
      },
    });
    expect(state.turnNumber).toBe(5);
  });

  it("does not change turnNumber on non-event actions", () => {
    let state = createInitialState(10);
    state = glassBoxReducer(state, {
      type: "AGENT_THOUGHT",
      payload: {
        event_type: "agent_thought",
        agent_name: "A",
        inner_thought: "x",
        turn_number: 7,
      },
    });

    state = glassBoxReducer(state, { type: "CONNECTION_OPENED" });
    expect(state.turnNumber).toBe(7);

    state = glassBoxReducer(state, {
      type: "SSE_ERROR",
      payload: { message: "err" },
    });
    expect(state.turnNumber).toBe(7);
  });
});

// ---------------------------------------------------------------------------
// CONNECTION_ERROR
// ---------------------------------------------------------------------------

describe("CONNECTION_ERROR", () => {
  it("sets error and isConnected=false", () => {
    let state = createInitialState(10);
    state = { ...state, isConnected: true };

    const next = glassBoxReducer(state, {
      type: "CONNECTION_ERROR",
      payload: { message: "Connection lost" },
    });

    expect(next.error).toBe("Connection lost");
    expect(next.isConnected).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Immutability
// ---------------------------------------------------------------------------

describe("reducer immutability", () => {
  it("does not mutate the previous state", () => {
    const state = createInitialState(10);
    const frozen = Object.freeze({ ...state, thoughts: Object.freeze([...state.thoughts]) });

    // Should not throw — reducer must create new objects
    const next = glassBoxReducer(frozen as GlassBoxState, {
      type: "AGENT_THOUGHT",
      payload: {
        event_type: "agent_thought",
        agent_name: "A",
        inner_thought: "t",
        turn_number: 1,
      },
    });

    expect(next).not.toBe(frozen);
    expect(next.thoughts).not.toBe(frozen.thoughts);
  });
});
