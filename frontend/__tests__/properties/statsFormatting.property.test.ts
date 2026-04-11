import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { FC_NUM_RUNS } from "../fc-config";

/**
 * Feature: 270_public-stats-dashboard
 * Property 9: Number formatting applies comma separators and decimal rules
 *
 * For any non-negative integer, the formatted string SHALL contain comma
 * separators at every three digits from the right. For any non-negative
 * float representing an average, the formatted string SHALL display
 * exactly one decimal place.
 *
 * **Validates: Requirements 12.4**
 */

/** Integer formatter matching the admin stats page implementation. */
function fmtInt(n: number): string {
  return n.toLocaleString("en-US");
}

/** Average formatter matching the admin stats page implementation. */
function fmtAvg(n: number | null): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

describe("Property 9: Number formatting rules", () => {
  it("integers have comma separators at every 3 digits", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 999_999_999 }),
        (n: number) => {
          const formatted = fmtInt(n);

          // Remove commas and verify it parses back to the same number
          const stripped = formatted.replace(/,/g, "");
          expect(Number(stripped)).toBe(n);

          // Verify comma placement: split by comma, first group 1-3 digits, rest exactly 3
          if (n >= 1000) {
            const parts = formatted.split(",");
            expect(parts[0].length).toBeGreaterThanOrEqual(1);
            expect(parts[0].length).toBeLessThanOrEqual(3);
            for (let i = 1; i < parts.length; i++) {
              expect(parts[i].length).toBe(3);
            }
          }
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("averages display exactly one decimal place", () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0, max: 999_999, noNaN: true, noDefaultInfinity: true }),
        (n: number) => {
          const formatted = fmtAvg(n);

          // Must contain a decimal point
          expect(formatted).toContain(".");

          // Extract the decimal portion (after last dot)
          const decimalPart = formatted.split(".").pop()!;
          expect(decimalPart.length).toBe(1);
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("null averages display em dash", () => {
    expect(fmtAvg(null)).toBe("—");
  });

  it("formatted integers round-trip correctly", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 999_999_999 }),
        (n: number) => {
          const formatted = fmtInt(n);
          const parsed = Number(formatted.replace(/,/g, ""));
          expect(parsed).toBe(n);
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
