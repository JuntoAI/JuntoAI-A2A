/**
 * Server-side proxy utilities for forwarding API requests to the backend.
 *
 * In Cloud Run, the frontend service account has roles/run.invoker on the
 * backend. We fetch an OIDC identity token from the GCE metadata server
 * and attach it as a Bearer token. In local dev, we skip auth entirely.
 */

/** Backend origin — server-side only, never exposed to the browser. */
export const BACKEND_ORIGIN =
  process.env.BACKEND_URL || "http://localhost:8000";

/**
 * Fetch a Google OIDC identity token for the given audience (backend URL).
 * Returns null when running outside GCP (local dev).
 */
async function fetchIdentityToken(audience: string): Promise<string | null> {
  // Skip auth in local development
  if (!process.env.K_SERVICE) return null;

  const metadataUrl =
    `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${audience}`;

  const res = await fetch(metadataUrl, {
    headers: { "Metadata-Flavor": "Google" },
  });

  if (!res.ok) {
    console.error(`Failed to fetch identity token: ${res.status}`);
    return null;
  }

  return res.text();
}

/**
 * Build headers for a proxied request to the backend.
 * Copies safe headers from the incoming request and adds auth.
 */
export async function buildProxyHeaders(
  incomingHeaders: Headers,
): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};

  // Forward content-type if present
  const ct = incomingHeaders.get("content-type");
  if (ct) headers["content-type"] = ct;

  // Forward accept
  const accept = incomingHeaders.get("accept");
  if (accept) headers["accept"] = accept;

  // Forward cookies (needed for admin_session and other auth cookies)
  const cookie = incomingHeaders.get("cookie");
  if (cookie) headers["cookie"] = cookie;

  // Attach identity token for Cloud Run service-to-service auth
  const token = await fetchIdentityToken(BACKEND_ORIGIN);
  if (token) {
    headers["authorization"] = `Bearer ${token}`;
  }

  return headers;
}

/**
 * Perform a server-side fetch to the backend with OIDC auth.
 * Use this from server components instead of going through the proxy route.
 */
export async function backendFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const token = await fetchIdentityToken(BACKEND_ORIGIN);
  const headers = new Headers(init?.headers);
  if (token) headers.set("authorization", `Bearer ${token}`);

  return fetch(`${BACKEND_ORIGIN}${path}`, { ...init, headers });
}
