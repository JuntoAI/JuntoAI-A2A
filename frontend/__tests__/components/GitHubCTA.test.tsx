import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";

// Mock components imported by page.tsx
vi.mock("@/components/WaitlistForm", () => ({
  default: () => createElement("div", { "data-testid": "waitlist-form" }, "WaitlistForm"),
}));

vi.mock("@/components/ScenarioBanner", () => ({
  default: () => createElement("div", { "data-testid": "scenario-banner" }, "ScenarioBanner"),
}));

// Force cloud mode so the landing page renders instead of redirecting
vi.mock("@/lib/runMode", () => ({ isLocalMode: false }));

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn() }),
}));

import Home from "@/app/page";

describe("Unit: GitHub CTA placement and content", () => {
  it("CTA appears after WaitlistForm in DOM order", () => {
    const { container } = render(createElement(Home));
    const waitlistForm = screen.getByTestId("waitlist-form");
    const ctaLink = screen.getByRole("link", { name: /view on github/i });

    const allElements = Array.from(container.querySelectorAll("*"));
    const waitlistIndex = allElements.indexOf(waitlistForm);
    const ctaIndex = allElements.indexOf(ctaLink);

    expect(ctaIndex).toBeGreaterThan(waitlistIndex);
  });

  it("CTA link has correct href and opens in new tab", () => {
    render(createElement(Home));
    const link = screen.getByRole("link", { name: /view on github/i });

    expect(link).toHaveAttribute("href", "https://github.com/JuntoAI/JuntoAI-A2A");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
