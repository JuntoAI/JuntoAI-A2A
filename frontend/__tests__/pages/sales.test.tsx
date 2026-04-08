import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";

// ---------------------------------------------------------------------------
// Mocks — declared before imports
// ---------------------------------------------------------------------------

vi.mock("@/components/WaitlistForm", () => ({
  default: () =>
    createElement("div", { "data-testid": "waitlist-form" }, "WaitlistForm"),
}));

vi.mock("@/lib/runMode", () => ({ isLocalMode: false }));

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn() }),
}));

import SalesPage, { metadata } from "@/app/sales/page";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Sales Landing Page (sales/page.tsx)", () => {
  // --- Hero section ---

  it("renders hero section with headline", () => {
    render(createElement(SalesPage));
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("renders WaitlistForm in hero section", () => {
    render(createElement(SalesPage));
    expect(screen.getByTestId("waitlist-form")).toBeInTheDocument();
  });

  // --- Value proposition cards ---

  it("renders at least 3 value proposition cards", () => {
    const { container } = render(createElement(SalesPage));
    const grid = container.querySelector(".sm\\:grid-cols-3");
    expect(grid).not.toBeNull();
    expect(grid!.children.length).toBeGreaterThanOrEqual(3);
  });

  // --- Scenario showcase cards ---

  it("renders 4 scenario showcase cards", () => {
    const { container } = render(createElement(SalesPage));
    const grid = container.querySelector(".sm\\:grid-cols-2");
    expect(grid).not.toBeNull();
    expect(grid!.children.length).toBe(4);
  });

  // --- CTA link to /arena ---

  it("renders CTA link with href='/arena'", () => {
    render(createElement(SalesPage));
    const link = screen.getByRole("link", { name: /open the arena/i });
    expect(link).toHaveAttribute("href", "/arena");
  });

  // --- No redirect behavior (Req 5.9) ---

  it("does not call redirect (no local-mode redirect)", async () => {
    const { redirect } = await import("next/navigation");
    render(createElement(SalesPage));
    expect(redirect).not.toHaveBeenCalled();
  });

  // --- Metadata export (Sub-task 11.2) ---

  describe("metadata export", () => {
    it("title contains sales-specific text", () => {
      expect(metadata.title).toBeDefined();
      const title =
        typeof metadata.title === "string"
          ? metadata.title
          : String(metadata.title);
      expect(title.toLowerCase()).toMatch(/sales/);
    });

    it("openGraph.title is present and sales-specific", () => {
      const og = metadata.openGraph as Record<string, unknown> | undefined;
      expect(og).toBeDefined();
      expect(og!.title).toBeDefined();
      const ogTitle = String(og!.title);
      expect(ogTitle.toLowerCase()).toMatch(/sales/);
    });

    it("openGraph.description is present and sales-specific", () => {
      const og = metadata.openGraph as Record<string, unknown> | undefined;
      expect(og).toBeDefined();
      expect(og!.description).toBeDefined();
      const ogDesc = String(og!.description);
      expect(ogDesc.toLowerCase()).toMatch(/sales|deal|negotiat/);
    });
  });
});
