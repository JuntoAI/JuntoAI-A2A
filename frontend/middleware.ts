import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Reject common vulnerability scanner probes before they hit the page router.
 *
 * Cloud Run bills per request-processing time; rendering a full Next.js 404 page
 * for WordPress/PHP probes wastes CPU and keeps the instance warm. This returns a
 * minimal plain-text 404 in ~0ms with no React rendering.
 *
 * In the 7 days ending 2026-08-18, 100% of 4xx traffic to the frontend was
 * automated vulnerability scanning: .php, .asp, .cgi, .env, wp-admin,
 * wp-includes, wp-content — zero legitimate users hit these paths on a
 * Next.js app.
 */
const PROBE_PATTERN =
  /\.(php|asp|aspx|cgi|env|git|sql|bak|old|swp|DS_Store)(\?.*)?$/i;
const WP_PATTERN = /^\/(wp-admin|wp-content|wp-includes|wp-login|wordpress)\b/i;
const DOTFILE_PATTERN = /^\/\.(env|git|svn|htaccess|htpasswd)/i;

function isProbe(pathname: string): boolean {
  return (
    PROBE_PATTERN.test(pathname) ||
    WP_PATTERN.test(pathname) ||
    DOTFILE_PATTERN.test(pathname)
  );
}

export function middleware(request: NextRequest) {
  // --- Bot/scanner rejection (before any auth logic) ---
  if (isProbe(request.nextUrl.pathname)) {
    return new NextResponse("Not Found", {
      status: 404,
      headers: { "Content-Type": "text/plain" },
    });
  }

  // Admin routes: check admin_session cookie, redirect to /admin/login if missing
  if (request.nextUrl.pathname.startsWith("/admin")) {
    if (request.nextUrl.pathname === "/admin/login") return NextResponse.next();
    const adminCookie = request.cookies.get("admin_session");
    if (!adminCookie?.value) {
      return NextResponse.redirect(new URL("/admin/login", request.url));
    }
    return NextResponse.next();
  }

  // In local mode, skip auth — allow all requests through
  if (process.env.NEXT_PUBLIC_RUN_MODE !== "cloud") {
    return NextResponse.next();
  }

  const sessionCookie = request.cookies.get("junto_session");

  if (!sessionCookie || !sessionCookie.value) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Probe paths must be matched here so the middleware function runs on them.
  // Next.js only invokes middleware for paths in this matcher.
  matcher: [
    "/arena/:path*",
    "/admin/:path*",
    // Catch-all for probe patterns. The regex inside middleware() does the
    // actual filtering; this just ensures the middleware is invoked at all.
    // Excludes Next.js internals and static assets to avoid overhead on every
    // legitimate request.
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
