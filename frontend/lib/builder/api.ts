/**
 * REST API client for the AI Scenario Builder.
 *
 * Follows the same pattern as frontend/lib/api.ts — all requests go
 * through the Next.js API proxy at /api/v1/*.
 */

import type {
  HealthCheckFinding,
  HealthCheckFullReport,
} from "./types";

const API_BASE = "/api/v1";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function extractErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();

    // Pydantic validation errors — format each field error for display
    if (Array.isArray(body.errors) && body.errors.length > 0) {
      return body.errors
        .map((e: { loc?: string[]; msg?: string }) => {
          const path = Array.isArray(e.loc) ? e.loc.join(" → ") : "unknown";
          return `${path}: ${e.msg ?? "invalid"}`;
        })
        .join("\n");
    }

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

export interface BuilderSaveCallbacks {
  onHealthStart?: () => void;
  onHealthFinding?: (finding: HealthCheckFinding) => void;
  onHealthComplete?: (report: HealthCheckFullReport) => void;
  onError?: (message: string) => void;
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
 *
 * The backend streams SSE events (health check progress + final save result).
 * This function consumes the stream, dispatches health-check callbacks, and
 * resolves with the final BuilderSaveResponse once `builder_save_complete`
 * arrives.
 */
export async function saveScenario(
  email: string,
  scenarioJson: Record<string, unknown>,
  callbacks?: BuilderSaveCallbacks,
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

  if (!res.body) {
    throw new Error("Response body is empty");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let saveResult: BuilderSaveResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      for (const line of rawEvent.split("\n")) {
        if (line.startsWith("data: ")) {
          const json = line.slice(6);
          try {
            const parsed = JSON.parse(json);
            switch (parsed.event_type) {
              case "builder_health_check_start":
                callbacks?.onHealthStart?.();
                break;
              case "builder_health_check_finding":
                callbacks?.onHealthFinding?.(parsed as HealthCheckFinding);
                break;
              case "builder_health_check_complete":
                callbacks?.onHealthComplete?.(
                  parsed.report as HealthCheckFullReport,
                );
                break;
              case "builder_save_complete":
                saveResult = {
                  scenario_id: parsed.scenario_id,
                  name: parsed.name,
                  readiness_score: parsed.readiness_score,
                  tier: parsed.tier,
                };
                break;
              case "builder_error":
                callbacks?.onError?.(parsed.message);
                throw new Error(parsed.message);
            }
          } catch (err) {
            if (err instanceof Error && err.message !== json) throw err;
            console.warn("[builder-save] Skipping malformed SSE payload:", json);
          }
        }
      }

      boundary = buffer.indexOf("\n\n");
    }
  }

  if (!saveResult) {
    throw new Error("Save stream ended without a save_complete event");
  }

  return saveResult;
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

/**
 * Update a custom scenario's JSON by ID.
 */
export async function updateCustomScenario(
  email: string,
  scenarioId: string,
  scenarioJson: Record<string, unknown>,
): Promise<{ scenario_id: string; name: string; updated_at: string }> {
  const res = await fetch(
    `${API_BASE}/builder/scenarios/${encodeURIComponent(scenarioId)}?email=${encodeURIComponent(email)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario_json: scenarioJson }),
    },
  );

  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }

  return res.json();
}

/**
 * Get the number of sessions linked to a custom scenario.
 */
export async function getScenarioSessionCount(
  email: string,
  scenarioId: string,
): Promise<{ count: number }> {
  const res = await fetch(
    `${API_BASE}/builder/scenarios/${encodeURIComponent(scenarioId)}/sessions/count?email=${encodeURIComponent(email)}`,
  );

  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }

  return res.json();
}
