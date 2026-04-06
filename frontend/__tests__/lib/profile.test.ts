import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getProfile,
  updateProfile,
  requestEmailVerification,
} from "@/lib/profile";
import type { ProfileResponse } from "@/lib/profile";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const sampleProfile: ProfileResponse = {
  display_name: "Test User",
  email_verified: true,
  github_url: "https://github.com/testuser",
  linkedin_url: null,
  profile_completed_at: "2024-01-01T00:00:00Z",
  created_at: "2024-01-01T00:00:00Z",
  password_hash_set: true,
  country: "US",
  google_oauth_id: null,
  tier: 0,
  daily_limit: 100,
  token_balance: 95,
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

const fetchSpy = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchSpy);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// getProfile
// ---------------------------------------------------------------------------

describe("getProfile", () => {
  it("returns ProfileResponse on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(sampleProfile));

    const result = await getProfile("user@test.com");

    expect(result).toEqual(sampleProfile);
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/profile/user%40test.com",
    );
  });

  it("throws on non-200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 404));

    await expect(getProfile("nobody@test.com")).rejects.toThrow(
      "getProfile failed: 404",
    );
  });
});

// ---------------------------------------------------------------------------
// updateProfile
// ---------------------------------------------------------------------------

describe("updateProfile", () => {
  it("returns ProfileResponse on 200", async () => {
    const updated = { ...sampleProfile, display_name: "New Name" };
    fetchSpy.mockResolvedValueOnce(jsonResponse(updated));

    const result = await updateProfile("user@test.com", {
      display_name: "New Name",
    });

    expect(result).toEqual(updated);
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/profile/user%40test.com",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: "New Name" }),
      },
    );
  });

  it("throws on non-200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 500));

    await expect(
      updateProfile("user@test.com", { display_name: "X" }),
    ).rejects.toThrow("updateProfile failed: 500");
  });
});

// ---------------------------------------------------------------------------
// requestEmailVerification
// ---------------------------------------------------------------------------

describe("requestEmailVerification", () => {
  it("resolves on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 200));

    await expect(
      requestEmailVerification("user@test.com"),
    ).resolves.toBeUndefined();
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/profile/user%40test.com/verify-email",
      { method: "POST" },
    );
  });

  it("throws on non-200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 403));

    await expect(
      requestEmailVerification("user@test.com"),
    ).rejects.toThrow("requestEmailVerification failed: 403");
  });
});
