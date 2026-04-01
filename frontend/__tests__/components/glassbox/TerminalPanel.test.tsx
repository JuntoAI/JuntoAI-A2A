import { render, screen } from "@testing-library/react";
import TerminalPanel from "@/components/glassbox/TerminalPanel";
import type { ThoughtEntry } from "@/lib/glassBoxReducer";

const makeThought = (
  agentName: string,
  innerThought: string,
  turnNumber = 1,
): ThoughtEntry => ({
  agentName,
  innerThought,
  turnNumber,
  timestamp: Date.now(),
});

describe("TerminalPanel", () => {
  it("renders thoughts with [AgentName] prefix in green", () => {
    const thoughts = [makeThought("BuyerBot", "I should offer less")];
    render(
      <TerminalPanel thoughts={thoughts} isConnected={true} dealStatus="Negotiating" />,
    );

    expect(screen.getByText("[BuyerBot]")).toBeInTheDocument();
    expect(screen.getByText("I should offer less")).toBeInTheDocument();

    // Agent name prefix should have green text class
    const prefix = screen.getByText("[BuyerBot]");
    expect(prefix.className).toContain("text-green-400");
  });

  it("has a bottomRef element for auto-scroll", () => {
    const { container } = render(
      <TerminalPanel thoughts={[]} isConnected={false} dealStatus="Negotiating" />,
    );

    // The bottomRef div is the last child inside the terminal container
    const terminal = container.querySelector('[data-testid="terminal-panel"]');
    expect(terminal).toBeTruthy();
    // The last div child is the scroll anchor
    const lastDiv = terminal!.querySelector("div:last-child");
    expect(lastDiv).toBeTruthy();
  });

  it("shows blinking cursor when isConnected && dealStatus === 'Negotiating'", () => {
    render(
      <TerminalPanel thoughts={[]} isConnected={true} dealStatus="Negotiating" />,
    );

    const cursor = screen.getByTestId("blinking-cursor");
    expect(cursor).toBeInTheDocument();
    expect(cursor.className).toContain("animate-pulse");
  });

  it("does not show blinking cursor when not connected", () => {
    render(
      <TerminalPanel thoughts={[]} isConnected={false} dealStatus="Negotiating" />,
    );

    expect(screen.queryByTestId("blinking-cursor")).not.toBeInTheDocument();
  });

  it("does not show blinking cursor when deal is terminal", () => {
    render(
      <TerminalPanel thoughts={[]} isConnected={true} dealStatus="Agreed" />,
    );

    expect(screen.queryByTestId("blinking-cursor")).not.toBeInTheDocument();
  });

  it('shows placeholder "Awaiting agent initialization..." when thoughts empty and connected', () => {
    render(
      <TerminalPanel thoughts={[]} isConnected={true} dealStatus="Negotiating" />,
    );

    expect(
      screen.getByText("Awaiting agent initialization..."),
    ).toBeInTheDocument();
  });

  it("does not show placeholder when thoughts are present", () => {
    const thoughts = [makeThought("Agent", "thinking...")];
    render(
      <TerminalPanel thoughts={thoughts} isConnected={true} dealStatus="Negotiating" />,
    );

    expect(
      screen.queryByText("Awaiting agent initialization..."),
    ).not.toBeInTheDocument();
  });
});
