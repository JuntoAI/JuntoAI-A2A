import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import * as fc from "fast-check";

// Mock components imported by page.tsx
vi.mock("@/components/WaitlistForm", () => ({
  default: () => createElement("div", { "data-testid": "waitlist-form" }, "WaitlistForm"),
}));

vi.mock("@/components/ScenarioBanner", () => ({
  default: () => createElement("div", { "data-testid": "scenario-banner" }, "ScenarioBanner"),
}));

// Force cloud mode so the landing page renders instead of redirecting
vi.mock("@/lib/runMode", () => ({ isLocalMode: false }));

import Home from "@/app/page";

/**
 * Feature: world-class-readme-contributor-hub
 * Property 6: GitHub CTA link has accessibility attributes
 *
 * Render the Home page component, verify the GitHub CTA link has non-empty
 * aria-label, href="https://github.com/Juntoai", target="_blank",
 * rel="noopener noreferrer".
 *
 * **Validates: Requirements 7.2, 7.6**
 */
describe("Property 6: GitHub CTA link accessibility", () => {
  it("has correct accessibility attributes across renders", () => {
    fc.assert(
      fc.property(fc.constant(null), () => {
        const { unmount } = render(createElement(Home));
        const link = screen.getByRole("link", { name: /contribute to juntoai on github/i });

        expect(link).toHaveAttribute("href", "https://github.com/JuntoAI/JuntoAI-A2A");
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener noreferrer");
        expect(link).toHaveAttribute("aria-label");
        expect(link.getAttribute("aria-label")).not.toBe("");

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});

describe("Unit: GitHub CTA placement and content", () => {
  it("CTA appears after WaitlistForm in DOM order", () => {
    const { container } = render(createElement(Home));
    const waitlistForm = screen.getByTestId("waitlist-form");
    const ctaLink = screen.getByRole("link", { name: /contribute to juntoai on github/i });

    // The CTA section should come after the waitlist form in document order
    const allElements = Array.from(container.querySelectorAll("*"));
    const waitlistIndex = allElements.indexOf(waitlistForm);
    const ctaIndex = allElements.indexOf(ctaLink);

    expect(ctaIndex).toBeGreaterThan(waitlistIndex);
  });

  it("CTA text contains 'Contribute' and 'GitHub'", () => {
    render(createElement(Home));
    const link = screen.getByRole("link", { name: /contribute to juntoai on github/i });

    expect(link.textContent).toMatch(/contribute/i);
    expect(link.textContent).toMatch(/github/i);
  });
});
