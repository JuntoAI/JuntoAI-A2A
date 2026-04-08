import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SharePanel from "@/components/glassbox/SharePanel";
import type { CreateShareResponse } from "@/lib/share";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockCreateShare = vi.fn<() => Promise<CreateShareResponse>>();

vi.mock("@/lib/share", () => ({
  createShare: (...args: unknown[]) => mockCreateShare(...args),
}));

const mockWindowOpen = vi.fn();
const originalOpen = window.open;

const mockClipboardWriteText = vi.fn<() => Promise<void>>();

beforeEach(() => {
  mockCreateShare.mockReset();
  mockWindowOpen.mockReset();
  mockClipboardWriteText.mockReset();

  window.open = mockWindowOpen;
  Object.assign(navigator, {
    clipboard: { writeText: mockClipboardWriteText },
  });
});

afterEach(() => {
  window.open = originalOpen;
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SHARE_RESPONSE: CreateShareResponse = {
  share_slug: "aB3dEf9x",
  share_url: "https://app.juntoai.org/share/aB3dEf9x",
  social_post_text: {
    twitter: "Test tweet text",
    linkedin: "Test LinkedIn text",
    facebook: "Test Facebook text",
  },
  share_image_url: "/api/v1/share/images/placeholder.png",
};

const defaultProps = { sessionId: "sess-123", email: "user@test.com" };

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SharePanel", () => {
  // Req 6.2 — renders 5 share buttons with correct data-testid attributes
  it("renders all 5 share buttons", () => {
    render(<SharePanel {...defaultProps} />);

    expect(screen.getByTestId("share-panel")).toBeInTheDocument();
    expect(screen.getByTestId("share-linkedin")).toBeInTheDocument();
    expect(screen.getByTestId("share-twitter")).toBeInTheDocument();
    expect(screen.getByTestId("share-facebook")).toBeInTheDocument();
    expect(screen.getByTestId("share-copy")).toBeInTheDocument();
    expect(screen.getByTestId("share-email")).toBeInTheDocument();
  });

  // Req 6.4 — lazy creation: first click triggers createShare API call
  it("first click on LinkedIn triggers createShare, then opens window", async () => {
    mockCreateShare.mockResolvedValueOnce(SHARE_RESPONSE);

    render(<SharePanel {...defaultProps} />);
    fireEvent.click(screen.getByTestId("share-linkedin"));

    await waitFor(() => {
      expect(mockCreateShare).toHaveBeenCalledWith("sess-123", "user@test.com");
    });

    // Req 4.4 — LinkedIn opens correct URL
    expect(mockWindowOpen).toHaveBeenCalledWith(
      expect.stringContaining("linkedin.com/sharing/share-offsite"),
      "_blank",
      "noopener,noreferrer",
    );
    expect(mockWindowOpen).toHaveBeenCalledWith(
      expect.stringContaining(encodeURIComponent(SHARE_RESPONSE.share_url)),
      expect.any(String),
      expect.any(String),
    );
  });

  // Req 6.5 — loading state: buttons disabled during API call
  it("disables all buttons while createShare is in progress", async () => {
    let resolveShare!: (v: CreateShareResponse) => void;
    mockCreateShare.mockReturnValueOnce(
      new Promise<CreateShareResponse>((r) => { resolveShare = r; }),
    );

    render(<SharePanel {...defaultProps} />);
    fireEvent.click(screen.getByTestId("share-linkedin"));

    // All buttons should be disabled while loading
    await waitFor(() => {
      expect(screen.getByTestId("share-linkedin")).toBeDisabled();
    });
    expect(screen.getByTestId("share-twitter")).toBeDisabled();
    expect(screen.getByTestId("share-facebook")).toBeDisabled();
    expect(screen.getByTestId("share-copy")).toBeDisabled();
    expect(screen.getByTestId("share-email")).toBeDisabled();

    // Resolve and verify buttons re-enable
    resolveShare(SHARE_RESPONSE);
    await waitFor(() => {
      expect(screen.getByTestId("share-linkedin")).not.toBeDisabled();
    });
  });

  // Req 4.5 — X/Twitter opens correct URL
  it("X/Twitter button opens correct intent URL", async () => {
    mockCreateShare.mockResolvedValueOnce(SHARE_RESPONSE);

    render(<SharePanel {...defaultProps} />);
    fireEvent.click(screen.getByTestId("share-twitter"));

    await waitFor(() => {
      expect(mockWindowOpen).toHaveBeenCalledWith(
        expect.stringContaining("twitter.com/intent/tweet"),
        "_blank",
        "noopener,noreferrer",
      );
    });
    expect(mockWindowOpen).toHaveBeenCalledWith(
      expect.stringContaining(encodeURIComponent(SHARE_RESPONSE.social_post_text.twitter)),
      expect.any(String),
      expect.any(String),
    );
  });

  // Req 4.6 — Facebook opens correct URL
  it("Facebook button opens correct sharer URL", async () => {
    mockCreateShare.mockResolvedValueOnce(SHARE_RESPONSE);

    render(<SharePanel {...defaultProps} />);
    fireEvent.click(screen.getByTestId("share-facebook"));

    await waitFor(() => {
      expect(mockWindowOpen).toHaveBeenCalledWith(
        expect.stringContaining("facebook.com/sharer/sharer.php"),
        "_blank",
        "noopener,noreferrer",
      );
    });
    expect(mockWindowOpen).toHaveBeenCalledWith(
      expect.stringContaining(encodeURIComponent(SHARE_RESPONSE.share_url)),
      expect.any(String),
      expect.any(String),
    );
  });

  // Req 5.1, 5.3 — Copy Link calls clipboard API and shows "Copied!" text
  it("Copy Link calls clipboard API and shows Copied! text", async () => {
    mockCreateShare.mockResolvedValueOnce(SHARE_RESPONSE);
    mockClipboardWriteText.mockResolvedValueOnce(undefined);

    render(<SharePanel {...defaultProps} />);
    fireEvent.click(screen.getByTestId("share-copy"));

    await waitFor(() => {
      expect(mockClipboardWriteText).toHaveBeenCalledWith(SHARE_RESPONSE.share_url);
    });

    // Button text changes to "Copied!"
    expect(screen.getByTestId("share-copy")).toHaveTextContent("Copied!");
  });

  // Req 5.4 — clipboard fallback: shows text input when clipboard fails
  it("shows fallback text input when clipboard API fails", async () => {
    mockCreateShare.mockResolvedValueOnce(SHARE_RESPONSE);
    mockClipboardWriteText.mockRejectedValueOnce(new Error("Clipboard unavailable"));

    render(<SharePanel {...defaultProps} />);
    fireEvent.click(screen.getByTestId("share-copy"));

    await waitFor(() => {
      expect(screen.getByTestId("share-copy-fallback")).toBeInTheDocument();
    });

    const input = screen.getByTestId("share-copy-fallback").querySelector("input");
    expect(input).toHaveValue(SHARE_RESPONSE.share_url);
  });

  // Req 5.1 — Email opens mailto link
  it("Email button navigates to mailto link", async () => {
    mockCreateShare.mockResolvedValueOnce(SHARE_RESPONSE);

    // Spy on window.location.href assignment
    const hrefSetter = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, href: "", set href(v: string) { hrefSetter(v); } },
    });
    // Re-define as writable for the setter spy
    Object.defineProperty(window.location, "href", {
      configurable: true,
      set: hrefSetter,
      get: () => "",
    });

    render(<SharePanel {...defaultProps} />);
    fireEvent.click(screen.getByTestId("share-email"));

    await waitFor(() => {
      expect(hrefSetter).toHaveBeenCalled();
    });

    const mailtoUrl = hrefSetter.mock.calls[0][0] as string;
    expect(mailtoUrl).toContain("mailto:");
    expect(mailtoUrl).toContain("subject=");
    expect(mailtoUrl).toContain("body=");
    // Body should contain the share URL
    expect(mailtoUrl).toContain(encodeURIComponent(SHARE_RESPONSE.share_url));

    // Restore
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
  });

  // Req 6.4 — second click reuses cached response, createShare not called again
  it("second click reuses cached share data without calling createShare again", async () => {
    mockCreateShare.mockResolvedValueOnce(SHARE_RESPONSE);

    render(<SharePanel {...defaultProps} />);

    // First click — triggers API
    fireEvent.click(screen.getByTestId("share-linkedin"));
    await waitFor(() => {
      expect(mockCreateShare).toHaveBeenCalledTimes(1);
    });

    // Second click — should reuse cached data
    fireEvent.click(screen.getByTestId("share-twitter"));
    await waitFor(() => {
      expect(mockWindowOpen).toHaveBeenCalledTimes(2);
    });
    expect(mockCreateShare).toHaveBeenCalledTimes(1);
  });

  // Req 6.6 — responsive layout: grid on mobile, flex row on desktop
  it("renders with responsive grid/flex layout classes", () => {
    render(<SharePanel {...defaultProps} />);

    const buttonContainer = screen.getByTestId("share-panel").querySelector(".grid");
    expect(buttonContainer).toBeInTheDocument();
    // Has mobile grid + desktop flex classes
    expect(buttonContainer?.className).toContain("grid-cols-2");
    expect(buttonContainer?.className).toContain("lg:flex");
  });

  // Error state
  it("displays error message when createShare fails", async () => {
    mockCreateShare.mockRejectedValueOnce(new Error("Network error"));

    render(<SharePanel {...defaultProps} />);
    fireEvent.click(screen.getByTestId("share-linkedin"));

    await waitFor(() => {
      expect(screen.getByTestId("share-error")).toHaveTextContent("Network error");
    });
  });
});
