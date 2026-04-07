export interface AgentThoughtEvent {
  event_type: "agent_thought";
  agent_name: string;
  inner_thought: string;
  turn_number: number;
}

export interface AgentMessageEvent {
  event_type: "agent_message";
  agent_name: string;
  public_message: string;
  turn_number: number;
  proposed_price?: number;
  retention_clause_demanded?: boolean;
  status?: "CLEAR" | "WARNING" | "BLOCKED";
}

export interface NegotiationCompleteEvent {
  event_type: "negotiation_complete";
  session_id: string;
  deal_status: "Agreed" | "Blocked" | "Failed";
  final_summary: Record<string, unknown>;
}

export interface EvaluationInterviewEvent {
  event_type: "evaluation_interview";
  agent_name: string;
  turn_number: number;
  status: "interviewing" | "complete";
  satisfaction_rating?: number;
  felt_respected?: boolean;
  is_win_win?: boolean;
}

export interface SSEErrorEvent {
  event_type: "error";
  message: string;
}

export type SSEEvent =
  | AgentThoughtEvent
  | AgentMessageEvent
  | NegotiationCompleteEvent
  | EvaluationInterviewEvent
  | SSEErrorEvent;
