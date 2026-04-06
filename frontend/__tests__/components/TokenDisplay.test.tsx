import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks — declared before imports that reference them
// ---------------------------------------------------------------------------

const sessionDefaults = {
  email: "user@example.com",
  lastResetDate: "2025-01-01",
  tier: 1,
  isAuthenticated: true,
  isHydrated: true,
  login: vi.fn(),
  logout: vi.fn(),
  updateTokenBalance: vi.fn(),
  updateTier: vi.fn(),
};

let mockTokenBalance = 50;
let mockDailyLimit = 100;

vi.mock("@/context/SessionContext", () => ({
  useSession: () => ({
    ...sessionDefaults,
    tokenBalance: mockTokenBalance,
    dailyLimit: mockDailyLimit,
  }),
}));

let mockIsLocalMode = false;

vi.mock("@/lib/runMode", () => ({
  get isLocalMode() {
    return mockIsLocalMode;
  },
}));

vi.mock("@/lib/tokens", () => ({
  formatTokenDisplay: (balance: number, dailyLimit: number) =>
    `Tokens: ${Math.max(0, balance)} / ${dailyLimit}`,
}));

// Import component AFTER mocks
import TokenDisplay from "@/components/TokenDisplay";

// ---------------------------------------------------------------------------
// Tests — Task 15.2: TokenDisplay Component Tests
// Validates: Requirement 9.2
// ---------------------------------------------------------------------------

describe("TokenDisplay", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTokenBalance = 50;
    mockDailyLimit = 100;
    mockIsLocalMode = false;
  });

  it("renders token count (e.g. 50)", () => {
    mockTokenBalance = 50;
    mockDailyLimit = 100;
    render(<TokenDisplay />);

    expect(screen.getByText("Tokens: 50 / 100")).toBeInTheDocument();
  });

  it("renders with 0 tokens", () => {
    mockTokenBalance = 0;
    mockDailyLimit = 100;
    render(<TokenDisplay />);

    expect(screen.getByText("Tokens: 0 / 100")).toBeInTheDocument();
  });

  it("handles negative token balance gracefully (clamps to 0)", () => {
    mockTokenBalance = -5;
    mockDailyLimit = 100;
    render(<TokenDisplay />);

    expect(screen.getByText("Tokens: 0 / 100")).toBeInTheDocument();
  });

  it("renders 'Unlimited' in local mode", () => {
    mockIsLocalMode = true;
    render(<TokenDisplay />);

    expect(screen.getByText("Unlimited")).toBeInTheDocument();
  });
});
