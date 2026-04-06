/**
 * REST API client for the AI Scenario Builder.
 *
 * Follows the same pattern as frontend/lib/api.ts — all requests go
 * through the Next.js API proxy at /api/v1/*.
 */

const API_BASE = "/api/v1";

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
// Types
// ---------------------------------------------------------------------------

export interface BuilderSaveResponse {
  scenario_id: string;
  name: string;
  readiness_score: number;
  tier: string;
}

export interface CustomScenarioSummary {
  scenario_id: string;
  scenario_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * Save a validated scenario JSON to the user's custom scenario store.
 */
export async function saveScenario(
  email: string,
  scenarioJson: Record<string, unknown>,
): Promise<BuilderSaveResponse> {
  const res = await fetch(`${API_BASE}/builder/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, scenario_json: scenarioJson }),
  });

  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }

  return res.json();
}

/**
 * List all custom scenarios for the given user email.
 */
export async function listCustomScenarios(
  email: string,
): Promise<CustomScenarioSummary[]> {
  const res = await fetch(
    `${API_BASE}/builder/scenarios?email=${encodeURIComponent(email)}`,
  );

  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }

  return res.json();
}

/**
 * Delete a custom scenario by ID.
 */
export async function deleteCustomScenario(
  email: string,
  scenarioId: string,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/builder/scenarios/${encodeURIComponent(scenarioId)}?email=${encodeURIComponent(email)}`,
    { method: "DELETE" },
  );

  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }
}
