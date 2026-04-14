import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { createElement, type ReactNode } from "react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSetPersona = vi.fn();

vi.mock("@/context/SessionContext", () => ({
  useSession: () => ({
    email: null,
    tokenBalance: 0,
    lastResetDate: null,
    tier: 1,
    dailyLimit: 20,
    isAuthenticated: false,
    isHydrated: true,
    persona: null,
    login: vi.fn(),
    logout: vi.fn(),
    updateTokenBalance: vi.fn(),
    updateTier: vi.fn(),
    setPersona: mockSetPersona,
  }),
  SessionProvider: ({ children }: { children: ReactNode }) => createElement("div", null, children),
}));

import FoundersPersonaSetter from "@/components/FoundersPersonaSetter";

// ---------------------------------------------------------------------------
// Tests — FoundersPersonaSetter
// ---------------------------------------------------------------------------

describe("FoundersPersonaSetter", () => {
  beforeEach(() => {
    mockSetPersona.mockClear();
  });

  it("calls setPersona('founder') on mount", () => {
    render(createElement(FoundersPersonaSetter));
    expect(mockSetPersona).toHaveBeenCalledWith("founder");
    expect(mockSetPersona).toHaveBeenCalledTimes(1);
  });

  it("renders nothing (returns null)", () => {
    const { container } = render(createElement(FoundersPersonaSetter));
    expect(container.innerHTML).toBe("");
  });
});
