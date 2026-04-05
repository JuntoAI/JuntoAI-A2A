import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";

// ---------------------------------------------------------------------------
// Mocks — declared before imports
// ---------------------------------------------------------------------------

vi.mock("@/components/WaitlistForm", () => ({
  default: () => createElement("div", { "data-testid": "waitlist-form" }, "WaitlistForm"),
}));

vi.mock("@/components/ScenarioBanner", () => ({
  default: () => createElement("div", { "data-testid": "scenario-banner" }, "ScenarioBanner"),
}));

vi.mock("@/lib/runMode", () => ({ isLocalMode: false }));

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn() }),
}));

import Home from "@/app/page";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Landing Page (page.tsx)", () => {
  // --- Hero section ---

  it("renders hero section with headline", () => {
    render(createElement(Home));
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("renders WaitlistForm in hero section", () => {
    render(createElement(Home));
    expect(screen.getByTestId("waitlist-form")).toBeInTheDocument();
  });

  // --- ScenarioBanner ---

  it("renders ScenarioBanner", () => {
    render(createElement(Home));
    expect(screen.getByTestId("scenario-banner")).toBeInTheDocument();
  });

  // --- Value proposition cards ---

  it("renders exactly 3 value proposition cards", () => {
    const { container } = render(createElement(Home));
    // Cards are identified by the sm:grid-cols-3 grid container's direct children
    const grid = container.querySelector(".sm\\:grid-cols-3");
    expect(grid).not.toBeNull();
    const cards = grid!.children;
    expect(cards.length).toBe(3);
  });

  it("each value proposition card has an icon, title, and description", () => {
    const { container } = render(createElement(Home));
    const grid = container.querySelector(".sm\\:grid-cols-3");
    expect(grid).not.toBeNull();

    Array.from(grid!.children).forEach((card) => {
      // Icon: SVG inside a rounded-full container
      const iconContainer = card.querySelector("svg");
      expect(iconContainer).not.toBeNull();

      // Title: h3 element
      const title = card.querySelector("h3");
      expect(title).not.toBeNull();
      expect(title!.textContent!.trim().length).toBeGreaterThan(0);

      // Description: p element
      const desc = card.querySelector("p");
      expect(desc).not.toBeNull();
      expect(desc!.textContent!.trim().length).toBeGreaterThan(0);
    });
  });

  it("value proposition cards have responsive grid classes", () => {
    const { container } = render(createElement(Home));
    const grid = container.querySelector(".sm\\:grid-cols-3");
    expect(grid).not.toBeNull();
    expect(grid!.className).toContain("grid");
  });

  // --- GitHub CTA section ---

  it("renders GitHub CTA section with heading", () => {
    render(createElement(Home));
    const heading = screen.getByText(/built in public/i);
    expect(heading).toBeInTheDocument();
  });

  it("GitHub CTA has a button linking to the correct repo URL", () => {
    render(createElement(Home));
    const link = screen.getByRole("link", { name: /view on github/i });
    expect(link).toHaveAttribute("href", "https://github.com/JuntoAI/JuntoAI-A2A");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("GitHub CTA includes a GitHub icon (SVG)", () => {
    render(createElement(Home));
    const heading = screen.getByText(/built in public/i);
    const section = heading.closest("section");
    expect(section).not.toBeNull();
    const svgs = section!.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThanOrEqual(1);
  });

  it("GitHub CTA includes supporting text about contributing", () => {
    render(createElement(Home));
    expect(screen.getByText(/clone the repo/i)).toBeInTheDocument();
  });

  // --- Container ---

  it("main container has max-width 1200px class", () => {
    const { container } = render(createElement(Home));
    const maxWidthElements = container.querySelectorAll(".max-w-\\[1200px\\]");
    expect(maxWidthElements.length).toBeGreaterThanOrEqual(1);
  });

  // --- Section order ---

  it("sections appear in correct order: hero, banner, value props, GitHub CTA", () => {
    const { container } = render(createElement(Home));
    const allElements = Array.from(container.querySelectorAll("*"));

    const waitlistForm = screen.getByTestId("waitlist-form");
    const scenarioBanner = screen.getByTestId("scenario-banner");
    const grid = container.querySelector(".sm\\:grid-cols-3")!;
    const githubHeading = screen.getByText(/built in public/i);

    const waitlistIdx = allElements.indexOf(waitlistForm);
    const bannerIdx = allElements.indexOf(scenarioBanner);
    const gridIdx = allElements.indexOf(grid);
    const githubIdx = allElements.indexOf(githubHeading);

    expect(waitlistIdx).toBeLessThan(bannerIdx);
    expect(bannerIdx).toBeLessThan(gridIdx);
    expect(gridIdx).toBeLessThan(githubIdx);
  });
});
