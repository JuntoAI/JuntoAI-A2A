import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
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
  matcher: ["/arena/:path*"],
};
