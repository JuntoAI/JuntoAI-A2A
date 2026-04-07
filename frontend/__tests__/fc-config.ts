/**
 * Shared fast-check configuration.
 *
 * In CI (FAST_CHECK_CI=1), property tests run fewer iterations for speed.
 * Locally, the full 100 iterations run by default.
 */
export const FC_NUM_RUNS = process.env.FAST_CHECK_CI === "1" ? 30 : 100;
