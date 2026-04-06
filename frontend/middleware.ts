import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
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
  matcher: ["/arena/:path*", "/admin/:path*"],
};
