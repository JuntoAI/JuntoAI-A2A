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

import SalesPersonaSetter from "@/components/SalesPersonaSetter";

// ---------------------------------------------------------------------------
// Tests — SalesPersonaSetter
// ---------------------------------------------------------------------------

describe("SalesPersonaSetter", () => {
  beforeEach(() => {
    mockSetPersona.mockClear();
  });

  it("calls setPersona('sales') on mount", () => {
    render(createElement(SalesPersonaSetter));
    expect(mockSetPersona).toHaveBeenCalledWith("sales");
    expect(mockSetPersona).toHaveBeenCalledTimes(1);
  });

  it("renders nothing (returns null)", () => {
    const { container } = render(createElement(SalesPersonaSetter));
    expect(container.innerHTML).toBe("");
  });
});
