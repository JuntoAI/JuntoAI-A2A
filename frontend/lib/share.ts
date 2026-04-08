/**
 * API client for the social sharing feature.
 *
 * All requests go through the Next.js API proxy at /api/v1/* which
 * handles service-to-service auth to the backend Cloud Run service.
 *
 * Follows the same patterns as api.ts — throws on non-2xx responses
 * with the error detail from the response body.
 */

const API_BASE = "/api/v1";

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface ParticipantSummary {
  role: string;
  name: string;
  agent_type: string;
  summary: string;
}

export interface SharePayload {
  share_slug: string;
  session_id: string;
  scenario_name: string;
  scenario_description: string;
  deal_status: "Agreed" | "Blocked" | "Failed";
  outcome_text: string;
  final_offer: number;
  turns_completed: number;
  warning_count: number;
  participant_summaries: ParticipantSummary[];
  elapsed_time_ms: number;
  share_image_url: string;
  created_at: string;
}

export interface SocialPostText {
  twitter: string;
  linkedin: string;
  facebook: string;
}

export interface CreateShareResponse {
  share_slug: string;
  share_url: string;
  social_post_text: SocialPostText;
  share_image_url: string;
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

export async function createShare(
  sessionId: string,
  email: string,
): Promise<CreateShareResponse> {
  const res = await fetch(`${API_BASE}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, email }),
  });

  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }

  return res.json();
}

export async function getShare(slug: string): Promise<SharePayload> {
  const res = await fetch(`${API_BASE}/share/${slug}`);

  if (!res.ok) {
    const detail = await extractErrorDetail(res);
    throw new Error(detail);
  }

  return res.json();
}
