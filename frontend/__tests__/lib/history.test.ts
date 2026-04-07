import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchNegotiationHistory } from "@/lib/history";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("fetchNegotiationHistory", () => {
  it("fetches history with email param", async () => {
    const payload = { days: [], total_token_cost: 0, period_days: 7 };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(payload),
    });

    const result = await fetchNegotiationHistory("user@example.com");
    expect(result).toEqual(payload);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/negotiation/history?email=user%40example.com",
    );
  });

  it("includes days param when provided", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ days: [], total_token_cost: 0, period_days: 30 }),
    });

    await fetchNegotiationHistory("a@b.com", 30);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/negotiation/history?email=a%40b.com&days=30",
    );
  });

  it("throws with detail from JSON error body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: () => Promise.resolve({ detail: "Token limit exceeded" }),
    });

    await expect(fetchNegotiationHistory("a@b.com")).rejects.toThrow(
      "Token limit exceeded",
    );
  });

  it("throws with message field from JSON error body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: () => Promise.resolve({ message: "Something broke" }),
    });

    await expect(fetchNegotiationHistory("a@b.com")).rejects.toThrow(
      "Something broke",
    );
  });

  it("falls back to statusText when JSON parsing fails", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: () => Promise.reject(new Error("not json")),
    });

    await expect(fetchNegotiationHistory("a@b.com")).rejects.toThrow(
      "Bad Gateway",
    );
  });

  it("falls back to HTTP status when statusText is empty", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "",
      json: () => Promise.reject(new Error("nope")),
    });

    await expect(fetchNegotiationHistory("a@b.com")).rejects.toThrow(
      "HTTP 500",
    );
  });

  it("stringifies unknown JSON body shape", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: () => Promise.resolve({ code: 42 }),
    });

    await expect(fetchNegotiationHistory("a@b.com")).rejects.toThrow(
      '{"code":42}',
    );
  });
});
