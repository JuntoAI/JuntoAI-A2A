import { render, screen, fireEvent } from "@testing-library/react";
import { InitializeButton } from "@/components/arena/InitializeButton";

describe("InitializeButton", () => {
  const defaultProps = {
    onClick: vi.fn(),
    disabled: false,
    isLoading: false,
    insufficientTokens: false,
  };

  // Req 4.1: renders label
  it("renders 'Start Negotiation' label", () => {
    render(<InitializeButton {...defaultProps} />);
    expect(
      screen.getByRole("button", { name: "Start Negotiation" }),
    ).toBeInTheDocument();
  });

  // Req 4.2: disabled when disabled prop is true
  it("is disabled when disabled prop is true", () => {
    render(<InitializeButton {...defaultProps} disabled={true} />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  // Enabled in default state
  it("is enabled when all flags are false", () => {
    render(<InitializeButton {...defaultProps} />);
    expect(screen.getByRole("button")).not.toBeDisabled();
  });

  // Req 4.8: loading spinner
  it("shows loading text when isLoading is true", () => {
    render(<InitializeButton {...defaultProps} isLoading={true} />);
    expect(screen.getByText("Starting…")).toBeInTheDocument();
  });

  it("is disabled when isLoading is true", () => {
    render(<InitializeButton {...defaultProps} isLoading={true} />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("renders a spinner SVG when isLoading is true", () => {
    const { container } = render(
      <InitializeButton {...defaultProps} isLoading={true} />,
    );
    const svg = container.querySelector("svg.animate-spin");
    expect(svg).toBeInTheDocument();
  });

  // Req 4.5: insufficient tokens
  it("is disabled when insufficientTokens is true", () => {
    render(<InitializeButton {...defaultProps} insufficientTokens={true} />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("shows insufficient tokens message when insufficientTokens is true", () => {
    render(<InitializeButton {...defaultProps} insufficientTokens={true} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Insufficient tokens — resets at midnight UTC",
    );
  });

  it("does not show insufficient tokens message when insufficientTokens is false", () => {
    render(<InitializeButton {...defaultProps} insufficientTokens={false} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  // Click fires onClick
  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<InitializeButton {...defaultProps} onClick={onClick} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  // Does not fire onClick when disabled
  it("does not call onClick when disabled", () => {
    const onClick = vi.fn();
    render(
      <InitializeButton {...defaultProps} disabled={true} onClick={onClick} />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });
});
