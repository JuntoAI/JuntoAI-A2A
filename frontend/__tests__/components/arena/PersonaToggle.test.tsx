import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PersonaToggle } from "@/components/arena/PersonaToggle";

describe("PersonaToggle", () => {
  const defaultProps = {
    persona: "sales" as const,
    onPersonaChange: vi.fn(),
  };

  // Req 8.1: renders both persona options
  it("renders Sales and Founders buttons", () => {
    render(<PersonaToggle {...defaultProps} />);
    expect(screen.getByRole("radio", { name: "Sales" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Founders" })).toBeInTheDocument();
  });

  // Req 8.1: renders as a radiogroup with accessible label
  it("renders a radiogroup with 'Persona selector' label", () => {
    render(<PersonaToggle {...defaultProps} />);
    expect(screen.getByRole("radiogroup", { name: "Persona selector" })).toBeInTheDocument();
  });

  // Req 8.1: Sales is active when persona is "sales"
  it("marks Sales as checked when persona is 'sales'", () => {
    render(<PersonaToggle {...defaultProps} persona="sales" />);
    expect(screen.getByRole("radio", { name: "Sales" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Founders" })).toHaveAttribute("aria-checked", "false");
  });

  // Req 8.1: Founders is active when persona is "founder"
  it("marks Founders as checked when persona is 'founder'", () => {
    render(<PersonaToggle {...defaultProps} persona="founder" />);
    expect(screen.getByRole("radio", { name: "Founders" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Sales" })).toHaveAttribute("aria-checked", "false");
  });

  // Req 8.1: defaults to Sales when persona is null
  it("defaults to Sales active when persona is null", () => {
    render(<PersonaToggle {...defaultProps} persona={null} />);
    expect(screen.getByRole("radio", { name: "Sales" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Founders" })).toHaveAttribute("aria-checked", "false");
  });

  // Req 8.2: fires onPersonaChange with "founder" when Founders clicked
  it("calls onPersonaChange with 'founder' when Founders is clicked", () => {
    const onPersonaChange = vi.fn();
    render(<PersonaToggle persona="sales" onPersonaChange={onPersonaChange} />);
    fireEvent.click(screen.getByRole("radio", { name: "Founders" }));
    expect(onPersonaChange).toHaveBeenCalledWith("founder");
  });

  // Req 8.2: fires onPersonaChange with "sales" when Sales clicked
  it("calls onPersonaChange with 'sales' when Sales is clicked", () => {
    const onPersonaChange = vi.fn();
    render(<PersonaToggle persona="founder" onPersonaChange={onPersonaChange} />);
    fireEvent.click(screen.getByRole("radio", { name: "Sales" }));
    expect(onPersonaChange).toHaveBeenCalledWith("sales");
  });

  // Req 8.2: clicking the already-active option still fires callback
  it("fires onPersonaChange even when clicking the already-active option", () => {
    const onPersonaChange = vi.fn();
    render(<PersonaToggle persona="sales" onPersonaChange={onPersonaChange} />);
    fireEvent.click(screen.getByRole("radio", { name: "Sales" }));
    expect(onPersonaChange).toHaveBeenCalledWith("sales");
  });
});
