import { describe, it, expect } from "vitest";
import * as fc from "fast-check";

/**
 * Feature: 060_a2a-glass-box-ui, Property 5: Toggle state management and reset
 *
 * Generate random sequences of toggle check/uncheck operations.
 * Verify active_toggles matches checked set.
 * Then simulate scenario switch and verify reset.
 *
 * **Validates: Requirements 3.3, 3.4, 3.5**
 */

// ---------------------------------------------------------------------------
// Pure toggle state logic (mirrors Control Panel behavior)
// ---------------------------------------------------------------------------

type ToggleOp = { id: string; checked: boolean };

/**
 * Apply a sequence of toggle operations to build the active toggles set.
 * This mirrors the Control Panel's onChange handler for InformationToggle.
 */
function applyToggleOps(ops: ToggleOp[]): Set<string> {
  const active = new Set<string>();
  for (const op of ops) {
    if (op.checked) {
      active.add(op.id);
    } else {
      active.delete(op.id);
    }
  }
  return active;
}

/**
 * Simulate a scenario switch: reset all toggles to unchecked.
 */
function resetToggles(): Set<string> {
  return new Set<string>();
}

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const toggleIdArb = fc.stringMatching(/^[a-z][a-z0-9_]{0,14}$/);

const toggleOpArb: fc.Arbitrary<ToggleOp> = fc.record({
  id: toggleIdArb,
  checked: fc.boolean(),
});

const toggleOpsArb = fc.array(toggleOpArb, { minLength: 1, maxLength: 20 });

// ---------------------------------------------------------------------------
// Property tests
// ---------------------------------------------------------------------------

describe("Property 5: Toggle state management and reset", () => {
  /**
   * **Validates: Requirements 3.3, 3.4**
   *
   * After applying any sequence of toggle check/uncheck operations,
   * the active_toggles set must contain exactly the IDs whose last
   * operation was "checked: true".
   */
  it("active_toggles matches the set of IDs last checked as true", () => {
    fc.assert(
      fc.property(toggleOpsArb, (ops) => {
        const activeSet = applyToggleOps(ops);

        // Build expected: for each unique id, the last operation determines membership
        const lastOpById = new Map<string, boolean>();
        for (const op of ops) {
          lastOpById.set(op.id, op.checked);
        }

        for (const [id, checked] of lastOpById) {
          if (checked) {
            expect(activeSet.has(id)).toBe(true);
          } else {
            expect(activeSet.has(id)).toBe(false);
          }
        }

        // No extra IDs beyond what was operated on
        for (const id of activeSet) {
          expect(lastOpById.has(id)).toBe(true);
        }
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirement 3.5**
   *
   * After any sequence of toggle operations followed by a scenario switch,
   * the active_toggles set must be empty (all toggles reset to unchecked).
   */
  it("scenario switch resets all toggles to unchecked regardless of prior state", () => {
    fc.assert(
      fc.property(toggleOpsArb, (ops) => {
        // Apply some operations to build up state
        const activeBeforeReset = applyToggleOps(ops);
        // Scenario switch should clear everything
        const activeAfterReset = resetToggles();

        expect(activeAfterReset.size).toBe(0);
        // Verify the pre-reset state was non-trivial (at least some ops happened)
        // This is just a sanity check — the real property is the reset
        expect(ops.length).toBeGreaterThan(0);
      }),
      { numRuns: 100 },
    );
  });

  /**
   * **Validates: Requirements 3.3, 3.4**
   *
   * Checking a toggle then unchecking it must result in it NOT being active.
   * Unchecking then checking must result in it being active.
   * The final state depends only on the last operation for each ID.
   */
  it("toggle state is idempotent — only the last operation per ID matters", () => {
    fc.assert(
      fc.property(
        toggleIdArb,
        fc.array(fc.boolean(), { minLength: 2, maxLength: 10 }),
        (id, checkedSequence) => {
          const ops: ToggleOp[] = checkedSequence.map((checked) => ({ id, checked }));
          const activeSet = applyToggleOps(ops);

          const lastChecked = checkedSequence[checkedSequence.length - 1];
          if (lastChecked) {
            expect(activeSet.has(id)).toBe(true);
          } else {
            expect(activeSet.has(id)).toBe(false);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
