import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

/**
 * Feature: 270_public-stats-dashboard
 * Unit test: Admin sidebar contains "Platform Stats" link.
 *
 * Validates: Requirements 2.1, 2.2, 2.3 (adapted to admin sidebar)
 */

const mockCookieStore = {
  get: vi.fn(),
};

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => mockCookieStore),
}));

import AdminLayout from "@/app/admin/layout";

describe("Admin Layout — Platform Stats sidebar link", () => {
  it("renders Platform Stats link in sidebar when authenticated", async () => {
    mockCookieStore.get.mockReturnValue({ value: "valid-session-token" });

    const layout = await AdminLayout({
      children: <div data-testid="child">content</div>,
    });
    render(layout);

    const statsLink = screen.getByRole("link", { name: "Platform Stats" });
    expect(statsLink).toBeInTheDocument();
    expect(statsLink).toHaveAttribute("href", "/admin/stats");
  });

  it("Platform Stats link is adjacent to Broadcast link", async () => {
    mockCookieStore.get.mockReturnValue({ value: "valid-session-token" });

    const layout = await AdminLayout({
      children: <div>content</div>,
    });
    render(layout);

    const links = screen.getAllByRole("link");
    const labels = links.map((l) => l.textContent);
    const broadcastIdx = labels.indexOf("Broadcast");
    const statsIdx = labels.indexOf("Platform Stats");

    expect(broadcastIdx).toBeGreaterThanOrEqual(0);
    expect(statsIdx).toBeGreaterThanOrEqual(0);
    expect(statsIdx).toBe(broadcastIdx + 1);
  });

  it("does not render sidebar when not authenticated", async () => {
    mockCookieStore.get.mockReturnValue(undefined);

    const layout = await AdminLayout({
      children: <div data-testid="child">content</div>,
    });
    render(layout);

    expect(screen.queryByRole("link", { name: "Platform Stats" })).not.toBeInTheDocument();
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});
