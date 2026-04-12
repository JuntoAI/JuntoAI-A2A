import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks — declared before imports that reference them
// ---------------------------------------------------------------------------

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const mockLogin = vi.fn();

vi.mock("@/context/SessionContext", () => ({
  useSession: () => ({
    email: null,
    tokenBalance: 0,
    lastResetDate: null,
    tier: 1,
    dailyLimit: 20,
    isAuthenticated: false,
    isHydrated: true,
    login: mockLogin,
    logout: vi.fn(),
    updateTokenBalance: vi.fn(),
    updateTier: vi.fn(),
  }),
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const mockCheckEmail = vi.fn();
const mockLoginWithPassword = vi.fn();
const mockLoginWithGoogle = vi.fn();

vi.mock("@/lib/auth", () => ({
  checkEmail: (...args: unknown[]) => mockCheckEmail(...args),
  loginWithPassword: (...args: unknown[]) => mockLoginWithPassword(...args),
  loginWithGoogle: (...args: unknown[]) => mockLoginWithGoogle(...args),
  joinWaitlist: (...args: unknown[]) => mockJoinWaitlist(...args),
  setPassword: vi.fn(),
  changePassword: vi.fn(),
  linkGoogle: vi.fn(),
  unlinkGoogle: vi.fn(),
}));

const mockGetProfile = vi.fn();

vi.mock("@/lib/profile", () => ({
  getProfile: (...args: unknown[]) => mockGetProfile(...args),
  updateProfile: vi.fn(),
  requestEmailVerification: vi.fn(),
}));

const mockJoinWaitlist = vi.fn();

// Import component AFTER mocks
import WaitlistForm from "@/components/WaitlistForm";

// ---------------------------------------------------------------------------
// Tests — Task 15.1: WaitlistForm Component Tests
// Validates: Requirement 9.1
// ---------------------------------------------------------------------------

describe("WaitlistForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders email input and submit button", () => {
    render(<WaitlistForm />);

    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /try a free simulation/i }),
    ).toBeInTheDocument();
  });

  it("fires success callback on valid email submission", async () => {
    mockCheckEmail.mockResolvedValue({ has_password: false });
    mockJoinWaitlist.mockResolvedValue({
      email: "valid@example.com",
      tier: 1,
      daily_limit: 20,
      token_balance: 20,
    });

    render(<WaitlistForm />);

    const emailInput = screen.getByLabelText("Email address");
    await act(async () => {
      fireEvent.change(emailInput, { target: { value: "valid@example.com" } });
    });

    await act(async () => {
      fireEvent.submit(emailInput.closest("form")!);
    });

    await waitFor(() => {
      expect(mockJoinWaitlist).toHaveBeenCalledWith("valid@example.com");
    });

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith(
        "valid@example.com",
        20,
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        1,
        20,
      );
    });

    expect(mockPush).toHaveBeenCalledWith("/arena");
  });

  it("displays error message for invalid email", async () => {
    render(<WaitlistForm />);

    const emailInput = screen.getByLabelText("Email address");
    await act(async () => {
      fireEvent.change(emailInput, { target: { value: "not-valid" } });
    });

    await act(async () => {
      fireEvent.submit(emailInput.closest("form")!);
    });

    await waitFor(() => {
      expect(
        screen.getByText("Please enter a valid email address."),
      ).toBeInTheDocument();
    });

    expect(mockJoinWaitlist).not.toHaveBeenCalled();
  });

  it("displays error message on API error", async () => {
    mockCheckEmail.mockResolvedValue({ has_password: false });
    mockJoinWaitlist.mockRejectedValue(new Error("Network failure"));

    render(<WaitlistForm />);

    const emailInput = screen.getByLabelText("Email address");
    await act(async () => {
      fireEvent.change(emailInput, { target: { value: "user@example.com" } });
    });

    await act(async () => {
      fireEvent.submit(emailInput.closest("form")!);
    });

    await waitFor(() => {
      expect(
        screen.getByText("Something went wrong. Please try again."),
      ).toBeInTheDocument();
    });

    expect(mockPush).not.toHaveBeenCalled();
  });

  // --- Scenario 2: Re-login without password (existing user) ---

  it("re-login without password calls joinWaitlist and logs in", async () => {
    mockCheckEmail.mockResolvedValue({ has_password: false });
    mockJoinWaitlist.mockResolvedValue({
      email: "returning@example.com",
      tier: 2,
      daily_limit: 50,
      token_balance: 42,
    });

    render(<WaitlistForm />);

    const emailInput = screen.getByLabelText("Email address");
    await act(async () => {
      fireEvent.change(emailInput, { target: { value: "returning@example.com" } });
    });

    await act(async () => {
      fireEvent.submit(emailInput.closest("form")!);
    });

    await waitFor(() => {
      expect(mockJoinWaitlist).toHaveBeenCalledWith("returning@example.com");
    });

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith(
        "returning@example.com",
        42,
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        2,
        50,
      );
    });

    expect(mockPush).toHaveBeenCalledWith("/arena");
  });

  // --- Scenario 3: Re-login with password ---

  it("shows password field and logs in with password", async () => {
    mockCheckEmail.mockResolvedValue({ has_password: true });
    mockLoginWithPassword.mockResolvedValue({
      email: "secure@example.com",
      tier: 3,
      daily_limit: 100,
      token_balance: 88,
    });

    render(<WaitlistForm />);

    const emailInput = screen.getByLabelText("Email address");
    await act(async () => {
      fireEvent.change(emailInput, { target: { value: "secure@example.com" } });
    });

    // Trigger blur to check email
    await act(async () => {
      fireEvent.blur(emailInput);
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Password")).toBeInTheDocument();
    });

    const passwordInput = screen.getByLabelText("Password");
    await act(async () => {
      fireEvent.change(passwordInput, { target: { value: "mypassword123" } });
    });

    await act(async () => {
      fireEvent.submit(emailInput.closest("form")!);
    });

    await waitFor(() => {
      expect(mockLoginWithPassword).toHaveBeenCalledWith(
        "secure@example.com",
        "mypassword123",
      );
    });

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith(
        "secure@example.com",
        88,
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        3,
        100,
      );
    });

    expect(mockPush).toHaveBeenCalledWith("/arena");
    expect(mockJoinWaitlist).not.toHaveBeenCalled();
  });

  it("shows error on wrong password", async () => {
    mockCheckEmail.mockResolvedValue({ has_password: true });
    mockLoginWithPassword.mockRejectedValue(new Error("Invalid password"));

    render(<WaitlistForm />);

    const emailInput = screen.getByLabelText("Email address");
    await act(async () => {
      fireEvent.change(emailInput, { target: { value: "secure@example.com" } });
      fireEvent.blur(emailInput);
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Password")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.change(screen.getByLabelText("Password"), {
        target: { value: "wrongpass123" },
      });
    });

    await act(async () => {
      fireEvent.submit(emailInput.closest("form")!);
    });

    await waitFor(() => {
      expect(
        screen.getByText("Invalid password. Please try again."),
      ).toBeInTheDocument();
    });

    expect(mockPush).not.toHaveBeenCalled();
  });

  // --- Scenario: password required but not entered ---

  it("shows error when password required but empty", async () => {
    mockCheckEmail.mockResolvedValue({ has_password: true });

    render(<WaitlistForm />);

    const emailInput = screen.getByLabelText("Email address");
    await act(async () => {
      fireEvent.change(emailInput, { target: { value: "secure@example.com" } });
      fireEvent.blur(emailInput);
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Password")).toBeInTheDocument();
    });

    // Submit without entering password
    await act(async () => {
      fireEvent.submit(emailInput.closest("form")!);
    });

    await waitFor(() => {
      expect(
        screen.getByText("Please enter your password."),
      ).toBeInTheDocument();
    });

    expect(mockLoginWithPassword).not.toHaveBeenCalled();
  });
});
