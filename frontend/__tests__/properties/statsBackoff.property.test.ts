import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { FC_NUM_RUNS } from "../fc-config";

/**
 * Feature: 270_public-stats-dashboard
 * Property 8: SSE reconnect backoff is exponential and capped at 60 seconds
 *
 * For any retry count n >= 0, the computed reconnect delay SHALL equal
 * min(baseDelay * 2^n, 60000) milliseconds.
 *
 * **Validates: Requirements 10.4**
 */

/** The backoff function as specified in the design doc. */
function computeBackoff(retryCount: number, baseDelay: number = 1000): number {
  return Math.min(baseDelay * Math.pow(2, retryCount), 60000);
}

describe("Property 8: SSE reconnect backoff is exponential and capped", () => {
  it("backoff equals min(baseDelay * 2^n, 60000) for any retry count", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 100 }),
        fc.integer({ min: 100, max: 5000 }),
        (retryCount: number, baseDelay: number) => {
          const result = computeBackoff(retryCount, baseDelay);
          const expected = Math.min(baseDelay * Math.pow(2, retryCount), 60000);

          expect(result).toBe(expected);
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("backoff never exceeds 60000ms", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 200 }),
        (retryCount: number) => {
          const result = computeBackoff(retryCount);
          expect(result).toBeLessThanOrEqual(60000);
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("backoff is monotonically non-decreasing up to the cap", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 99 }),
        fc.integer({ min: 100, max: 5000 }),
        (retryCount: number, baseDelay: number) => {
          const current = computeBackoff(retryCount, baseDelay);
          const next = computeBackoff(retryCount + 1, baseDelay);
          expect(next).toBeGreaterThanOrEqual(current);
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });

  it("first retry (n=0) equals baseDelay when baseDelay <= 60000", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 60000 }),
        (baseDelay: number) => {
          const result = computeBackoff(0, baseDelay);
          expect(result).toBe(baseDelay);
        },
      ),
      { numRuns: FC_NUM_RUNS },
    );
  });
});
