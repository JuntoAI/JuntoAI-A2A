import { render, screen } from "@testing-library/react";
import ChatPanel from "@/components/glassbox/ChatPanel";
import type { MessageEntry } from "@/lib/glassBoxReducer";

const makeMessage = (
  overrides: Partial<MessageEntry> = {},
): MessageEntry => ({
  agentName: "SellerBot",
  publicMessage: "I propose $500k",
  turnNumber: 1,
  timestamp: Date.now(),
  ...overrides,
});

describe("ChatPanel", () => {
  it("renders messages with agent name in color", () => {
    const messages = [
      makeMessage({ agentName: "BuyerBot", publicMessage: "Offer $400k" }),
      makeMessage({ agentName: "SellerBot", publicMessage: "Counter $600k" }),
    ];
    render(<ChatPanel messages={messages} isConnected={true} />);

    expect(screen.getByText("BuyerBot")).toBeInTheDocument();
    expect(screen.getByText("SellerBot")).toBeInTheDocument();
    expect(screen.getByText("Offer $400k")).toBeInTheDocument();
    expect(screen.getByText("Counter $600k")).toBeInTheDocument();

    // Agent names should have inline color styles
    const buyerLabel = screen.getByText("BuyerBot");
    expect(buyerLabel.style.color).toBeTruthy();
  });

  it("renders proposed price badge when proposedPrice present", () => {
    const messages = [makeMessage({ proposedPrice: 500000 })];
    render(<ChatPanel messages={messages} isConnected={true} />);

    const badge = screen.getByTestId("proposed-price-badge");
    expect(badge).toBeInTheDocument();
    expect(badge.textContent).toContain("500,000");
  });

  it("does not render proposed price badge when proposedPrice absent", () => {
    const messages = [makeMessage()];
    render(<ChatPanel messages={messages} isConnected={true} />);

    expect(screen.queryByTestId("proposed-price-badge")).not.toBeInTheDocument();
  });

  it("renders regulator status message with green classes for CLEAR", () => {
    const messages = [
      makeMessage({
        agentName: "Regulator",
        regulatorStatus: "CLEAR",
        publicMessage: "All good",
      }),
    ];
    render(<ChatPanel messages={messages} isConnected={true} />);

    const statusMsg = screen.getByTestId("regulator-status-message");
    expect(statusMsg).toBeInTheDocument();
    expect(statusMsg.className).toContain("text-green-400");
    expect(statusMsg.className).toContain("bg-green-900/30");
  });

  it("renders regulator status message with yellow classes for WARNING", () => {
    const messages = [
      makeMessage({
        agentName: "Regulator",
        regulatorStatus: "WARNING",
        publicMessage: "Caution",
      }),
    ];
    render(<ChatPanel messages={messages} isConnected={true} />);

    const statusMsg = screen.getByTestId("regulator-status-message");
    expect(statusMsg.className).toContain("text-yellow-400");
    expect(statusMsg.className).toContain("bg-yellow-900/30");
  });

  it("renders regulator status message with red classes for BLOCKED", () => {
    const messages = [
      makeMessage({
        agentName: "Regulator",
        regulatorStatus: "BLOCKED",
        publicMessage: "Deal blocked",
      }),
    ];
    render(<ChatPanel messages={messages} isConnected={true} />);

    const statusMsg = screen.getByTestId("regulator-status-message");
    expect(statusMsg.className).toContain("text-red-400");
    expect(statusMsg.className).toContain("bg-red-900/30");
  });

  it("renders messages left-aligned", () => {
    const messages = [makeMessage()];
    const { container } = render(
      <ChatPanel messages={messages} isConnected={true} />,
    );

    // All message wrappers should have text-left class
    const messageDiv = container.querySelector(".text-left");
    expect(messageDiv).toBeTruthy();
  });
});
