/**
 * API client for negotiation history.
 *
 * Fetches the authenticated user's completed negotiation sessions
 * grouped by UTC day. Calls the Next.js catch-all proxy which
 * forwards to the backend GET /api/v1/negotiation/history endpoint.
 */

const API_BASE = "/api/v1";

// ---------------------------------------------------------------------------
// Interfaces — mirror backend Pydantic models exactly
// ---------------------------------------------------------------------------

export interface SessionHistoryItem {
  session_id: string;
  scenario_id: string;
  scenario_name: string;
  deal_status: string;
  total_tokens_used: number;
  token_cost: number;
  created_at: string;
  completed_at: string | null;
}

export interface DayGroup {
  date: string; // YYYY-MM-DD
  total_token_cost: number;
  sessions: SessionHistoryItem[];
}

export interface SessionHistoryResponse {
  days: DayGroup[];
  total_token_cost: number;
  period_days: number;
}

// ---------------------------------------------------------------------------
// API function
// ---------------------------------------------------------------------------

export async function fetchNegotiationHistory(
  email: string,
  days?: number,
): Promise<SessionHistoryResponse> {
  const params = new URLSearchParams({ email });
  if (days !== undefined) {
    params.set("days", String(days));
  }

  const res = await fetch(`${API_BASE}/negotiation/history?${params}`);

  if (!res.ok) {
    let detail: string;
    try {
      const body = await res.json();
      detail = body.detail ?? body.message ?? JSON.stringify(body);
    } catch {
      detail = res.statusText || `HTTP ${res.status}`;
    }
    throw new Error(detail);
  }

  return res.json();
}
