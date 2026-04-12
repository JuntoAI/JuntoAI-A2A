import { render, screen, fireEvent, waitFor, act, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks — must be declared before imports that use them
// ---------------------------------------------------------------------------

const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => new URLSearchParams(),
}));

// Session context mock
const mockUpdateTier = vi.fn();
const mockLogin = vi.fn();
const mockLogout = vi.fn();

let mockSessionState: Record<string, unknown> = {
  email: "test@example.com",
  tokenBalance: 20,
  lastResetDate: "2025-01-01",
  tier: 1,
  dailyLimit: 20,
  isAuthenticated: true,
  isHydrated: true,
  login: mockLogin,
  logout: mockLogout,
  updateTokenBalance: vi.fn(),
  updateTier: mockUpdateTier,
};

vi.mock("@/context/SessionContext", () => ({
  useSession: () => mockSessionState,
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Profile API mock
const mockGetProfile = vi.fn();
const mockUpdateProfile = vi.fn();
const mockRequestEmailVerification = vi.fn();

vi.mock("@/lib/profile", () => ({
  getProfile: (...args: unknown[]) => mockGetProfile(...args),
  updateProfile: (...args: unknown[]) => mockUpdateProfile(...args),
  requestEmailVerification: (...args: unknown[]) => mockRequestEmailVerification(...args),
}));

// Auth API mock
const mockSetPassword = vi.fn();
const mockChangePassword = vi.fn();
const mockLinkGoogle = vi.fn();
const mockUnlinkGoogle = vi.fn();

vi.mock("@/lib/auth", () => ({
  setPassword: (...args: unknown[]) => mockSetPassword(...args),
  changePassword: (...args: unknown[]) => mockChangePassword(...args),
  linkGoogle: (...args: unknown[]) => mockLinkGoogle(...args),
  unlinkGoogle: (...args: unknown[]) => mockUnlinkGoogle(...args),
  checkEmail: vi.fn(),
  loginWithPassword: vi.fn(),
  loginWithGoogle: vi.fn(),
  joinWaitlist: vi.fn(),
}));

// Import component AFTER mocks
import ProfilePage from "@/app/(protected)/profile/page";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------


function makeProfile(overrides: Record<string, unknown> = {}) {
  return {
    display_name: "Test User",
    email_verified: false,
    github_url: null,
    linkedin_url: null,
    profile_completed_at: null,
    created_at: "2025-01-01T00:00:00Z",
    password_hash_set: false,
    country: null,
    google_oauth_id: null,
    tier: 1,
    daily_limit: 20,
    token_balance: 20,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests — Task 14.4: Profile Page Component Tests
// ---------------------------------------------------------------------------

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSessionState = {
      email: "test@example.com",
      tokenBalance: 20,
      lastResetDate: "2025-01-01",
      tier: 1,
      dailyLimit: 20,
      isAuthenticated: true,
      isHydrated: true,
      login: mockLogin,
      logout: mockLogout,
      updateTokenBalance: vi.fn(),
      updateTier: mockUpdateTier,
    };
  });

  // --- Validates: Requirements 2.1, 2.2, 12.1 ---
  describe("renders all profile fields", () => {
    it("displays display name, GitHub URL, LinkedIn URL, country dropdown, and Google OAuth section", async () => {
      mockGetProfile.mockResolvedValue(makeProfile());
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByLabelText("Display Name")).toBeInTheDocument();
      });

      expect(screen.getByLabelText("GitHub URL")).toBeInTheDocument();
      expect(screen.getByLabelText("LinkedIn URL")).toBeInTheDocument();
      expect(screen.getByLabelText("Country")).toBeInTheDocument();
      expect(screen.getByText("Google Account")).toBeInTheDocument();
      expect(screen.getByText("Password")).toBeInTheDocument();
    });
  });

  // --- Validates: Requirements 12.1, 12.5 ---
  describe("country dropdown", () => {
    it("renders with ISO 3166-1 alpha-2 codes and country names", async () => {
      mockGetProfile.mockResolvedValue(makeProfile());
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByLabelText("Country")).toBeInTheDocument();
      });

      const select = screen.getByLabelText("Country") as HTMLSelectElement;
      // Should have "Select a country" + all country options
      const options = Array.from(select.querySelectorAll("option"));
      expect(options.length).toBeGreaterThan(100); // 190+ countries + placeholder

      // Check a few known countries
      expect(options.some((o) => o.value === "US" && o.textContent === "United States")).toBe(true);
      expect(options.some((o) => o.value === "DE" && o.textContent === "Germany")).toBe(true);
      expect(options.some((o) => o.value === "JP" && o.textContent === "Japan")).toBe(true);
    });

    it("displays country name when a country is selected", async () => {
      mockGetProfile.mockResolvedValue(makeProfile({ country: "US" }));
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByText("Selected: United States")).toBeInTheDocument();
      });
    });
  });

  // --- Validates: Requirements 11.1, 2.3 ---
  describe("password section", () => {
    it("shows 'Set Password' when email verified and no password set", async () => {
      mockGetProfile.mockResolvedValue(
        makeProfile({ email_verified: true, password_hash_set: false }),
      );
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Set Password" })).toBeInTheDocument();
      });
    });

    it("shows 'Change Password' when password is already set", async () => {
      mockGetProfile.mockResolvedValue(
        makeProfile({ email_verified: true, password_hash_set: true }),
      );
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Change Password" })).toBeInTheDocument();
      });
    });

    it("shows message to verify email when not verified", async () => {
      mockGetProfile.mockResolvedValue(
        makeProfile({ email_verified: false, password_hash_set: false }),
      );
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByText("Verify your email to set a password.")).toBeInTheDocument();
      });
    });
  });

  // --- Validates: Requirements 13.1, 13.6 ---
  describe("Google OAuth section", () => {
    it("shows 'Link Google Account' when email verified and no Google linked", async () => {
      mockGetProfile.mockResolvedValue(
        makeProfile({ email_verified: true, google_oauth_id: null }),
      );
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Link Google Account/i })).toBeInTheDocument();
      });
    });

    it("shows linked info and 'Unlink Google Account' when Google is linked", async () => {
      mockGetProfile.mockResolvedValue(
        makeProfile({ email_verified: true, google_oauth_id: "google-sub-12345678" }),
      );
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByText(/Google account linked/)).toBeInTheDocument();
      });
      expect(screen.getByRole("button", { name: /Unlink Google Account/i })).toBeInTheDocument();
    });

    it("shows message to verify email when not verified", async () => {
      mockGetProfile.mockResolvedValue(
        makeProfile({ email_verified: false, google_oauth_id: null }),
      );
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByText("Verify your email to link a Google account.")).toBeInTheDocument();
      });
    });
  });

  // --- Validates: Requirements 2.4, 8.4 ---
  describe("save triggers API call and updates session context on tier upgrade", () => {
    it("calls updateProfile and updateTier on save", async () => {
      const initialProfile = makeProfile({ email_verified: true });
      const updatedProfile = makeProfile({
        email_verified: true,
        display_name: "Updated Name",
        github_url: "https://github.com/testuser",
        tier: 3,
        daily_limit: 100,
        token_balance: 100,
        profile_completed_at: "2025-01-01T00:00:00Z",
      });

      mockGetProfile.mockResolvedValue(initialProfile);
      mockUpdateProfile.mockResolvedValue(updatedProfile);

      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByLabelText("Display Name")).toBeInTheDocument();
      });

      // Click save
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: /Save Profile/i }));
      });

      await waitFor(() => {
        expect(mockUpdateProfile).toHaveBeenCalledWith("test@example.com", {
          display_name: "Test User",
          github_url: null,
          linkedin_url: null,
          country: null,
        });
      });

      expect(mockUpdateTier).toHaveBeenCalledWith(3, 100, 100);
    });
  });

  // --- Validates: Requirements 4.7, 2.3 ---
  describe("email verification button visibility", () => {
    it("shows 'Verify Email' button when email is not verified", async () => {
      mockGetProfile.mockResolvedValue(makeProfile({ email_verified: false }));
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Verify Email/i })).toBeInTheDocument();
      });
    });

    it("shows 'Verified' badge when email is already verified", async () => {
      mockGetProfile.mockResolvedValue(makeProfile({ email_verified: true }));
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByText("Verified")).toBeInTheDocument();
      });
      expect(screen.queryByRole("button", { name: /Verify Email/i })).not.toBeInTheDocument();
    });
  });

  // --- Validates: Requirements 2.5 ---
  describe("unauthenticated redirect", () => {
    it("redirects to landing page when not authenticated", async () => {
      mockSessionState = {
        ...mockSessionState,
        isAuthenticated: false,
        isHydrated: true,
        email: null,
      };

      render(<ProfilePage />);

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalledWith("/");
      });
    });
  });

  // --- Validates: Requirements 2.4 ---
  describe("progress indicator", () => {
    it("shows completion steps", async () => {
      mockGetProfile.mockResolvedValue(
        makeProfile({
          email_verified: true,
          display_name: "Test User",
          github_url: "https://github.com/testuser",
        }),
      );
      render(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByText(/Profile completion: 3 \/ 3/)).toBeInTheDocument();
      });

      expect(screen.getByText("Email verified")).toBeInTheDocument();
      expect(screen.getByText("Display name set")).toBeInTheDocument();
      expect(screen.getByText("Professional link added")).toBeInTheDocument();
    });
  });
});
