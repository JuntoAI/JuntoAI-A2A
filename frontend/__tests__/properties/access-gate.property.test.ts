import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fc from "fast-check";
import { NextRequest } from "next/server";
import { FC_NUM_RUNS } from "../fc-config";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Properties 6 & 7: Access gate blocks/allows users
 *
 * Property 6: For any protected route path with no session cookie,
 * the middleware SHALL redirect to `/` (HTTP 307).
 *
 * Property 7: For any protected route path with a valid session cookie,
 * the middleware SHALL allow access (HTTP 200, no redirect).
 *
 * These properties apply to cloud mode. In local mode, all requests pass through.
 */

/** Arbitrary for a safe path segment character set. */
const segmentCharArb = fc.constantFrom(
  "a", "b", "c", "d", "e", "f", "1", "2", "3", "-", "_",
);

/** Arbitrary for a non-empty path segment. */
const segmentArb = fc
  .array(segmentCharArb, { minLength: 1, maxLength: 12 })
  .map((chars) => chars.join(""));

/** Arbitrary for protected route paths like /arena/xyz or /arena/abc/def. */
const protectedPathArb = fc
  .oneof(
    segmentArb.map((s) => `/arena/${s}`),
    fc.tuple(segmentArb, segmentArb).map(([a, b]) => `/arena/${a}/${b}`),
  );

/** Helper: create a NextRequest with optional cookies. */
function createRequest(
  path: string,
  cookies: Record<string, string> = {},
): NextRequest {
  const req = new NextRequest(new URL(path, "http://localhost:3000"));
  for (const [name, value] of Object.entries(cookies)) {
    req.cookies.set(name, value);
  }
  return req;
}

describe("Property 6: Access gate blocks unauthenticated users (cloud mode)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_RUN_MODE", "cloud");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  /**
   * **Validates: Requirements 4.1, 4.2**
   *
   * For any random protected route path with no session cookie,
   * the middleware SHALL return a 307 redirect to `/`.
   */
  it("redirects to / when no junto_session cookie is present", async () => {
    const { middleware } = await import("../../middleware");
    fc.assert(
      fc.property(protectedPathArb, (path) => {
        const req = createRequest(path);
        const res = middleware(req);

        expect(res.status).toBe(307);
        expect(new URL(res.headers.get("location")!).pathname).toBe("/");
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});

describe("Property 7: Access gate allows authenticated users (cloud mode)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_RUN_MODE", "cloud");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  /**
   * **Validates: Requirements 4.3**
   *
   * For any random protected route path with a valid junto_session=1 cookie,
   * the middleware SHALL return 200 with no redirect.
   */
  it("allows access when junto_session cookie is present", async () => {
    const { middleware } = await import("../../middleware");
    fc.assert(
      fc.property(protectedPathArb, (path) => {
        const req = createRequest(path, { junto_session: "1" });
        const res = middleware(req);

        expect(res.status).toBe(200);
        expect(res.headers.get("location")).toBeNull();
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});

describe("Local mode: Access gate bypassed", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_RUN_MODE", "local");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  /**
   * **Validates: Requirements 12.2, 5.5**
   *
   * For any random protected route path with no session cookie,
   * the middleware SHALL allow access (HTTP 200) in local mode.
   */
  it("allows all requests without session cookie in local mode", async () => {
    const { middleware } = await import("../../middleware");
    fc.assert(
      fc.property(protectedPathArb, (path) => {
        const req = createRequest(path);
        const res = middleware(req);

        expect(res.status).toBe(200);
        expect(res.headers.get("location")).toBeNull();
      }),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
