import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/runMode", () => ({ isLocalMode: false }));

vi.mock("@/components/ScenarioBanner", () => ({
  default: () => createElement("div", { "data-testid": "scenario-banner" }, "ScenarioBanner"),
}));

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn() }),
}));

import OpenSourcePage from "@/app/open-source/page";

// ---------------------------------------------------------------------------
// Tests — Open Source Developer Page
// ---------------------------------------------------------------------------

describe("Open Source Page (open-source/page.tsx)", () => {
  // --- Requirement 17.2: Developer-focused hero heading ---

  it("renders developer hero heading with 'AI Negotiation Sandbox'", () => {
    render(createElement(OpenSourcePage));
    expect(screen.getByText(/ai negotiation sandbox/i)).toBeInTheDocument();
  });

  // --- Requirement 17.3: ScenarioBanner is rendered ---

  it("renders ScenarioBanner component", () => {
    render(createElement(OpenSourcePage));
    expect(screen.getByTestId("scenario-banner")).toBeInTheDocument();
  });

  // --- Requirement 17.4: 3 developer value proposition cards ---

  it("renders 3 developer value proposition cards", () => {
    render(createElement(OpenSourcePage));
    expect(screen.getByText("Not Zero-Sum")).toBeInTheDocument();
    expect(screen.getByText("Glass Box Reasoning")).toBeInTheDocument();
    expect(screen.getByText("One Toggle Changes Everything")).toBeInTheDocument();
  });

  // --- Requirement 17.5: GitHub CTA section ---

  it("renders GitHub CTA section with correct repo link", () => {
    render(createElement(OpenSourcePage));
    expect(screen.getByText(/built in public/i)).toBeInTheDocument();
    const githubLink = screen.getByRole("link", { name: /view on github/i });
    expect(githubLink).toHaveAttribute("href", "https://github.com/JuntoAI/a2a");
  });

  // --- Requirement 17.6: WaitlistForm is NOT rendered ---

  it("does not render WaitlistForm", () => {
    render(createElement(OpenSourcePage));
    expect(screen.queryByTestId("waitlist-form")).not.toBeInTheDocument();
  });
});
