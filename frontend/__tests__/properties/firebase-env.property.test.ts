import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fc from "fast-check";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 13: Missing Firebase env var throws descriptive error
 *
 * For each required Firebase env var, removing it causes the firebase.ts
 * module to throw an error whose message includes the config key name
 * when the Firestore instance is first accessed.
 *
 * Validates: Requirements 8.4
 */

const REQUIRED_ENV_VARS = [
  { envKey: "NEXT_PUBLIC_FIREBASE_API_KEY", configKey: "apiKey" },
  { envKey: "NEXT_PUBLIC_FIREBASE_PROJECT_ID", configKey: "projectId" },
  { envKey: "NEXT_PUBLIC_FIREBASE_APP_ID", configKey: "appId" },
] as const;

function setupFirebaseMocks() {
  const mockApp = { name: "[DEFAULT]", options: {}, automaticDataCollectionEnabled: false };
  vi.doMock("firebase/app", () => ({
    initializeApp: vi.fn(() => mockApp),
    getApps: vi.fn(() => []),
    getApp: vi.fn(() => mockApp),
  }));
  vi.doMock("firebase/firestore", () => ({
    getFirestore: vi.fn(() => ({ type: "firestore", app: { name: "[DEFAULT]" } })),
  }));
}

const nonEmptyStringArb = fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.length > 0);

describe("Property 13: Missing Firebase env var throws descriptive error", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each(REQUIRED_ENV_VARS)(
    "throws error mentioning '$configKey' when $envKey is missing",
    async ({ envKey, configKey }) => {
      await fc.assert(
        fc.asyncProperty(
          nonEmptyStringArb,
          nonEmptyStringArb,
          nonEmptyStringArb,
          async (val1, val2, val3) => {
            vi.resetModules();
            vi.unstubAllEnvs();

            const values = [val1, val2, val3];
            REQUIRED_ENV_VARS.forEach(({ envKey: ek }, i) => {
              vi.stubEnv(ek, values[i]);
            });

            vi.stubEnv(envKey, "");

            setupFirebaseMocks();

            // Import the module — it no longer throws at import time (lazy init)
            const mod = await import("../../lib/firebase");

            // Accessing a property on db triggers the lazy initialization via Proxy
            expect(() => {
              // eslint-disable-next-line @typescript-eslint/no-unused-expressions
              mod.db.type;
            }).toThrowError(`Missing Firebase env var: ${configKey}`);
          },
        ),
        { numRuns: 50 },
      );
    },
  );
});
