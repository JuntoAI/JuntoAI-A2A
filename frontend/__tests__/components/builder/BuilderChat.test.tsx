import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { containsLinkedInUrl } from "@/components/builder/BuilderChat";

// ---------------------------------------------------------------------------
// Mock SSE client before importing component
// ---------------------------------------------------------------------------

const mockStreamBuilderChat = vi.fn();

vi.mock("@/lib/builder/sse-client", () => ({
  streamBuilderChat: (...args: unknown[]) => mockStreamBuilderChat(...args),
}));

import { BuilderChat } from "@/components/builder/BuilderChat";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BuilderChat", () => {
  const defaultProps = {
    sessionId: "test-session",
    email: "user@example.com",
    onJsonDelta: vi.fn(),
    onHealthReport: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockStreamBuilderChat.mockReturnValue({ abort: vi.fn() });
  });

  it("renders chat container with input and send button", () => {
    render(<BuilderChat {...defaultProps} />);
    expect(screen.getByTestId("builder-chat")).toBeInTheDocument();
    expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    expect(screen.getByTestId("send-button")).toBeInTheDocument();
  });

  it("send button is disabled when input is empty", () => {
    render(<BuilderChat {...defaultProps} />);
    expect(screen.getByTestId("send-button")).toBeDisabled();
  });

  it("sends message on Enter key", () => {
    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(mockStreamBuilderChat).toHaveBeenCalledWith(
      "user@example.com",
      "test-session",
      "Hello",
      expect.any(Object),
    );
  });

  it("sends message on send button click", () => {
    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByTestId("send-button"));

    expect(mockStreamBuilderChat).toHaveBeenCalledOnce();
  });

  it("displays user message after sending", () => {
    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Build a scenario" } });
    fireEvent.click(screen.getByTestId("send-button"));

    expect(screen.getByTestId("chat-message-user")).toHaveTextContent(
      "Build a scenario",
    );
  });

  it("disables input while waiting for response", () => {
    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByTestId("send-button"));

    expect(input).toBeDisabled();
  });

  it("clears input after sending", () => {
    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByTestId("send-button"));

    expect(input.value).toBe("");
  });
});

// ---------------------------------------------------------------------------
// LinkedIn URL detection
// ---------------------------------------------------------------------------

describe("containsLinkedInUrl", () => {
  it("detects valid LinkedIn URLs", () => {
    expect(
      containsLinkedInUrl("Check https://www.linkedin.com/in/john-doe"),
    ).toBe(true);
  });

  it("returns false for non-LinkedIn URLs", () => {
    expect(containsLinkedInUrl("Visit https://example.com")).toBe(false);
  });

  it("returns false for empty string", () => {
    expect(containsLinkedInUrl("")).toBe(false);
  });

  it("detects LinkedIn URL in mixed text", () => {
    expect(
      containsLinkedInUrl(
        "Use this profile https://www.linkedin.com/in/jane-smith for the agent",
      ),
    ).toBe(true);
  });
});
