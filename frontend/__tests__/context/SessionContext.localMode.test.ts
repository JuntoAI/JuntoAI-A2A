import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { createElement, type ReactNode } from "react";

// Mock runMode to local so SessionContext uses local mode defaults
vi.mock("../../lib/runMode", () => ({ isLocalMode: true }));

import { SessionProvider, useSession } from "../../context/SessionContext";

function wrapper({ children }: { children: ReactNode }) {
  return createElement(SessionProvider, null, children);
}

describe("SessionContext (local mode) — persona", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("defaults persona to 'sales' in local mode", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.persona).toBe("sales");
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.email).toBe("local@dev");
  });

  it("restores persona from sessionStorage in local mode when overridden", () => {
    sessionStorage.setItem("junto_persona", "founder");

    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.persona).toBe("founder");
  });

  it("setPersona() works in local mode", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    expect(result.current.persona).toBe("sales");

    act(() => {
      result.current.setPersona("founder");
    });

    expect(result.current.persona).toBe("founder");
    expect(sessionStorage.getItem("junto_persona")).toBe("founder");
  });
});
