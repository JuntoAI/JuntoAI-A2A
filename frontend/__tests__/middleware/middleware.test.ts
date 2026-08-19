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
  it("includes arena, admin, and catch-all patterns", async () => {
    const { config } = await import("../../middleware");
    expect(config.matcher).toContain("/arena/:path*");
    expect(config.matcher).toContain("/admin/:path*");
    // Catch-all for probe interception (excludes Next.js internals)
    expect(config.matcher).toContainEqual(
      expect.stringContaining("(?!_next/static|_next/image|favicon.ico)")
    );
  });
});


// ---------------------------------------------------------------------------
// Probe / vulnerability scanner rejection
// ---------------------------------------------------------------------------

describe("middleware (probe rejection)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_RUN_MODE", "cloud");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  const phpProbes = [
    "/wp-admin/install.php",
    "/wp-content/plugins/admin.php",
    "/wp-includes/ID3/index.php",
    "/blog/byp.php",
    "/first.php",
    "/images/security.php",
  ];

  const otherProbes = [
    "/.env",
    "/.git/config",
    "/backup.sql",
    "/config.asp",
    "/shell.aspx",
    "/cgi-bin/test.cgi",
    "/old-backup.bak",
  ];

  const wpPaths = [
    "/wp-admin/some/page",
    "/wp-content/uploads/file.jpg",
    "/wp-includes/js/jquery.js",
    "/wp-login.php",
    "/wordpress/readme.html",
  ];

  it.each(phpProbes)("blocks PHP probe: %s", async (path) => {
    const { middleware } = await import("../../middleware");
    const req = createRequest(path);
    const res = middleware(req);

    expect(res.status).toBe(404);
    expect(res.headers.get("content-type")).toBe("text/plain");
  });

  it.each(otherProbes)("blocks non-PHP probe: %s", async (path) => {
    const { middleware } = await import("../../middleware");
    const req = createRequest(path);
    const res = middleware(req);

    expect(res.status).toBe(404);
    expect(res.headers.get("content-type")).toBe("text/plain");
  });

  it.each(wpPaths)("blocks WordPress path: %s", async (path) => {
    const { middleware } = await import("../../middleware");
    const req = createRequest(path);
    const res = middleware(req);

    expect(res.status).toBe(404);
    expect(res.headers.get("content-type")).toBe("text/plain");
  });

  it("does not block legitimate paths", async () => {
    const { middleware } = await import("../../middleware");
    const legitimatePaths = ["/", "/arena", "/admin/login", "/api/health"];

    for (const path of legitimatePaths) {
      const req = createRequest(path);
      const res = middleware(req);
      expect(res.status).not.toBe(404);
    }
  });

  it("blocks probes regardless of query parameters", async () => {
    const { middleware } = await import("../../middleware");
    const req = createRequest("/shell.php?cmd=ls");
    const res = middleware(req);

    expect(res.status).toBe(404);
  });

  it("probe rejection takes priority over auth", async () => {
    const { middleware } = await import("../../middleware");
    // Even with a valid session, a probe path should 404
    const req = createRequest("/wp-admin/install.php", { junto_session: "valid" });
    const res = middleware(req);

    expect(res.status).toBe(404);
  });
});
