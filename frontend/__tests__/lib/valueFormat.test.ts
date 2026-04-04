import { describe, it, expect } from "vitest";
import { formatValue } from "@/lib/valueFormat";

describe("formatValue", () => {
  it("formats currency with euro sign", () => {
    expect(formatValue(1000, "currency")).toBe("€1,000");
  });

  it("defaults to currency format", () => {
    expect(formatValue(500)).toBe("€500");
  });

  it("formats percent with rounding", () => {
    expect(formatValue(42.7, "percent")).toBe("43%");
  });

  it("formats number with locale string", () => {
    expect(formatValue(9999, "number")).toBe("9,999");
  });

  it("formats time_from_22 for 0 minutes (10:00 PM)", () => {
    expect(formatValue(0, "time_from_22")).toBe("10:00 PM");
  });

  it("formats time_from_22 for 60 minutes (11:00 PM)", () => {
    expect(formatValue(60, "time_from_22")).toBe("11:00 PM");
  });

  it("formats time_from_22 for 120 minutes (12:00 AM)", () => {
    expect(formatValue(120, "time_from_22")).toBe("12:00 AM");
  });

  it("formats time_from_22 for 150 minutes (12:30 AM)", () => {
    expect(formatValue(150, "time_from_22")).toBe("12:30 AM");
  });
});
