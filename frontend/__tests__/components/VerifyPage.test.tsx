import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { createElement } from "react";

// Mock next/navigation
const mockGet = vi.fn();
vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: mockGet }),
}));

import VerifyPage from "@/app/profile/verify/page";

describe("VerifyPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows invalid state when no token in URL", async () => {
    mockGet.mockReturnValue(null);
    render(createElement(VerifyPage));
    await waitFor(() => {
      expect(screen.getByText("Invalid Link")).toBeInTheDocument();
    });
  });

  it("shows success state on 200 response", async () => {
    mockGet.mockReturnValue("valid-token");
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, status: 200 });
    render(createElement(VerifyPage));
    await waitFor(() => {
      expect(screen.getByText("Email Verified")).toBeInTheDocument();
    });
  });

  it("shows expired state on 410 response", async () => {
    mockGet.mockReturnValue("expired-token");
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: false, status: 410 });
    render(createElement(VerifyPage));
    await waitFor(() => {
      expect(screen.getByText("Link Expired")).toBeInTheDocument();
    });
  });

  it("shows invalid state on other error response", async () => {
    mockGet.mockReturnValue("bad-token");
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: false, status: 400 });
    render(createElement(VerifyPage));
    await waitFor(() => {
      expect(screen.getByText("Invalid Link")).toBeInTheDocument();
    });
  });

  it("shows invalid state on fetch error", async () => {
    mockGet.mockReturnValue("token");
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("Network error"));
    render(createElement(VerifyPage));
    await waitFor(() => {
      expect(screen.getByText("Invalid Link")).toBeInTheDocument();
    });
  });
});
