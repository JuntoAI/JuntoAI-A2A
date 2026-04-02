import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";

/**
 * Feature: agent-advanced-config, Property 9: Request payload includes only non-empty overrides
 *
 * For any set of agent configurations where some agents have custom prompts or
 * model overrides and others do not, the StartNegotiationRequest payload should
 * include only the agents with non-empty values in `custom_prompts` and
 * `model_overrides` respectively. Agents with empty or unset values should be
 * omitted from both maps.
 *
 * **Validates: Requirements 5.1, 5.2, 5.3, 5.5, 5.6, 5.7**
 */

describe("Property 9: Request payload includes only non-empty overrides", () => {
  let startNegotiation: typeof import("@/lib/api").startNegotiation;

  beforeEach(async () => {
    vi.restoreAllMocks();
    const apiModule = await import("@/lib/api");
    startNegotiation = apiModule.startNegotiation;
  });

  /** Arbitrary for a Record<string, string> with mixed empty/non-empty values. */
  const mixedRecordArb = fc.dictionary(
    fc.stringMatching(/^[A-Za-z][A-Za-z0-9_ ]{0,19}$/),
    fc.oneof(fc.constant(""), fc.string({ minLength: 1, maxLength: 100 })),
    { minKeys: 0, maxKeys: 5 },
  );

  it("payload includes custom_prompts and model_overrides only when records have entries", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.emailAddress(),
        fc.string({ minLength: 1, maxLength: 30 }),
        fc.array(fc.string({ minLength: 1 }), { maxLength: 3 }),
        mixedRecordArb,
        mixedRecordArb,
        async (email, scenarioId, toggles, customPrompts, modelOverrides) => {
          const mockFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
              session_id: "s",
              tokens_remaining: 99,
              max_turns: 10,
            }),
          });
          vi.stubGlobal("fetch", mockFetch);

          await startNegotiation(
            email,
            scenarioId,
            toggles,
            customPrompts,
            modelOverrides,
          );

          expect(mockFetch).toHaveBeenCalledOnce();
          const [, options] = mockFetch.mock.calls[0];
          const body = JSON.parse(options.body);

          const hasPromptKeys = Object.keys(customPrompts).length > 0;
          const hasOverrideKeys = Object.keys(modelOverrides).length > 0;

          // custom_prompts included iff the record has at least one key
          if (hasPromptKeys) {
            expect(body).toHaveProperty("custom_prompts");
            expect(body.custom_prompts).toEqual(customPrompts);
          } else {
            expect(body).not.toHaveProperty("custom_prompts");
          }

          // model_overrides included iff the record has at least one key
          if (hasOverrideKeys) {
            expect(body).toHaveProperty("model_overrides");
            expect(body.model_overrides).toEqual(modelOverrides);
          } else {
            expect(body).not.toHaveProperty("model_overrides");
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it("payload omits both fields when undefined is passed", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.emailAddress(),
        fc.string({ minLength: 1, maxLength: 30 }),
        fc.array(fc.string({ minLength: 1 }), { maxLength: 3 }),
        async (email, scenarioId, toggles) => {
          const mockFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
              session_id: "s",
              tokens_remaining: 99,
              max_turns: 10,
            }),
          });
          vi.stubGlobal("fetch", mockFetch);

          await startNegotiation(email, scenarioId, toggles);

          const [, options] = mockFetch.mock.calls[0];
          const body = JSON.parse(options.body);

          expect(body).not.toHaveProperty("custom_prompts");
          expect(body).not.toHaveProperty("model_overrides");
        },
      ),
      { numRuns: 100 },
    );
  });

  it("payload omits both fields when empty records are passed", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.emailAddress(),
        fc.string({ minLength: 1, maxLength: 30 }),
        fc.array(fc.string({ minLength: 1 }), { maxLength: 3 }),
        async (email, scenarioId, toggles) => {
          const mockFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
              session_id: "s",
              tokens_remaining: 99,
              max_turns: 10,
            }),
          });
          vi.stubGlobal("fetch", mockFetch);

          await startNegotiation(email, scenarioId, toggles, {}, {});

          const [, options] = mockFetch.mock.calls[0];
          const body = JSON.parse(options.body);

          expect(body).not.toHaveProperty("custom_prompts");
          expect(body).not.toHaveProperty("model_overrides");
        },
      ),
      { numRuns: 100 },
    );
  });
});
