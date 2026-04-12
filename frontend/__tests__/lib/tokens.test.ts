import { describe, it, expect, vi } from "vitest";

import { getUtcDateString, formatTokenDisplay } from "../../lib/tokens";

describe("getUtcDateString", () => {
  it("returns YYYY-MM-DD format", () => {
    const result = getUtcDateString();
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("returns UTC date, not local date", () => {
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
