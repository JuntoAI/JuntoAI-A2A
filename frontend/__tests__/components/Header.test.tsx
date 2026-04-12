import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { createElement } from "react";

// ---------------------------------------------------------------------------
// Mocks — declared before imports
// ---------------------------------------------------------------------------

let mockSessionState: {
  email: string | null;
  tokenBalance: number;
  lastResetDate: string | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  login: ReturnType<typeof vi.fn>;
  logout: ReturnType<typeof vi.fn>;
  updateTokenBalance: ReturnType<typeof vi.fn>;
};

vi.mock("@/context/SessionContext", () => ({
  useSession: () => mockSessionState,
}));

let mockPathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), forward: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
}));

vi.mock("@/components/TokenDisplay", () => ({
  default: () => createElement("div", { "data-testid": "token-display" }, "50 tokens"),
}));

vi.mock("next/image", () => ({
  default: (props: Record<string, unknown>) =>
    createElement("img", {
      src: props.src,
      alt: props.alt,
      width: props.width,
      height: props.height,
      "data-testid": "header-logo",
    }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));

import Header from "@/components/Header";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Header Component", () => {
  beforeEach(() => {
    cleanup();
    mockPathname = "/";
    mockSessionState = {
      email: null,
      tokenBalance: 0,
      lastResetDate: null,
      isAuthenticated: false,
      isHydrated: true,
      login: vi.fn(),
      logout: vi.fn(),
      updateTokenBalance: vi.fn(),
    };
  });

  // --- Logo rendering ---

  it("renders logo image with correct src and alt text", () => {
    render(createElement(Header));
    const logo = screen.getByTestId("header-logo");
    expect(logo).toHaveAttribute("src", "/juntoai_logo_500x500.png");
    expect(logo).toHaveAttribute("alt", "JuntoAI logo");
  });

  it("renders product name text next to logo", () => {
    render(createElement(Header));
    expect(screen.getByText("JuntoAI A2A")).toBeInTheDocument();
  });

  it("logo links to home page", () => {
    render(createElement(Header));
    const logo = screen.getByTestId("header-logo");
    const link = logo.closest("a");
    expect(link).toHaveAttribute("href", "/");
  });

  it("logo height does not exceed 40px", () => {
    render(createElement(Header));
    const logo = screen.getByTestId("header-logo");
    const height = Number(logo.getAttribute("height"));
    expect(height).toBeLessThanOrEqual(40);
  });

  // --- Navigation links ---

  it("contains link to juntoai.org", () => {
    render(createElement(Header));
    const links = screen.getAllByRole("link").filter(
      (el) => el.getAttribute("href") === "https://juntoai.org",
    );
    expect(links.length).toBeGreaterThanOrEqual(1);
  });

  it("does not contain GitHub link in header nav", () => {
    render(createElement(Header));
    const links = screen.queryAllByRole("link").filter(
      (el) => el.getAttribute("href") === "https://github.com/JuntoAI/JuntoAI-A2A",
    );
    expect(links.length).toBe(0);
  });

  // --- Positioning ---

  it("has sticky top-0 z-50 positioning classes", () => {
    const { container } = render(createElement(Header));
    const header = container.querySelector("header");
    expect(header).not.toBeNull();
    expect(header!.className).toContain("sticky");
    expect(header!.className).toContain("top-0");
    expect(header!.className).toContain("z-50");
  });

  // --- Unauthenticated state ---

  it("does not show waitlist CTA in header", () => {
    mockSessionState.isAuthenticated = false;
    mockSessionState.isHydrated = true;
    render(createElement(Header));
    expect(screen.queryByText(/join waitlist/i)).not.toBeInTheDocument();
  });

  // --- Authenticated state ---

  it("shows email, token display, and logout button when authenticated", () => {
    mockSessionState.email = "test@example.com";
    mockSessionState.tokenBalance = 50;
    mockSessionState.isAuthenticated = true;
    mockSessionState.isHydrated = true;
    render(createElement(Header));

    expect(screen.getByText("test@example.com")).toBeInTheDocument();
    expect(screen.getByTestId("token-display")).toBeInTheDocument();
    expect(screen.getByLabelText("Logout")).toBeInTheDocument();
  });

  it("does not show waitlist CTA when authenticated either", () => {
    mockSessionState.email = "test@example.com";
    mockSessionState.isAuthenticated = true;
    mockSessionState.isHydrated = true;
    render(createElement(Header));
    expect(screen.queryByText(/join waitlist/i)).not.toBeInTheDocument();
  });

  // --- Arena route: no external links ---

  it("hides JuntoAI and GitHub links on /arena", () => {
    mockPathname = "/arena";
    render(createElement(Header));
    const juntoLinks = screen.queryAllByRole("link").filter(
      (el) => el.getAttribute("href") === "https://juntoai.org",
    );
    const ghLinks = screen.queryAllByRole("link").filter(
      (el) => el.getAttribute("href") === "https://github.com/JuntoAI/JuntoAI-A2A",
    );
    expect(juntoLinks.length).toBe(0);
    expect(ghLinks.length).toBe(0);
  });
});
