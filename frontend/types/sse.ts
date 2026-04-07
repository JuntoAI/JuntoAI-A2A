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

export interface PersonaUsageStats {
  agent_role: string;
  agent_type: string;
  model_id: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  call_count: number;
  error_count: number;
  avg_latency_ms: number;
  tokens_per_message: number;
}

export interface ModelUsageStats {
  model_id: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  call_count: number;
  error_count: number;
  avg_latency_ms: number;
  tokens_per_message: number;
}

export interface UsageSummary {
  per_persona: PersonaUsageStats[];
  per_model: ModelUsageStats[];
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_calls: number;
  total_errors: number;
  avg_latency_ms: number;
  negotiation_duration_ms: number;
}
