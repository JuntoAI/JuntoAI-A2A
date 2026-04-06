import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";

function createRequest(url: string, cookies: Record<string, string> = {}): NextRequest {
  const req = new NextRequest(new URL(url, "http://localhost:3000"));
  for (const [name, value] of Object.entries(cookies)) {
    req.cookies.set(name, value);
  }
  return req;
}

describe("admin middleware", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_RUN_MODE", "cloud");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // Validates: Requirement 2.1 — unauthenticated user redirected to /admin/login
  it("redirects /admin/users to /admin/login when admin_session cookie is absent", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/admin/users");
    const res = middleware(req);

    expect(res.status).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/admin/login");
  });

  it("redirects /admin to /admin/login when admin_session cookie is absent", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/admin");
    const res = middleware(req);

    expect(res.status).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/admin/login");
  });

  it("redirects /admin/simulations to /admin/login when admin_session cookie is empty", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/admin/simulations", { admin_session: "" });
    const res = middleware(req);

    expect(res.status).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/admin/login");
  });

  // Validates: Requirement 2.1 — /admin/login itself should not redirect
  it("allows /admin/login through without redirect", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/admin/login");
    const res = middleware(req);

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });

  // Validates: Requirement 2.1 — authenticated admin passes through
  it("allows /admin/users through when admin_session cookie is present", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/admin/users", { admin_session: "valid-token" });
    const res = middleware(req);

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });

  it("allows nested admin routes with valid cookie", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/admin/simulations/abc123", { admin_session: "valid-token" });
    const res = middleware(req);

    expect(res.status).toBe(200);
  });

  // Validates: config.matcher includes /admin/:path*
  it("matcher includes /admin/:path*", async () => {
    const { config } = await import("../../middleware");
    expect(config.matcher).toContain("/admin/:path*");
  });
});
