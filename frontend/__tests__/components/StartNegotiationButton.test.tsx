import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks — declared before imports that reference them
// ---------------------------------------------------------------------------

const sessionDefaults = {
  email: "user@example.com",
  lastResetDate: "2025-01-01",
  tier: 1,
  dailyLimit: 100,
  isAuthenticated: true,
  isHydrated: true,
  login: vi.fn(),
  logout: vi.fn(),
  updateTokenBalance: vi.fn(),
  updateTier: vi.fn(),
};

let mockTokenBalance = 10;

vi.mock("@/context/SessionContext", () => ({
  useSession: () => ({
    ...sessionDefaults,
    tokenBalance: mockTokenBalance,
  }),
}));

// Import component AFTER mocks
import StartNegotiationButton from "@/components/StartNegotiationButton";

// ---------------------------------------------------------------------------
// Tests — Task 15.3: StartNegotiationButton Component Tests
// Validates: Requirement 9.3
// ---------------------------------------------------------------------------

describe("StartNegotiationButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTokenBalance = 10;
  });

  it("renders enabled button when tokens > 0", () => {
    mockTokenBalance = 5;
    render(<StartNegotiationButton />);

    const button = screen.getByRole("button", { name: /initialize a2a protocol/i });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it("renders disabled button when tokens = 0", () => {
    mockTokenBalance = 0;
    render(<StartNegotiationButton />);

    const button = screen.getByRole("button", { name: /initialize a2a protocol/i });
    expect(button).toBeDisabled();
    expect(screen.getByText(/no tokens remaining/i)).toBeInTheDocument();
  });

  it("click fires on enabled button", () => {
    mockTokenBalance = 5;
    render(<StartNegotiationButton />);

    const button = screen.getByRole("button", { name: /initialize a2a protocol/i });
    // Should not throw — the onClick is a placeholder but the button is clickable
    fireEvent.click(button);
    expect(button).not.toBeDisabled();
  });
});
