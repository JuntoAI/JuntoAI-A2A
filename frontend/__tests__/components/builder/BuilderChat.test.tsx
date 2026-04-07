import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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

  it("shows thinking indicator while waiting before first token", () => {
    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByTestId("send-button"));

    expect(screen.getByTestId("thinking-indicator")).toBeInTheDocument();
  });

  it("does not send on Shift+Enter", () => {
    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

    expect(mockStreamBuilderChat).not.toHaveBeenCalled();
  });

  it("does not send when input is only whitespace", () => {
    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.click(screen.getByTestId("send-button"));

    expect(mockStreamBuilderChat).not.toHaveBeenCalled();
  });

  it("displays assistant message after onComplete callback", async () => {
    mockStreamBuilderChat.mockImplementation((_email: string, _sid: string, _msg: string, callbacks: { onToken: (t: string) => void; onComplete: () => void }) => {
      // Simulate streaming tokens then completing
      setTimeout(() => {
        callbacks.onToken("Hello ");
        callbacks.onToken("world");
      }, 10);
      setTimeout(() => {
        callbacks.onComplete();
      }, 20);
      return { abort: vi.fn() };
    });

    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hi" } });
    fireEvent.click(screen.getByTestId("send-button"));

    await waitFor(() => {
      expect(screen.getByTestId("chat-message-assistant")).toHaveTextContent("Hello world");
    });
  });

  it("displays error message from onError callback", async () => {
    mockStreamBuilderChat.mockImplementation((_email: string, _sid: string, _msg: string, callbacks: { onError: (m: string) => void }) => {
      setTimeout(() => {
        callbacks.onError("Something went wrong");
      }, 10);
      return { abort: vi.fn() };
    });

    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hi" } });
    fireEvent.click(screen.getByTestId("send-button"));

    await waitFor(() => {
      expect(screen.getByTestId("chat-message-assistant")).toHaveTextContent("Error: Something went wrong");
    });
  });

  it("calls onJsonDelta when SSE sends json delta", async () => {
    const onJsonDelta = vi.fn();
    mockStreamBuilderChat.mockImplementation((_email: string, _sid: string, _msg: string, callbacks: { onJsonDelta: (s: string, d: Record<string, unknown>) => void; onComplete: () => void }) => {
      setTimeout(() => {
        callbacks.onJsonDelta("agents", { name: "Bot" });
        callbacks.onComplete();
      }, 10);
      return { abort: vi.fn() };
    });

    render(<BuilderChat {...defaultProps} onJsonDelta={onJsonDelta} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hi" } });
    fireEvent.click(screen.getByTestId("send-button"));

    await waitFor(() => {
      expect(onJsonDelta).toHaveBeenCalledWith("agents", { name: "Bot" });
    });
  });

  it("calls onHealthReport when SSE sends health complete", async () => {
    const onHealthReport = vi.fn();
    const report = { readiness_score: 85, tier: "Ready" };
    mockStreamBuilderChat.mockImplementation((_email: string, _sid: string, _msg: string, callbacks: { onHealthComplete: (r: unknown) => void; onComplete: () => void }) => {
      setTimeout(() => {
        callbacks.onHealthComplete(report);
        callbacks.onComplete();
      }, 10);
      return { abort: vi.fn() };
    });

    render(<BuilderChat {...defaultProps} onHealthReport={onHealthReport} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hi" } });
    fireEvent.click(screen.getByTestId("send-button"));

    await waitFor(() => {
      expect(onHealthReport).toHaveBeenCalledWith(report);
    });
  });

  it("shows streaming message with cursor while tokens arrive", async () => {
    mockStreamBuilderChat.mockImplementation((_email: string, _sid: string, _msg: string, callbacks: { onToken: (t: string) => void }) => {
      setTimeout(() => {
        callbacks.onToken("Streaming...");
      }, 10);
      return { abort: vi.fn() };
    });

    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hi" } });
    fireEvent.click(screen.getByTestId("send-button"));

    await waitFor(() => {
      expect(screen.getByTestId("streaming-message")).toBeInTheDocument();
    });
  });

  it("re-enables input after onComplete", async () => {
    mockStreamBuilderChat.mockImplementation((_email: string, _sid: string, _msg: string, callbacks: { onComplete: () => void }) => {
      setTimeout(() => callbacks.onComplete(), 10);
      return { abort: vi.fn() };
    });

    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hi" } });
    fireEvent.click(screen.getByTestId("send-button"));

    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });
  });

  it("re-enables input after onError", async () => {
    mockStreamBuilderChat.mockImplementation((_email: string, _sid: string, _msg: string, callbacks: { onError: (m: string) => void }) => {
      setTimeout(() => callbacks.onError("fail"), 10);
      return { abort: vi.fn() };
    });

    render(<BuilderChat {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "Hi" } });
    fireEvent.click(screen.getByTestId("send-button"));

    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });
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
