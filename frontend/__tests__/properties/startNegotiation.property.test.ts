import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";

/**
 * Feature: 060_a2a-glass-box-ui, Property 7: Start negotiation request contains correct payload
 *
 * For any combination of authenticated email, selected scenario ID, and active
 * toggles list, the POST /api/v1/negotiation/start request body shall contain
 * `email` matching the authenticated email, `scenario_id` matching the selected
 * scenario, and `active_toggles` matching the current toggle selection.
 *
 * **Validates: Requirements 4.3**
 */

describe("Property 7: Start negotiation request contains correct payload", () => {
  let startNegotiation: typeof import("@/lib/api").startNegotiation;

  beforeEach(async () => {
    vi.restoreAllMocks();
    // Re-import to get a fresh module with clean fetch mock
    const apiModule = await import("@/lib/api");
    startNegotiation = apiModule.startNegotiation;
  });

  it("request body contains email, scenario_id, and active_toggles matching inputs", async () => {
    const inputArb = fc.record({
      email: fc.emailAddress(),
      scenarioId: fc.string({ minLength: 1 }),
      toggles: fc.array(fc.string({ minLength: 1 })),
    });

    await fc.assert(
      fc.asyncProperty(inputArb, async ({ email, scenarioId, toggles }) => {
        // Mock fetch to capture the request body
        const mockFetch = vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          json: async () => ({
            session_id: "test-session",
            tokens_remaining: 50,
            max_turns: 10,
          }),
        });
        vi.stubGlobal("fetch", mockFetch);

        await startNegotiation(email, scenarioId, toggles);

        expect(mockFetch).toHaveBeenCalledOnce();

        const [, options] = mockFetch.mock.calls[0];
        const body = JSON.parse(options.body);

        expect(body.email).toBe(email);
        expect(body.scenario_id).toBe(scenarioId);
        expect(body.active_toggles).toEqual(toggles);
      }),
      { numRuns: 100 },
    );
  });
});
