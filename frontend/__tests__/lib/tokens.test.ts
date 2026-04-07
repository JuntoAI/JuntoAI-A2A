import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock the firebase module so importing tokens.ts doesn't trigger env var validation
vi.mock("../../lib/firebase", () => ({
  getDb: vi.fn(() => ({ type: "firestore", app: { name: "[DEFAULT]" } })),
}));

import { getUtcDateString, needsReset, resetTokens, formatTokenDisplay } from "../../lib/tokens";

describe("getUtcDateString", () => {
  it("returns YYYY-MM-DD format", () => {
    const result = getUtcDateString();
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("returns UTC date, not local date", () => {
    // Pin to a known UTC date
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-06-15T23:30:00Z"));
    expect(getUtcDateString()).toBe("2025-06-15");
    vi.useRealTimers();
  });

  it("handles UTC midnight boundary", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-01-01T00:00:00Z"));
    expect(getUtcDateString()).toBe("2025-01-01");
    vi.useRealTimers();
  });
});

describe("needsReset", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-07-10T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns true when lastResetDate is yesterday", () => {
    expect(needsReset("2025-07-09")).toBe(true);
  });

  it("returns false when lastResetDate is today", () => {
    expect(needsReset("2025-07-10")).toBe(false);
  });

  it("returns true when lastResetDate is far in the past", () => {
    expect(needsReset("2024-01-01")).toBe(true);
  });

  it("returns false when lastResetDate is in the future", () => {
    expect(needsReset("2025-12-31")).toBe(false);
  });
});

describe("resetTokens", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-07-10T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("calls updateDoc with correct args", async () => {
    const { updateDoc, doc } = await import("firebase/firestore");

    await resetTokens("test@example.com", 100);

    expect(doc).toHaveBeenCalledWith(expect.anything(), "waitlist", "test@example.com");
    expect(updateDoc).toHaveBeenCalled();
    const [, payload] = vi.mocked(updateDoc).mock.calls[0];
    expect(payload).toEqual({ token_balance: 100, last_reset_date: "2025-07-10" });
  });
});

describe("formatTokenDisplay", () => {
  it("formats positive balance", () => {
    expect(formatTokenDisplay(75, 100)).toBe("Tokens: 75 / 100");
  });

  it("formats zero balance", () => {
    expect(formatTokenDisplay(0, 100)).toBe("Tokens: 0 / 100");
  });

  it("clamps negative balance to 0", () => {
    expect(formatTokenDisplay(-5, 100)).toBe("Tokens: 0 / 100");
  });

  it("formats max balance", () => {
    expect(formatTokenDisplay(100, 100)).toBe("Tokens: 100 / 100");
  });
});
