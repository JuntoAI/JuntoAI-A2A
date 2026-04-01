import { describe, it, expect, vi } from "vitest";
import { NextRequest } from "next/server";
import { middleware, config } from "../../middleware";

function createRequest(url: string, cookies: Record<string, string> = {}): NextRequest {
  const req = new NextRequest(new URL(url, "http://localhost:3000"));
  for (const [name, value] of Object.entries(cookies)) {
    req.cookies.set(name, value);
  }
  return req;
}

describe("middleware", () => {
  it("redirects to / when junto_session cookie is absent", () => {
    const req = createRequest("/arena");
    const res = middleware(req);

    expect(res.status).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/");
  });

  it("redirects to / when junto_session cookie is empty", () => {
    const req = createRequest("/arena/some-path", { junto_session: "" });
    const res = middleware(req);

    expect(res.status).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/");
  });

  it("allows request when junto_session cookie is present", () => {
    const req = createRequest("/arena", { junto_session: "1" });
    const res = middleware(req);

    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });

  it("allows request on nested arena paths with valid cookie", () => {
    const req = createRequest("/arena/deep/nested/path", { junto_session: "1" });
    const res = middleware(req);

    expect(res.status).toBe(200);
  });
});

describe("config.matcher", () => {
  it("matches /arena/:path* routes only", () => {
    expect(config.matcher).toEqual(["/arena/:path*"]);
  });
});
