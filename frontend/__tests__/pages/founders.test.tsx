import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/runMode", () => ({ isLocalMode: false }));

vi.mock("@/components/WaitlistForm", () => ({
  default: () => createElement("div", { "data-testid": "waitlist-form" }, "WaitlistForm"),
}));

vi.mock("@/components/FoundersPersonaSetter", () => ({
  default: () => createElement("div", { "data-testid": "founders-persona-setter" }),
}));

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn() }),
}));

import FoundersPage from "@/app/founders/page";
import { metadata } from "@/app/founders/page";

// ---------------------------------------------------------------------------
// Tests — Founders Landing Page
// ---------------------------------------------------------------------------

describe("Founders Landing Page (founders/page.tsx)", () => {
  // --- Requirement 2.2: Hero section ---

  it("renders hero heading with 'Rehearse Your Pitch'", () => {
    render(createElement(FoundersPage));
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(/rehearse your pitch/i);
  });

  it("renders hero heading with 'Negotiate with Confidence'", () => {
    render(createElement(FoundersPage));
    expect(screen.getByText(/negotiate with confidence/i)).toBeInTheDocument();
  });

  it("renders hero subheadline about investor meetings", () => {
    render(createElement(FoundersPage));
    expect(screen.getByText(/simulate investor meetings/i)).toBeInTheDocument();
  });

  // --- Requirement 2.3: Value proposition cards ---

  it("renders 3 founder value proposition cards", () => {
    render(createElement(FoundersPage));
    expect(screen.getByText("Pitch Simulation")).toBeInTheDocument();
    // "Term Sheet Negotiation" appears in both value props and scenarios
    expect(screen.getAllByText("Term Sheet Negotiation")).toHaveLength(2);
    expect(screen.getByText("Investor Objection Handling")).toBeInTheDocument();
  });

  // --- Requirement 2.4: Scenario showcase cards ---

  it("renders 4 founder scenario showcase cards", () => {
    render(createElement(FoundersPage));
    expect(screen.getByText("Startup Pitch")).toBeInTheDocument();
    expect(screen.getByText("Co-Founder Equity Split")).toBeInTheDocument();
    // "Term Sheet Negotiation" already verified above
    expect(screen.getByText("M&A Buyout")).toBeInTheDocument();
  });

  it("renders scenario showcase heading", () => {
    render(createElement(FoundersPage));
    expect(screen.getByText(/four founder scenarios/i)).toBeInTheDocument();
  });

  // --- Requirement 2.5: WaitlistForm ---

  it("renders WaitlistForm", () => {
    render(createElement(FoundersPage));
    expect(screen.getByTestId("waitlist-form")).toBeInTheDocument();
  });

  // --- Requirement 2.6: CTA linking to Arena ---

  it("renders CTA linking to /arena", () => {
    render(createElement(FoundersPage));
    const ctaLink = screen.getByRole("link", { name: /try a free simulation/i });
    expect(ctaLink).toHaveAttribute("href", "/arena");
  });

  // --- Requirement 2.8: SEO metadata ---

  it("exports metadata with founder-focused SEO", () => {
    expect(metadata).toBeDefined();
    expect(metadata.title).toContain("Founders");
    expect(metadata.description).toBeTruthy();
    expect(metadata.openGraph).toBeDefined();
    expect((metadata.openGraph as Record<string, unknown>).url).toBe("/founders");
    expect(metadata.alternates?.canonical).toBe("/founders");
  });

  // --- Requirement 1.1: FoundersPersonaSetter is rendered ---

  it("renders FoundersPersonaSetter component", () => {
    render(createElement(FoundersPage));
    expect(screen.getByTestId("founders-persona-setter")).toBeInTheDocument();
  });

  // --- Does NOT contain sales-specific content ---

  it("does not render sales-specific content", () => {
    render(createElement(FoundersPage));
    expect(screen.queryByText(/rehearse your next deal/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Objection Handling")).not.toBeInTheDocument();
  });
});
