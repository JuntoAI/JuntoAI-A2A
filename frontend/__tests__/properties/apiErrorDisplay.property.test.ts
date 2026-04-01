import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fc from "fast-check";
import { startNegotiation, TokenLimitError } from "@/lib/api";

/**
 * Feature: 060_a2a-glass-box-ui
 * Property 13: API error display on negotiation start failure
 *
 * Generate random HTTP error responses (status 400-599, excluding 429)
 * with random error detail strings. Call startNegotiation with a mocked
 * fetch returning the error response. Verify the thrown Error contains
 * the error detail string from the response body. Also test that 429
 * specifically throws TokenLimitError.
 *
 * **Validates: Requirements 4.7, 11.5**
 */

// ---------------------------------------------------------------------------
// Generators (from design doc)
// ---------------------------------------------------------------------------

/** Random non-429 HTTP error response */
const httpErrorArb = fc.record({
  status: fc.integer({ min: 400, max: 599 }).filter((s) => s !== 429),
  detail: fc.string({ minLength: 1 }),
});

/** Random 429 response with detail */
const tokenLimitErrorArb = fc.record({
  status: fc.constant(429),
  detail: fc.string({ minLength: 1 }),
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

const fetchSpy = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchSpy);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Property Tests
// ---------------------------------------------------------------------------

describe("Property 13: API error display on negotiation start failure", () => {
  /**
   * **Validates: Requirements 4.7, 11.5**
   *
   * For any non-429 HTTP error status (400-599), startNegotiation must
   * throw a generic Error whose message contains the detail string from
   * the response body. This ensures the UI can display the server's
   * error detail to the user.
   */
  it("throws Error containing response detail for non-429 HTTP errors", async () => {
    await fc.assert(
      fc.asyncProperty(httpErrorArb, async ({ status, detail }) => {
        fetchSpy.mockResolvedValueOnce(jsonResponse({ detail }, status));

        const err = await startNegotiation("test@example.com", "scenario-1", []).catch(
          (e: unknown) => e,
        );

        expect(err).toBeInstanceOf(Error);
        expect(err).not.toBeInstanceOf(TokenLimitError);
        expect((err as Error).message).toBe(detail);
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 4.7, 11.5**
   *
   * HTTP 429 must specifically throw a TokenLimitError (not a generic Error)
   * whose message contains the detail string from the response body.
   */
  it("throws TokenLimitError with response detail for HTTP 429", async () => {
    await fc.assert(
      fc.asyncProperty(tokenLimitErrorArb, async ({ detail }) => {
        fetchSpy.mockResolvedValueOnce(jsonResponse({ detail }, 429));

        const err = await startNegotiation("test@example.com", "scenario-1", []).catch(
          (e: unknown) => e,
        );

        expect(err).toBeInstanceOf(TokenLimitError);
        expect((err as Error).message).toBe(detail);
      }),
      { numRuns: 100 },
    );
  });
});
