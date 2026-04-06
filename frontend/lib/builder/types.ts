/**
 * TypeScript types for the AI Scenario Builder.
 *
 * Mirrors the backend Pydantic models in backend/app/builder/events.py
 * and backend/app/builder/models.py.
 */

// ---------------------------------------------------------------------------
// SSE Event Types
// ---------------------------------------------------------------------------

export type BuilderEventType =
  | "builder_token"
  | "builder_json_delta"
  | "builder_complete"
  | "builder_error"
  | "builder_health_check_start"
  | "builder_health_check_finding"
  | "builder_health_check_complete";

export interface BuilderTokenEvent {
  event_type: "builder_token";
  token: string;
}

export interface BuilderJsonDeltaEvent {
  event_type: "builder_json_delta";
  section: string;
  data: Record<string, unknown>;
}

export interface BuilderCompleteEvent {
  event_type: "builder_complete";
}

export interface BuilderErrorEvent {
  event_type: "builder_error";
  message: string;
}

// ---------------------------------------------------------------------------
// Health Check Types
// ---------------------------------------------------------------------------

export interface HealthCheckFinding {
  check_name: string;
  severity: "critical" | "warning" | "info";
  agent_role: string | null;
  message: string;
}

export interface HealthCheckFullReport {
  readiness_score: number;
  tier: "Ready" | "Needs Work" | "Not Ready";
  prompt_quality_scores: Array<{
    role: string;
    name: string;
    prompt_quality_score: number;
    findings: string[];
  }>;
  tension_score: number;
  budget_overlap_score: number;
  toggle_effectiveness_score: number;
  turn_sanity_score: number;
  stall_risk: { stall_risk_score: number; risks: string[] };
  findings: HealthCheckFinding[];
  recommendations: string[];
}

// ---------------------------------------------------------------------------
// Chat UI Types
// ---------------------------------------------------------------------------

export interface BuilderChatMessage {
  role: "user" | "assistant";
  content: string;
}
