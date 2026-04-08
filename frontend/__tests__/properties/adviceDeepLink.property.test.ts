import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { FC_NUM_RUNS } from "../fc-config";
import { buildAdviceDeepLinkUrl } from "@/lib/whatIfPrompts";

// ---------------------------------------------------------------------------
// Shared arbitraries
// ---------------------------------------------------------------------------

/** Role strings: lowercase alpha + underscores, 2–12 chars. */
const roleArb = fc.stringMatching(/^[a-z][a-z_]{1,11}$/);

/**
 * Prompt text: ASCII printable characters (0x20–0x7E) plus newlines and tabs.
 * We restrict to this range because the production code uses `btoa()` which
 * only handles Latin-1 (single-byte) characters. Unicode would throw in the
 * browser's native `btoa`. This matches real-world behavior.
 */
const promptTextArb = fc
  .array(
    fc.oneof(
      // printable ASCII
      fc.integer({ min: 0x20, max: 0x7e }).map((c) => String.fromCharCode(c)),
      // newlines / tabs for multi-line prompts
      fc.constantFrom("\n", "\r\n", "\t"),
    ),
    { minLength: 1, maxLength: 200 },
  )
  .map((chars) => chars.join(""));

/**
 * Generate a non-empty Record<string, string> mapping roles → prompt text.
 * Keys are unique role strings, values are prompt text.
 */
const promptMapArb = fc
  .array(fc.tuple(roleArb, promptTextArb), { minLength: 1, maxLength: 5 })
  .map((pairs) => {
    const map: Record<string, string> = {};
    for (const [role, text] of pairs) {
      map[role] = text; // last-write-wins deduplicates roles
    }
    return map;
  })
  .filter((m) => Object.keys(m).length > 0);

// ---------------------------------------------------------------------------
// Feature: 260_what-if-prompts
// ---------------------------------------------------------------------------

describe("Feature: 260_what-if-prompts", () => {

  // -------------------------------------------------------------------------
  // Property 8: Custom prompts URL encoding round-trip
  // -------------------------------------------------------------------------

  /**
   * **Validates: Requirements 6.2, 6.3, 6.4**
   *
   * For any valid Record<string, string> mapping agent roles to prompt text,
   * encoding via btoa(JSON.stringify(map)) then decoding via
   * JSON.parse(atob(encoded)) produces an object deeply equal to the original.
   *
   * Also: building a full URL with buildAdviceDeepLinkUrl, extracting the
   * customPrompts param, and decoding it preserves the original role and prompt.
   */
  describe("Property 8: Custom prompts URL encoding round-trip", () => {
    it("btoa/atob round-trip preserves arbitrary prompt maps", () => {
      fc.assert(
        fc.property(promptMapArb, (map) => {
          const encoded = btoa(JSON.stringify(map));
          const decoded = JSON.parse(atob(encoded)) as Record<string, string>;
          expect(decoded).toEqual(map);
        }),
        { numRuns: FC_NUM_RUNS },
      );
    });

    it("buildAdviceDeepLinkUrl round-trip preserves role and prompt", () => {
      fc.assert(
        fc.property(
          fc.stringMatching(/^[a-z][a-z0-9_]{1,15}$/), // scenarioId
          roleArb,
          promptTextArb,
          (scenarioId, role, prompt) => {
            const url = buildAdviceDeepLinkUrl(scenarioId, role, prompt);

            // Parse the URL and extract customPrompts param
            const parsed = new URL(url, "http://localhost");
            expect(parsed.searchParams.get("scenario")).toBe(scenarioId);

            const rawParam = parsed.searchParams.get("customPrompts");
            expect(rawParam).not.toBeNull();

            // Decode: reverse encodeURIComponent then atob then JSON.parse
            const decoded = JSON.parse(atob(decodeURIComponent(rawParam!))) as Record<string, string>;
            expect(decoded[role]).toBe(prompt);
            expect(Object.keys(decoded)).toHaveLength(1);
          },
        ),
        { numRuns: FC_NUM_RUNS },
      );
    });
  });

  // -------------------------------------------------------------------------
  // Property 9: Only valid roles are prefilled
  // -------------------------------------------------------------------------

  /**
   * **Validates: Requirements 6.6**
   *
   * For any decoded custom prompts map and any agent role list, filtering
   * the map to only roles in the agent list:
   * - contains no roles outside the agent list
   * - retains all roles that were in both the map and the agent list
   */
  it("Property 9: Only valid roles are prefilled", () => {
    fc.assert(
      fc.property(
        promptMapArb,
        fc.array(roleArb, { minLength: 0, maxLength: 8 }),
        (decodedMap, agentRoles) => {
          const validRoles = new Set(agentRoles);

          // Filter — mirrors the Arena page logic from design.md
          const filtered: Record<string, string> = {};
          for (const [role, prompt] of Object.entries(decodedMap)) {
            if (validRoles.has(role) && typeof prompt === "string" && prompt.trim()) {
              filtered[role] = prompt;
            }
          }

          // 1. No roles outside the agent list
          for (const role of Object.keys(filtered)) {
            expect(validRoles.has(role)).toBe(true);
          }

          // 2. Retains all roles that were in both map and agent list
          for (const role of Object.keys(decodedMap)) {
            if (
              validRoles.has(role) &&
              typeof decodedMap[role] === "string" &&
              decodedMap[role].trim()
            ) {
              expect(filtered[role]).toBe(decodedMap[role]);
            }
          }
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
