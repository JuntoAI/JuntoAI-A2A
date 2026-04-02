/**
 * API client for the JuntoAI A2A backend.
 *
 * All functions throw on non-2xx responses with the error detail from the
 * response body. `startNegotiation` specifically checks for HTTP 429 and
 * throws a typed `TokenLimitError`.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface ScenarioSummary {
  id: string;
  name: string;
  description: string;
  difficulty: "beginner" | "intermediate" | "advanced" | "fun";
}

export interface AgentDefinition {
  name: string;
  role: string;
  goals: string[];
  model_id: string;
  type: "negotiator" | "regulator" | "observer";
}

export interface ToggleDefinition {
  id: string;
  label: string;
}

export interface ArenaScenario {
  id: string;
  name: string;
  description: string;
  agents: AgentDefinition[];
  toggles: ToggleDefinition[];
  negotiation_params: {
    max_turns: number;
    value_label?: string;
    value_format?: "currency" | "time_from_22" | "percent" | "number";
  };
  outcome_receipt: {
    equivalent_human_time: string;
    process_label: string;
  };
}

export interface StartNegotiationResponse {
  session_id: string;
  tokens_remaining: number;
  max_turns: number;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class TokenLimitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TokenLimitError";
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function extractErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? body.message ?? JSON.stringify(body);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchScenarios(): Promise<ScenarioSummary[]> {
  const res = await fetch(`${API_BASE}/scenarios`);
  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchScenarioDetail(
  scenarioId: string,
): Promise<ArenaScenario> {
  const res = await fetch(`${API_BASE}/scenarios/${scenarioId}`);
  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

export async function startNegotiation(
  email: string,
  scenarioId: string,
  activeToggles: string[],
  customPrompts?: Record<string, string>,
  modelOverrides?: Record<string, string>,
): Promise<StartNegotiationResponse> {
  const body: Record<string, unknown> = {
    email,
    scenario_id: scenarioId,
    active_toggles: activeToggles,
  };

  if (customPrompts && Object.keys(customPrompts).length > 0) {
    body.custom_prompts = customPrompts;
  }
  if (modelOverrides && Object.keys(modelOverrides).length > 0) {
    body.model_overrides = modelOverrides;
  }

  const res = await fetch(`${API_BASE}/negotiation/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (res.status === 429) {
    const detail = await extractErrorDetail(res);
    throw new TokenLimitError(detail);
  }

  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }

  return res.json();
}

export interface ModelInfo {
  model_id: string;
  family: string;
}

export async function fetchAvailableModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}
