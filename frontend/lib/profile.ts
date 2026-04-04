const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface ProfileResponse {
  display_name: string;
  email_verified: boolean;
  github_url: string | null;
  linkedin_url: string | null;
  profile_completed_at: string | null;
  created_at: string | null;
  password_hash_set: boolean;
  country: string | null;
  google_oauth_id: string | null;
  tier: number;
  daily_limit: number;
  token_balance: number;
}

/** Fetch (or create) a user profile by email. */
export async function getProfile(email: string): Promise<ProfileResponse> {
  const res = await fetch(`${API_URL}/api/v1/profile/${encodeURIComponent(email)}`);
  if (!res.ok) {
    throw new Error(`getProfile failed: ${res.status}`);
  }
  return res.json();
}

export interface ProfileUpdateData {
  display_name?: string;
  github_url?: string | null;
  linkedin_url?: string | null;
  country?: string | null;
}

/** Update a user profile. */
export async function updateProfile(email: string, data: ProfileUpdateData): Promise<ProfileResponse> {
  const res = await fetch(`${API_URL}/api/v1/profile/${encodeURIComponent(email)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`updateProfile failed: ${res.status}`);
  }
  return res.json();
}

/** Request email verification. */
export async function requestEmailVerification(email: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/profile/${encodeURIComponent(email)}/verify-email`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`requestEmailVerification failed: ${res.status}`);
  }
}
