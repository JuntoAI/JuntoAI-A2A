import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock window.location for redirect testing
const originalLocation = window.location;

beforeEach(() => {
  Object.defineProperty(window, "location", {
    writable: true,
    value: { ...originalLocation, href: "" },
  });
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import AdminLoginPage from "@/app/admin/login/page";

// ---------------------------------------------------------------------------
// Tests — Validates: Requirements 2.2, 2.3
// ---------------------------------------------------------------------------

describe("AdminLoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("renders password input and submit button", () => {
    render(<AdminLoginPage />);

    expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("renders the Admin Login heading", () => {
    render(<AdminLoginPage />);

    expect(screen.getByText("Admin Login")).toBeInTheDocument();
  });

  // Validates: Requirement 2.2 — correct password redirects to /admin
  it("redirects to /admin on successful login", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200 });

    render(<AdminLoginPage />);

    const passwordInput = screen.getByPlaceholderText("Password");
    const submitButton = screen.getByRole("button", { name: /sign in/i });

    await act(async () => {
      fireEvent.change(passwordInput, { target: { value: "correct-password" } });
    });

    await act(async () => {
      fireEvent.click(submitButton);
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/admin/login"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ password: "correct-password" }),
        }),
      );
    });

    await waitFor(() => {
      expect(window.location.href).toBe("/admin");
    });
  });

  // Validates: Requirement 2.3 — wrong password shows "Invalid password"
  it("displays 'Invalid password' on failed login", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });

    render(<AdminLoginPage />);

    const passwordInput = screen.getByPlaceholderText("Password");
    const submitButton = screen.getByRole("button", { name: /sign in/i });

    await act(async () => {
      fireEvent.change(passwordInput, { target: { value: "wrong-password" } });
    });

    await act(async () => {
      fireEvent.click(submitButton);
    });

    await waitFor(() => {
      expect(screen.getByText("Invalid password")).toBeInTheDocument();
    });
  });

  it("displays rate limit message on 429 response", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 429 });

    render(<AdminLoginPage />);

    const passwordInput = screen.getByPlaceholderText("Password");

    await act(async () => {
      fireEvent.change(passwordInput, { target: { value: "any-password" } });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/too many login attempts/i)).toBeInTheDocument();
    });
  });

  it("displays network error message when fetch throws", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network failure"));

    render(<AdminLoginPage />);

    const passwordInput = screen.getByPlaceholderText("Password");

    await act(async () => {
      fireEvent.change(passwordInput, { target: { value: "any-password" } });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/unable to reach the server/i)).toBeInTheDocument();
    });
  });

  it("shows loading state while submitting", async () => {
    let resolvePromise: (value: unknown) => void;
    const pendingPromise = new Promise((resolve) => { resolvePromise = resolve; });
    global.fetch = vi.fn().mockReturnValue(pendingPromise);

    render(<AdminLoginPage />);

    const passwordInput = screen.getByPlaceholderText("Password");

    await act(async () => {
      fireEvent.change(passwordInput, { target: { value: "test" } });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    });

    expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();

    // Resolve to clean up
    await act(async () => {
      resolvePromise!({ ok: true, status: 200 });
    });
  });
});
