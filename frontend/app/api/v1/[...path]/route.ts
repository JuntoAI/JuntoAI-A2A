/**
 * Catch-all API proxy route.
 *
 * Forwards all /api/v1/* requests from the browser to the backend
 * Cloud Run service with service-to-service OIDC auth. This keeps
 * the backend private (no allUsers invoker binding needed).
 *
 * SSE streams are forwarded as-is using a ReadableStream so the
 * browser receives events in real time.
 */

import { NextRequest } from "next/server";
import { BACKEND_ORIGIN, buildProxyHeaders } from "@/lib/proxy";

export const runtime = "nodejs";
// SSE streams can run for minutes — disable the default 25s timeout.
// Cloud Run's own request timeout (1200s) is the real ceiling.
export const maxDuration = 300;

async function proxyRequest(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const target = `${BACKEND_ORIGIN}${pathname}${search}`;

  const headers = await buildProxyHeaders(req.headers);

  const init: RequestInit = {
    method: req.method,
    headers,
    // Don't follow redirects — let the client handle them
    redirect: "manual",
  };

  // Forward body for non-GET/HEAD requests
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    // @ts-expect-error -- Node fetch supports duplex for streaming request bodies
    init.duplex = "half";
  }

  const upstream = await fetch(target, init);

  // For SSE streams, pipe the response body through as-is
  const contentType = upstream.headers.get("content-type") ?? "";
  const isStream = contentType.includes("text/event-stream");

  const responseHeaders = new Headers();
  // Forward content-type
  if (contentType) responseHeaders.set("content-type", contentType);
  // Forward cache-control
  const cc = upstream.headers.get("cache-control");
  if (cc) responseHeaders.set("cache-control", cc);

  if (isStream) {
    // Disable buffering for SSE
    responseHeaders.set("x-accel-buffering", "no");
    responseHeaders.set("cache-control", "no-cache, no-transform");
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
export const PATCH = proxyRequest;
