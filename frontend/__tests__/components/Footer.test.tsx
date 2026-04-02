import { describe, it, expect } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { createElement } from "react";
import * as fc from "fast-check";
import Footer from "@/components/Footer";

/**
 * Feature: world-class-readme-contributor-hub
 * Property 7: Footer GitHub link has correct attributes
 *
 * Render Footer component, verify GitHub link has aria-label="GitHub",
 * href="https://github.com/Juntoai", target="_blank",
 * rel="noopener noreferrer", and contains an SVG with h-4 w-4 class
 * and fill="currentColor".
 *
 * **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
 */
describe("Property 7: Footer GitHub link attributes", () => {
  it("has correct attributes across renders", { timeout: 30_000 }, () => {
    fc.assert(
      fc.property(fc.constant(null), () => {
        cleanup();
        render(createElement(Footer));
        const link = screen.getByRole("link", { name: "GitHub" });

        expect(link).toHaveAttribute("href", "https://github.com/juntoai");
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener noreferrer");
        expect(link).toHaveAttribute("aria-label", "GitHub");

        // Verify SVG inside the link
        const svg = link.querySelector("svg");
        expect(svg).not.toBeNull();
        expect(svg!.classList.contains("h-4")).toBe(true);
        expect(svg!.classList.contains("w-4")).toBe(true);
        expect(svg!.getAttribute("fill")).toBe("currentColor");

        cleanup();
      }),
      { numRuns: 100 },
    );
  });
});

describe("Unit: Footer social icon order", () => {
  it("renders three social icons in order: LinkedIn, GitHub, X", () => {
    render(createElement(Footer));

    const linkedin = screen.getByRole("link", { name: "LinkedIn" });
    const github = screen.getByRole("link", { name: "GitHub" });
    const xTwitter = screen.getByRole("link", { name: /X \(Twitter\)/i });

    // All three should exist
    expect(linkedin).toBeInTheDocument();
    expect(github).toBeInTheDocument();
    expect(xTwitter).toBeInTheDocument();

    // Verify order: LinkedIn before GitHub before X
    const socialContainer = linkedin.parentElement!;
    const links = Array.from(socialContainer.querySelectorAll("a[aria-label]"));
    const ariaLabels = links.map((el) => el.getAttribute("aria-label"));

    const linkedinIdx = ariaLabels.indexOf("LinkedIn");
    const githubIdx = ariaLabels.indexOf("GitHub");
    const xIdx = ariaLabels.findIndex((l) => l?.includes("X"));

    expect(linkedinIdx).toBeLessThan(githubIdx);
    expect(githubIdx).toBeLessThan(xIdx);
  });
});
