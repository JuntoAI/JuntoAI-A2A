/**
 * API client for the JuntoAI A2A backend.
 *
 * All requests go through the Next.js API proxy at /api/v1/* which
 * handles service-to-service auth to the backend Cloud Run service.
 *
 * All functions throw on non-2xx responses with the error detail from the
 * response body. `startNegotiation` specifically checks for HTTP 429 and
 * throws a typed `TokenLimitError`.
 */

const API_BASE = "/api/v1";

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

export async function fetchScenarios(email?: string): Promise<ScenarioSummary[]> {
  const params = email ? `?email=${encodeURIComponent(email)}` : "";
  const res = await fetch(`${API_BASE}/scenarios${params}`);
  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchScenarioDetail(
  scenarioId: string,
  email?: string,
): Promise<ArenaScenario> {
  const params = email ? `?email=${encodeURIComponent(email)}` : "";
  const res = await fetch(`${API_BASE}/scenarios/${scenarioId}${params}`);
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
  structuredMemoryRoles?: string[],
  milestoneSummariesEnabled?: boolean,
  noMemoryRoles?: string[],
): Promise<StartNegotiationResponse> {
  const body: Record<string, unknown> = {
    email,
    scenario_id: scenarioId,
    active_toggles: activeToggles,
  };

  if (structuredMemoryRoles && structuredMemoryRoles.length > 0) {
    body.structured_memory_enabled = true;
    body.structured_memory_roles = structuredMemoryRoles;
  } else {
    body.structured_memory_enabled = false;
    body.structured_memory_roles = [];
  }

  body.milestone_summaries_enabled = milestoneSummariesEnabled ?? false;
  body.no_memory_roles = noMemoryRoles ?? [];

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
  label: string;
}

export async function fetchAvailableModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }
  return res.json();
}
