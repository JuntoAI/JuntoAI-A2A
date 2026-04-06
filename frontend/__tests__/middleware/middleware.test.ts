import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";

function createRequest(url: string, cookies: Record<string, string> = {}): NextRequest {
  const req = new NextRequest(new URL(url, "http://localhost:3000"));
  for (const [name, value] of Object.entries(cookies)) {
    req.cookies.set(name, value);
  }
  return req;
}

describe("middleware (cloud mode)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_RUN_MODE", "cloud");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("redirects to / when junto_session cookie is absent", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/arena");
    const res = middleware(req);

    expect(res.status).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/");
  });

  it("redirects to / when junto_session cookie is empty", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/arena/some-path", { junto_session: "" });
    const res = middleware(req);

    expect(res.status).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/");
  });

  it("allows request when junto_session cookie is present", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/arena", { junto_session: "1" });
    const res = middleware(req);

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });

  it("allows request on nested arena paths with valid cookie", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/arena/deep/nested/path", { junto_session: "1" });
    const res = middleware(req);

    expect(res.status).toBe(200);
  });
});

describe("middleware (local mode)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_RUN_MODE", "local");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("allows request without session cookie", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/arena");
    const res = middleware(req);

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });

  it("allows request on nested paths without session cookie", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/arena/deep/path");
    const res = middleware(req);

    expect(res.status).toBe(200);
  });
});

describe("middleware (default mode — no env set)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_RUN_MODE", "");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("defaults to local mode (allows without cookie)", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/arena");
    const res = middleware(req);

    expect(res.status).toBe(200);
  });
});

describe("config.matcher", () => {
  it("matches /arena/:path* and /admin/:path* routes", async () => {
    const { config } = await import("../../middleware");
    expect(config.matcher).toEqual(["/arena/:path*", "/admin/:path*"]);
  });
});
