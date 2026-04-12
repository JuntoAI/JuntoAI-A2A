// Client-side calls use relative URLs to go through the Next.js API proxy
// (frontend/app/api/v1/[...path]/route.ts) which adds IAM auth for Cloud Run.
const API_URL = "";

export interface CheckEmailResponse {
  has_password: boolean;
}

export interface LoginResponse {
  email: string;
  tier: number;
  daily_limit: number;
  token_balance: number;
}

/** Join waitlist / login with email only (no password). */
export async function joinWaitlist(email: string): Promise<LoginResponse> {
  const res = await fetch(`${API_URL}/api/v1/auth/join`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    throw new Error(`join failed: ${res.status}`);
  }
  return res.json();
}

/** Check if an email has a password set. */
export async function checkEmail(email: string): Promise<CheckEmailResponse> {
  const res = await fetch(`${API_URL}/api/v1/auth/check-email/${encodeURIComponent(email)}`);
  if (!res.ok) {
    throw new Error(`check-email failed: ${res.status}`);
  }
  return res.json();
}

/** Login with email + password. Throws on 401 (invalid password). */
export async function loginWithPassword(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (res.status === 401) {
    throw new Error("Invalid password");
  }
  if (!res.ok) {
    throw new Error(`login failed: ${res.status}`);
  }
  return res.json();
}

/** Login with Google ID token. Throws on 404 (no linked account). */
export async function loginWithGoogle(idToken: string): Promise<LoginResponse> {
  const res = await fetch(`${API_URL}/api/v1/auth/google/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (res.status === 404) {
    throw new Error("No linked account found for this Google account. Please sign in with email first and link your Google account from the profile page.");
  }
  if (!res.ok) {
    throw new Error(`Google login failed: ${res.status}`);
  }
  return res.json();
}

/** Set a password for an account. */
export async function setPassword(email: string, password: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/auth/set-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `set-password failed: ${res.status}`);
  }
}

/** Change an existing password. */
export async function changePassword(
  email: string,
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, current_password: currentPassword, new_password: newPassword }),
  });
  if (res.status === 401) {
    throw new Error("Invalid current password");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `change-password failed: ${res.status}`);
  }
}

/** Link a Google account to a profile. */
export async function linkGoogle(
  idToken: string,
  email: string,
): Promise<{ google_oauth_id: string; google_email: string }> {
  const res = await fetch(`${API_URL}/api/v1/auth/google/link`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken, email }),
  });
  if (res.status === 409) {
    throw new Error("Google account already linked to another profile");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `link-google failed: ${res.status}`);
  }
  return res.json();
}

/** Unlink a Google account from a profile. */
export async function unlinkGoogle(email: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/auth/google/link/${encodeURIComponent(email)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`unlink-google failed: ${res.status}`);
  }
}
