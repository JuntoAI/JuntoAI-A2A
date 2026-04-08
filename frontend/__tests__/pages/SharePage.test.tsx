import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import type { SharePayload } from "@/lib/share";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockBackendFetch = vi.fn<() => Promise<Response>>();

vi.mock("@/lib/proxy", () => ({
  backendFetch: (...args: unknown[]) => mockBackendFetch(...args),
}));

vi.mock("next/image", () => ({
  default: (props: Record<string, unknown>) =>
    createElement("img", { src: props.src, alt: props.alt, "data-testid": "next-image" }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makePayload(overrides: Partial<SharePayload> = {}): SharePayload {
  return {
    share_slug: "aB3dEf9x",
    session_id: "sess-abc-123",
    scenario_name: "M&A Buyout",
    scenario_description: "Corporate acquisition negotiation",
    deal_status: "Agreed",
    outcome_text: "Both parties reached a deal at $4.2M",
    final_offer: 4200000,
    turns_completed: 6,
    warning_count: 1,
    participant_summaries: [
      { role: "Buyer", name: "Buyer CEO", agent_type: "negotiator", summary: "Pushed for lower price" },
      { role: "Seller", name: "Founder", agent_type: "negotiator", summary: "Held firm on valuation" },
      { role: "Regulator", name: "EU Regulator", agent_type: "regulator", summary: "Approved the deal" },
    ],
    elapsed_time_ms: 12500,
    share_image_url: "/api/v1/share/images/aB3dEf9x.png",
    created_at: "2024-01-15T10:30:00Z",
    ...overrides,
  };
}

function mockFetchOk(payload: SharePayload) {
  mockBackendFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(payload),
  } as unknown as Response);
}

function mockFetch404() {
  mockBackendFetch.mockResolvedValue({
    ok: false,
    status: 404,
  } as unknown as Response);
}

// ---------------------------------------------------------------------------
// Helper — render async server component
// ---------------------------------------------------------------------------

async function renderSharePage(slug = "aB3dEf9x") {
  const Page = (await import("@/app/share/[slug]/page")).default;
  const jsx = await Page({ params: Promise.resolve({ slug }) });
  return render(jsx);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Public Share Page", () => {
  beforeEach(() => {
    mockBackendFetch.mockReset();
    vi.resetModules();
  });

  // -----------------------------------------------------------------------
  // Req 2.1 — Public page renders without auth
  // -----------------------------------------------------------------------

  describe("Agreed status", () => {
    it("renders scenario name and deal status with green styling", async () => {
      const payload = makePayload({ deal_status: "Agreed" });
      mockFetchOk(payload);

      await renderSharePage();

      expect(screen.getByText("M&A Buyout")).toBeInTheDocument();
      expect(screen.getByText("Deal Agreed")).toBeInTheDocument();

      // Green border on the main card
      const badge = screen.getByText("Deal Agreed").closest("span");
      expect(badge?.className).toContain("text-green-800");
    });

    it("renders final offer formatted as currency", async () => {
      mockFetchOk(makePayload({ final_offer: 4200000 }));
      await renderSharePage();

      expect(screen.getByText("$4,200,000")).toBeInTheDocument();
      expect(screen.getByText("Final Offer")).toBeInTheDocument();
    });

    it("renders outcome text", async () => {
      mockFetchOk(makePayload({ outcome_text: "Both parties reached a deal at $4.2M" }));
      await renderSharePage();

      expect(screen.getByText("Both parties reached a deal at $4.2M")).toBeInTheDocument();
    });

    it("renders turn count and warning count", async () => {
      mockFetchOk(makePayload({ turns_completed: 6, warning_count: 1 }));
      await renderSharePage();

      expect(screen.getByText("6")).toBeInTheDocument();
      expect(screen.getByText("Turns")).toBeInTheDocument();
      expect(screen.getByText("1")).toBeInTheDocument();
      expect(screen.getByText("Warnings")).toBeInTheDocument();
    });

    it("renders elapsed time formatted", async () => {
      mockFetchOk(makePayload({ elapsed_time_ms: 12500 }));
      await renderSharePage();

      expect(screen.getByText("13s")).toBeInTheDocument();
      expect(screen.getByText("Elapsed")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Req 2.2 — Status-appropriate styling
  // -----------------------------------------------------------------------

  describe("Blocked status", () => {
    it("renders with yellow styling and 'Deal Blocked' label", async () => {
      mockFetchOk(makePayload({ deal_status: "Blocked" }));
      await renderSharePage();

      expect(screen.getByText("Deal Blocked")).toBeInTheDocument();
      const badge = screen.getByText("Deal Blocked").closest("span");
      expect(badge?.className).toContain("text-yellow-800");
    });
  });

  describe("Failed status", () => {
    it("renders with gray styling and 'Negotiation Failed' label", async () => {
      mockFetchOk(makePayload({ deal_status: "Failed" }));
      await renderSharePage();

      expect(screen.getByText("Negotiation Failed")).toBeInTheDocument();
      const badge = screen.getByText("Negotiation Failed").closest("span");
      expect(badge?.className).toContain("text-gray-700");
    });
  });

  // -----------------------------------------------------------------------
  // Req 2.2 — Participant summaries
  // -----------------------------------------------------------------------

  describe("Participant summaries", () => {
    it("renders participant names, roles, and summaries", async () => {
      mockFetchOk(makePayload());
      await renderSharePage();

      expect(screen.getByText("Buyer CEO")).toBeInTheDocument();
      expect(screen.getByText("Buyer")).toBeInTheDocument();
      expect(screen.getByText("Pushed for lower price")).toBeInTheDocument();

      expect(screen.getByText("Founder")).toBeInTheDocument();
      expect(screen.getByText("Seller")).toBeInTheDocument();

      expect(screen.getByText("EU Regulator")).toBeInTheDocument();
    });

    it("applies regulator-specific styling to regulator participants", async () => {
      mockFetchOk(makePayload());
      await renderSharePage();

      const regulatorBadge = screen.getByText("EU Regulator");
      expect(regulatorBadge.className).toContain("bg-red-100");
      expect(regulatorBadge.className).toContain("text-red-700");
    });

    it("does not render participants section when list is empty", async () => {
      mockFetchOk(makePayload({ participant_summaries: [] }));
      await renderSharePage();

      expect(screen.queryByText("Participants")).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Req 2.3 — 404 state
  // -----------------------------------------------------------------------

  describe("404 state", () => {
    it("shows 'Negotiation not found' when slug does not exist", async () => {
      mockFetch404();
      await renderSharePage("nonexistent");

      expect(screen.getByText("Negotiation not found")).toBeInTheDocument();
      expect(
        screen.getByText(/this share link may have expired/i),
      ).toBeInTheDocument();
    });

    it("shows CTA linking to landing page", async () => {
      mockFetch404();
      await renderSharePage("nonexistent");

      const cta = screen.getByText("Try JuntoAI A2A");
      expect(cta).toBeInTheDocument();
      expect(cta.closest("a")).toHaveAttribute("href", "/");
    });
  });

  // -----------------------------------------------------------------------
  // Req 2.6 — Branded header
  // -----------------------------------------------------------------------

  describe("Branded header", () => {
    it("renders JuntoAI logo and branding text in header", async () => {
      mockFetchOk(makePayload());
      await renderSharePage();

      // "JuntoAI A2A" appears in header and footer — check header specifically
      const header = document.querySelector("header")!;
      expect(header).toBeInTheDocument();
      expect(header.textContent).toContain("JuntoAI A2A");

      const logo = screen.getByTestId("next-image");
      expect(logo).toHaveAttribute("alt", "JuntoAI logo");
    });

    it("renders 'Try JuntoAI A2A' CTA in header linking to landing page", async () => {
      mockFetchOk(makePayload());
      await renderSharePage();

      // There are two "Try JuntoAI A2A" links — header CTA and footer
      const links = screen.getAllByText("Try JuntoAI A2A");
      const headerCta = links.find((el) => el.closest("header"));
      expect(headerCta).toBeDefined();
      expect(headerCta?.closest("a")).toHaveAttribute("href", "/");
    });
  });

  // -----------------------------------------------------------------------
  // Edge cases
  // -----------------------------------------------------------------------

  describe("Edge cases", () => {
    it("hides final offer metric when final_offer is 0", async () => {
      mockFetchOk(makePayload({ final_offer: 0 }));
      await renderSharePage();

      expect(screen.queryByText("Final Offer")).not.toBeInTheDocument();
    });

    it("hides warnings metric when warning_count is 0", async () => {
      mockFetchOk(makePayload({ warning_count: 0 }));
      await renderSharePage();

      expect(screen.queryByText("Warnings")).not.toBeInTheDocument();
    });

    it("renders scenario description when present", async () => {
      mockFetchOk(makePayload({ scenario_description: "Corporate acquisition negotiation" }));
      await renderSharePage();

      expect(screen.getByText("Corporate acquisition negotiation")).toBeInTheDocument();
    });

    it("handles backendFetch throwing an error gracefully (shows 404)", async () => {
      mockBackendFetch.mockRejectedValue(new Error("Network error"));
      await renderSharePage("broken");

      expect(screen.getByText("Negotiation not found")).toBeInTheDocument();
    });
  });
});
