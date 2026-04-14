import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { createElement, type ReactNode } from "react";

// Mock runMode to cloud so SessionContext uses sessionStorage-based auth
vi.mock("../../lib/runMode", () => ({ isLocalMode: false }));

import { SessionProvider, useSession } from "../../context/SessionContext";

function wrapper({ children }: { children: ReactNode }) {
  return createElement(SessionProvider, null, children);
}

describe("SessionContext (cloud mode)", () => {
  beforeEach(() => {
    sessionStorage.clear();
    // Clear cookies
    document.cookie = "junto_session=; max-age=0; path=/";
  });

  it("provides default unauthenticated state", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.email).toBeNull();
    expect(result.current.tokenBalance).toBe(0);
    expect(result.current.lastResetDate).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.persona).toBeNull();
  });

  it("login() sets state, sessionStorage, and cookie", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.login("test@example.com", 85, "2025-01-15");
    });

    expect(result.current.email).toBe("test@example.com");
    expect(result.current.tokenBalance).toBe(85);
    expect(result.current.lastResetDate).toBe("2025-01-15");
    expect(result.current.isAuthenticated).toBe(true);

    expect(sessionStorage.getItem("junto_email")).toBe("test@example.com");
    expect(sessionStorage.getItem("junto_token_balance")).toBe("85");
    expect(sessionStorage.getItem("junto_last_reset")).toBe("2025-01-15");

    expect(document.cookie).toContain("junto_session=1");
  });

  it("logout() clears state, sessionStorage, and cookie", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.login("test@example.com", 50, "2025-01-15");
    });
    act(() => {
      result.current.logout();
    });

    expect(result.current.email).toBeNull();
    expect(result.current.tokenBalance).toBe(0);
    expect(result.current.lastResetDate).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    // isHydrated must stay true so the protected layout redirect fires
    expect(result.current.isHydrated).toBe(true);

    expect(sessionStorage.getItem("junto_email")).toBeNull();
    expect(sessionStorage.getItem("junto_token_balance")).toBeNull();
    expect(sessionStorage.getItem("junto_last_reset")).toBeNull();

    expect(document.cookie).not.toContain("junto_session=1");
  });

  it("updateTokenBalance() updates state and sessionStorage", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.login("test@example.com", 100, "2025-01-15");
    });
    act(() => {
      result.current.updateTokenBalance(73);
    });

    expect(result.current.tokenBalance).toBe(73);
    expect(sessionStorage.getItem("junto_token_balance")).toBe("73");
    // Other state unchanged
    expect(result.current.email).toBe("test@example.com");
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("restores state from sessionStorage on mount", () => {
    sessionStorage.setItem("junto_email", "restored@example.com");
    sessionStorage.setItem("junto_token_balance", "42");
    sessionStorage.setItem("junto_last_reset", "2025-06-01");

    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.email).toBe("restored@example.com");
    expect(result.current.tokenBalance).toBe(42);
    expect(result.current.lastResetDate).toBe("2025-06-01");
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("restores with zero balance when sessionStorage has email but no balance", () => {
    sessionStorage.setItem("junto_email", "user@example.com");

    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.email).toBe("user@example.com");
    expect(result.current.tokenBalance).toBe(0);
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("does not restore when sessionStorage has no email", () => {
    sessionStorage.setItem("junto_token_balance", "50");

    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.email).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("useSession() throws when used outside SessionProvider", () => {
    expect(() => {
      renderHook(() => useSession());
    }).toThrow("useSession must be used within a SessionProvider");
  });

  // --- Persona tests ---

  it("setPersona() updates state and sessionStorage", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.setPersona("founder");
    });

    expect(result.current.persona).toBe("founder");
    expect(sessionStorage.getItem("junto_persona")).toBe("founder");
  });

  it("setPersona() can switch between personas", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.setPersona("sales");
    });
    expect(result.current.persona).toBe("sales");
    expect(sessionStorage.getItem("junto_persona")).toBe("sales");

    act(() => {
      result.current.setPersona("founder");
    });
    expect(result.current.persona).toBe("founder");
    expect(sessionStorage.getItem("junto_persona")).toBe("founder");
  });

  it("setPersona(null) clears persona from state and sessionStorage", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.setPersona("sales");
    });
    act(() => {
      result.current.setPersona(null);
    });

    expect(result.current.persona).toBeNull();
    expect(sessionStorage.getItem("junto_persona")).toBeNull();
  });

  it("logout() clears persona from state and sessionStorage", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.setPersona("founder");
    });
    expect(result.current.persona).toBe("founder");

    act(() => {
      result.current.logout();
    });

    expect(result.current.persona).toBeNull();
    expect(sessionStorage.getItem("junto_persona")).toBeNull();
  });

  it("restores persona from sessionStorage on mount", () => {
    sessionStorage.setItem("junto_email", "user@example.com");
    sessionStorage.setItem("junto_token_balance", "50");
    sessionStorage.setItem("junto_last_reset", "2025-06-01");
    sessionStorage.setItem("junto_persona", "founder");

    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.persona).toBe("founder");
    expect(result.current.email).toBe("user@example.com");
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("restores persona even without email (unauthenticated with persona)", () => {
    sessionStorage.setItem("junto_persona", "sales");

    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.persona).toBe("sales");
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("login() preserves persona that was set before authentication", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.setPersona("founder");
    });
    expect(result.current.persona).toBe("founder");

    act(() => {
      result.current.login("test@example.com", 100, "2025-01-15");
    });

    expect(result.current.persona).toBe("founder");
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("persona defaults to null when no persona is stored", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.persona).toBeNull();
  });
});
