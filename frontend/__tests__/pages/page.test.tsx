import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/components/WaitlistForm", () => ({
  default: () => createElement("div", { "data-testid": "waitlist-form" }, "WaitlistForm"),
}));

vi.mock("@/lib/runMode", () => ({ isLocalMode: false }));

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn() }),
}));

import Home from "@/app/page";

// ---------------------------------------------------------------------------
// Tests — Sales-Focused Homepage
// ---------------------------------------------------------------------------

describe("Sales-Focused Homepage (page.tsx)", () => {
  // --- Requirement 16.1: Sales hero heading ---

  it("renders hero heading with 'Rehearse Your Next Deal'", () => {
    render(createElement(Home));
    expect(screen.getByText(/rehearse your next deal/i)).toBeInTheDocument();
  });

  it("renders hero heading with 'Close with Confidence'", () => {
    render(createElement(Home));
    expect(screen.getByText(/close with confidence/i)).toBeInTheDocument();
  });

  // --- Requirement 16.2: 4 scenario showcase cards ---

  it("renders 4 scenario showcase cards", () => {
    render(createElement(Home));
    expect(screen.getByText("SaaS Contract Negotiation")).toBeInTheDocument();
    expect(screen.getByText("Renewal / Churn Save")).toBeInTheDocument();
    expect(screen.getByText("Enterprise Multi-Stakeholder")).toBeInTheDocument();
    expect(screen.getByText("Discovery / Qualification")).toBeInTheDocument();
  });

  // --- Requirement 16.3: 3 sales value prop cards ---

  it("renders 3 sales value proposition cards", () => {
    render(createElement(Home));
    expect(screen.getByText("Objection Handling")).toBeInTheDocument();
    expect(screen.getByText("Hidden Variables")).toBeInTheDocument();
    expect(screen.getByText("Multi-Stakeholder Navigation")).toBeInTheDocument();
  });

  // --- Requirement 16.4: Pricing signal ---

  it("renders pricing signal text", () => {
    render(createElement(Home));
    expect(screen.getByText("Starting at $500/month for teams")).toBeInTheDocument();
  });

  // --- Requirement 16.5: Supported By section ---

  it("renders 'Supported By' section", () => {
    render(createElement(Home));
    expect(screen.getByText(/supported by/i)).toBeInTheDocument();
    expect(screen.getByAltText("Enterprise Ireland")).toBeInTheDocument();
    expect(screen.getByAltText("Google Cloud for Startups")).toBeInTheDocument();
    expect(screen.getByAltText("Web Summit")).toBeInTheDocument();
  });

  // --- Requirement 16.6: Demo video placeholder ---

  it("renders demo video placeholder", () => {
    render(createElement(Home));
    expect(screen.getByText("Demo coming soon")).toBeInTheDocument();
  });

  // --- CTA link to /arena ---

  it("renders 'Try a Free Simulation' CTA linking to /arena", () => {
    render(createElement(Home));
    const ctaLinks = screen.getAllByRole("link", { name: /try a free simulation/i });
    expect(ctaLinks.length).toBeGreaterThanOrEqual(1);
    expect(ctaLinks[0]).toHaveAttribute("href", "/arena");
  });

  // --- WaitlistForm ---

  it("renders WaitlistForm", () => {
    render(createElement(Home));
    expect(screen.getByTestId("waitlist-form")).toBeInTheDocument();
  });

  // --- Old developer content NOT present ---

  it("does not render old developer heading 'AI Negotiation Sandbox'", () => {
    render(createElement(Home));
    expect(screen.queryByText(/ai negotiation sandbox/i)).not.toBeInTheDocument();
  });

  it("does not render old 'Built in Public' section", () => {
    render(createElement(Home));
    expect(screen.queryByText(/built in public/i)).not.toBeInTheDocument();
  });
});
