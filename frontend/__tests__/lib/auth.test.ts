import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  checkEmail,
  loginWithPassword,
  loginWithGoogle,
  setPassword,
  changePassword,
  linkGoogle,
  unlinkGoogle,
} from "@/lib/auth";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

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
// checkEmail
// ---------------------------------------------------------------------------

describe("checkEmail", () => {
  it("returns { has_password } on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ has_password: true }));

    const result = await checkEmail("user@test.com");

    expect(result).toEqual({ has_password: true });
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/auth/check-email/user%40test.com",
    );
  });

  it("throws on non-200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 404));

    await expect(checkEmail("nobody@test.com")).rejects.toThrow(
      "check-email failed: 404",
    );
  });
});

// ---------------------------------------------------------------------------
// loginWithPassword
// ---------------------------------------------------------------------------

describe("loginWithPassword", () => {
  const loginResponse = {
    email: "user@test.com",
    tier: 0,
    daily_limit: 100,
    token_balance: 95,
  };

  it("returns LoginResponse on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(loginResponse));

    const result = await loginWithPassword("user@test.com", "secret123");

    expect(result).toEqual(loginResponse);
    expect(fetchSpy).toHaveBeenCalledWith("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "user@test.com", password: "secret123" }),
    });
  });

  it("throws 'Invalid password' on 401", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 401));

    await expect(
      loginWithPassword("user@test.com", "wrong"),
    ).rejects.toThrow("Invalid password");
  });

  it("throws generic error on other non-200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 500));

    await expect(
      loginWithPassword("user@test.com", "pw"),
    ).rejects.toThrow("login failed: 500");
  });
});


// ---------------------------------------------------------------------------
// loginWithGoogle
// ---------------------------------------------------------------------------

describe("loginWithGoogle", () => {
  const loginResponse = {
    email: "guser@test.com",
    tier: 0,
    daily_limit: 100,
    token_balance: 80,
  };

  it("returns LoginResponse on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(loginResponse));

    const result = await loginWithGoogle("google-id-token-abc");

    expect(result).toEqual(loginResponse);
    expect(fetchSpy).toHaveBeenCalledWith("/api/v1/auth/google/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: "google-id-token-abc" }),
    });
  });

  it("throws specific message on 404", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 404));

    await expect(loginWithGoogle("token")).rejects.toThrow(
      "No linked account found for this Google account",
    );
  });

  it("throws generic error on other non-200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 503));

    await expect(loginWithGoogle("token")).rejects.toThrow(
      "Google login failed: 503",
    );
  });
});

// ---------------------------------------------------------------------------
// setPassword
// ---------------------------------------------------------------------------

describe("setPassword", () => {
  it("resolves on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 200));

    await expect(setPassword("user@test.com", "newpw")).resolves.toBeUndefined();
  });

  it("throws with detail from body on non-200", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ detail: "Password too short" }, 400),
    );

    await expect(setPassword("user@test.com", "x")).rejects.toThrow(
      "Password too short",
    );
  });

  it("throws with status fallback when body has no detail", async () => {
    fetchSpy.mockResolvedValueOnce(
      new Response("not json", { status: 500 }),
    );

    await expect(setPassword("user@test.com", "pw")).rejects.toThrow(
      "set-password failed: 500",
    );
  });
});

// ---------------------------------------------------------------------------
// changePassword
// ---------------------------------------------------------------------------

describe("changePassword", () => {
  it("resolves on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 200));

    await expect(
      changePassword("user@test.com", "old", "new"),
    ).resolves.toBeUndefined();
  });

  it("throws 'Invalid current password' on 401", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 401));

    await expect(
      changePassword("user@test.com", "wrong", "new"),
    ).rejects.toThrow("Invalid current password");
  });

  it("throws with detail from body on other non-200", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ detail: "Validation error" }, 422),
    );

    await expect(
      changePassword("user@test.com", "old", "short"),
    ).rejects.toThrow("Validation error");
  });

  it("throws with status fallback when body is not JSON", async () => {
    fetchSpy.mockResolvedValueOnce(
      new Response("bad", { status: 500 }),
    );

    await expect(
      changePassword("user@test.com", "old", "new"),
    ).rejects.toThrow("change-password failed: 500");
  });
});

// ---------------------------------------------------------------------------
// linkGoogle
// ---------------------------------------------------------------------------

describe("linkGoogle", () => {
  it("returns response on 200", async () => {
    const body = { google_oauth_id: "g123", google_email: "g@test.com" };
    fetchSpy.mockResolvedValueOnce(jsonResponse(body));

    const result = await linkGoogle("id-token", "user@test.com");

    expect(result).toEqual(body);
    expect(fetchSpy).toHaveBeenCalledWith("/api/v1/auth/google/link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: "id-token", email: "user@test.com" }),
    });
  });

  it("throws 'already linked' on 409", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 409));

    await expect(linkGoogle("token", "user@test.com")).rejects.toThrow(
      "Google account already linked to another profile",
    );
  });

  it("throws generic error on other non-200", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ detail: "Server error" }, 500),
    );

    await expect(linkGoogle("token", "user@test.com")).rejects.toThrow(
      "Server error",
    );
  });
});

// ---------------------------------------------------------------------------
// unlinkGoogle
// ---------------------------------------------------------------------------

describe("unlinkGoogle", () => {
  it("resolves on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 200));

    await expect(unlinkGoogle("user@test.com")).resolves.toBeUndefined();
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/auth/google/link/user%40test.com",
      { method: "DELETE" },
    );
  });

  it("throws on non-200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, 500));

    await expect(unlinkGoogle("user@test.com")).rejects.toThrow(
      "unlink-google failed: 500",
    );
  });
});
