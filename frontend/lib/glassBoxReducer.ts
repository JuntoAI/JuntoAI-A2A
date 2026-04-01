import type {
  AgentThoughtEvent,
  AgentMessageEvent,
  NegotiationCompleteEvent,
} from "@/types/sse";

// ---------------------------------------------------------------------------
// State types
// ---------------------------------------------------------------------------

export interface ThoughtEntry {
  agentName: string;
  innerThought: string;
  turnNumber: number;
  timestamp: number;
}

export interface MessageEntry {
  agentName: string;
  publicMessage: string;
  turnNumber: number;
  proposedPrice?: number;
  retentionClauseDemanded?: boolean;
  regulatorStatus?: "CLEAR" | "WARNING" | "BLOCKED";
  timestamp: number;
}

export interface GlassBoxState {
  thoughts: ThoughtEntry[];
  messages: MessageEntry[];
  currentOffer: number;
  regulatorStatuses: Record<string, "CLEAR" | "WARNING" | "BLOCKED">;
  turnNumber: number;
  maxTurns: number;
  dealStatus: "Negotiating" | "Agreed" | "Blocked" | "Failed";
  finalSummary: Record<string, unknown> | null;
  error: string | null;
  isConnected: boolean;
}

// ---------------------------------------------------------------------------
// Action types
// ---------------------------------------------------------------------------

export type GlassBoxAction =
  | { type: "AGENT_THOUGHT"; payload: AgentThoughtEvent }
  | { type: "AGENT_MESSAGE"; payload: AgentMessageEvent }
  | { type: "NEGOTIATION_COMPLETE"; payload: NegotiationCompleteEvent }
  | { type: "SSE_ERROR"; payload: { message: string } }
  | { type: "CONNECTION_OPENED" }
  | { type: "CONNECTION_ERROR"; payload: { message: string } };

// ---------------------------------------------------------------------------
// Initial state factory
// ---------------------------------------------------------------------------

export function createInitialState(maxTurns: number): GlassBoxState {
  return {
    thoughts: [],
    messages: [],
    currentOffer: 0,
    regulatorStatuses: {},
    turnNumber: 0,
    maxTurns,
    dealStatus: "Negotiating",
    finalSummary: null,
    error: null,
    isConnected: false,
  };
}

// ---------------------------------------------------------------------------
// Reducer (pure function)
// ---------------------------------------------------------------------------

export function glassBoxReducer(
  state: GlassBoxState,
  action: GlassBoxAction,
): GlassBoxState {
  switch (action.type) {
    case "AGENT_THOUGHT": {
      const { agent_name, inner_thought, turn_number } = action.payload;
      return {
        ...state,
        thoughts: [
          ...state.thoughts,
          {
            agentName: agent_name,
            innerThought: inner_thought,
            turnNumber: turn_number,
            timestamp: Date.now(),
          },
        ],
        turnNumber: Math.max(state.turnNumber, turn_number),
      };
    }

    case "AGENT_MESSAGE": {
      const { agent_name, public_message, turn_number, proposed_price, retention_clause_demanded, status } =
        action.payload;

      const entry: MessageEntry = {
        agentName: agent_name,
        publicMessage: public_message,
        turnNumber: turn_number,
        timestamp: Date.now(),
      };
      if (proposed_price !== undefined) entry.proposedPrice = proposed_price;
      if (retention_clause_demanded !== undefined) entry.retentionClauseDemanded = retention_clause_demanded;
      if (status !== undefined) entry.regulatorStatus = status;

      const nextRegulatorStatuses =
        status !== undefined
          ? { ...state.regulatorStatuses, [agent_name]: status }
          : state.regulatorStatuses;

      return {
        ...state,
        messages: [...state.messages, entry],
        turnNumber: Math.max(state.turnNumber, turn_number),
        currentOffer: proposed_price !== undefined ? proposed_price : state.currentOffer,
        regulatorStatuses: nextRegulatorStatuses,
      };
    }

    case "NEGOTIATION_COMPLETE": {
      const { deal_status, final_summary } = action.payload;
      return {
        ...state,
        dealStatus: deal_status,
        finalSummary: final_summary,
        isConnected: false,
      };
    }

    case "SSE_ERROR":
      return {
        ...state,
        error: action.payload.message,
        isConnected: false,
      };

    case "CONNECTION_OPENED":
      return {
        ...state,
        isConnected: true,
        error: null,
      };

    case "CONNECTION_ERROR":
      return {
        ...state,
        error: action.payload.message,
        isConnected: false,
      };

    default:
      return state;
  }
}
