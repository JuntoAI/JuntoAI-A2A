import { render, screen, fireEvent } from "@testing-library/react";
import { InformationToggle } from "@/components/arena/InformationToggle";

describe("InformationToggle", () => {
  const defaultProps = {
    id: "competing_offer",
    label: "Reveal competing offer to buyer",
    checked: false,
    onChange: vi.fn(),
  };

  // Req 3.2: renders label text
  it("renders the toggle label", () => {
    render(<InformationToggle {...defaultProps} />);
    expect(
      screen.getByText("Reveal competing offer to buyer"),
    ).toBeInTheDocument();
  });

  it("renders a checkbox input", () => {
    render(<InformationToggle {...defaultProps} />);
    expect(screen.getByRole("checkbox")).toBeInTheDocument();
  });

  it("reflects unchecked state", () => {
    render(<InformationToggle {...defaultProps} checked={false} />);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("reflects checked state", () => {
    render(<InformationToggle {...defaultProps} checked={true} />);
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  // Fires onChange with id and new checked state
  it("calls onChange with id and true when checking", () => {
    const onChange = vi.fn();
    render(
      <InformationToggle {...defaultProps} checked={false} onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith("competing_offer", true);
  });

  it("calls onChange with id and false when unchecking", () => {
    const onChange = vi.fn();
    render(
      <InformationToggle {...defaultProps} checked={true} onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith("competing_offer", false);
  });

  // Associates label with checkbox via htmlFor
  it("associates the label with the checkbox via id", () => {
    render(<InformationToggle {...defaultProps} />);
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toHaveAttribute("id", "competing_offer");
  });
});
