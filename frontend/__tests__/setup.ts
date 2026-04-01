import "@testing-library/jest-dom/vitest";

// Mock firebase/app
vi.mock("firebase/app", () => {
  const mockApp = { name: "[DEFAULT]", options: {}, automaticDataCollectionEnabled: false };
  return {
    initializeApp: vi.fn(() => mockApp),
    getApps: vi.fn(() => []),
    getApp: vi.fn(() => mockApp),
  };
});

// Mock firebase/firestore
vi.mock("firebase/firestore", () => {
  const mockDb = { type: "firestore", app: { name: "[DEFAULT]" } };
  return {
    getFirestore: vi.fn(() => mockDb),
    collection: vi.fn(),
    doc: vi.fn(),
    getDoc: vi.fn(),
    setDoc: vi.fn(),
    updateDoc: vi.fn(),
    serverTimestamp: vi.fn(() => ({ _methodName: "serverTimestamp" })),
    Timestamp: {
      now: vi.fn(() => ({ seconds: Date.now() / 1000, nanoseconds: 0 })),
      fromDate: vi.fn((d: Date) => ({ seconds: d.getTime() / 1000, nanoseconds: 0 })),
    },
  };
});
