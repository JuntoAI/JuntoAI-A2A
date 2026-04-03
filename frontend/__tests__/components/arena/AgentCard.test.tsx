import { render, screen } from "@testing-library/react";
import { AgentCard } from "@/components/arena/AgentCard";

describe("AgentCard", () => {
  const baseProps = {
    name: "Buyer CEO",
    role: "negotiator",
    goals: ["Acquire company at lowest price", "Retain key talent"],
    modelId: "gemini-3-flash-preview",
    index: 0,
  };

  // Req 2.2: displays all required fields
  it("renders agent name", () => {
    render(<AgentCard {...baseProps} />);
    expect(screen.getByText("Buyer CEO")).toBeInTheDocument();
  });

  it("renders agent role", () => {
    render(<AgentCard {...baseProps} />);
    expect(screen.getByText("negotiator")).toBeInTheDocument();
  });

  it("renders all goals", () => {
    render(<AgentCard {...baseProps} />);
    for (const goal of baseProps.goals) {
      expect(screen.getByText(`• ${goal}`)).toBeInTheDocument();
    }
  });

  it("renders model identifier", () => {
    render(<AgentCard {...baseProps} />);
    expect(screen.getByText("Model: gemini-3-flash-preview")).toBeInTheDocument();
  });

  // Req 2.3: distinct colors per index
  it("applies distinct border color for index 0 vs index 1", () => {
    const { container: c0 } = render(<AgentCard {...baseProps} index={0} />);
    const { container: c1 } = render(<AgentCard {...baseProps} index={1} />);

    const card0 = c0.firstElementChild as HTMLElement;
    const card1 = c1.firstElementChild as HTMLElement;

    expect(card0.style.borderLeftColor).not.toBe(card1.style.borderLeftColor);
  });

  it("applies distinct role badge color for index 0 vs index 2", () => {
    const { container: c0 } = render(<AgentCard {...baseProps} index={0} />);
    const { container: c2 } = render(<AgentCard {...baseProps} index={2} />);

    // The role badge is a <span> with inline backgroundColor
    const badge0 = c0.querySelector("span[style]") as HTMLElement;
    const badge2 = c2.querySelector("span[style]") as HTMLElement;

    expect(badge0.style.backgroundColor).not.toBe(
      badge2.style.backgroundColor,
    );
  });

  // Color wraps around for large indices
  it("wraps color palette for indices beyond palette length", () => {
    const { container: c0 } = render(<AgentCard {...baseProps} index={0} />);
    const { container: c8 } = render(<AgentCard {...baseProps} index={8} />);

    const card0 = c0.firstElementChild as HTMLElement;
    const card8 = c8.firstElementChild as HTMLElement;

    // index 8 % 8 === 0, so same color as index 0
    expect(card0.style.borderLeftColor).toBe(card8.style.borderLeftColor);
  });
});
