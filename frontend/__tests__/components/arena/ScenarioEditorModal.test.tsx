import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ScenarioEditorModal } from "@/components/arena/ScenarioEditorModal";

const sampleJson: Record<string, unknown> = {
  name: "Test Scenario",
  description: "A test scenario",
  agents: [{ role: "buyer" }, { role: "seller" }],
};

describe("ScenarioEditorModal", () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    scenarioId: "scenario-123",
    scenarioJson: sampleJson,
    onSave: vi.fn().mockResolvedValue(undefined),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Req 4.1: Renders with formatted JSON in textarea when isOpen=true
  it("renders with 2-space formatted JSON in textarea when isOpen=true", () => {
    render(<ScenarioEditorModal {...defaultProps} />);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();

    const textarea = screen.getByLabelText("Scenario JSON");
    expect(textarea).toHaveValue(JSON.stringify(sampleJson, null, 2));
  });

  // Req 4.1: Does not render when isOpen=false
  it("does not render when isOpen=false", () => {
    render(<ScenarioEditorModal {...defaultProps} isOpen={false} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  // Req 7.3: Name field shows scenario name
  it("name field shows scenario name from JSON", () => {
    render(<ScenarioEditorModal {...defaultProps} />);
    const nameInput = screen.getByLabelText("Scenario Name");
    expect(nameInput).toHaveValue("Test Scenario");
  });

  // Req 4.2: Editing name updates JSON text
  it("editing name updates the name inside JSON text", () => {
    render(<ScenarioEditorModal {...defaultProps} />);

    const nameInput = screen.getByLabelText("Scenario Name");
    fireEvent.change(nameInput, { target: { value: "Renamed Scenario" } });

    expect(nameInput).toHaveValue("Renamed Scenario");

    const textarea = screen.getByLabelText("Scenario JSON");
    const parsed = JSON.parse(textarea.getAttribute("value") || (textarea as HTMLTextAreaElement).value);
    expect(parsed.name).toBe("Renamed Scenario");
  });

  // Req 4.5: Invalid JSON shows red error and disables Save button
  it("shows parse error and disables Save when JSON is invalid", () => {
    render(<ScenarioEditorModal {...defaultProps} />);

    const textarea = screen.getByLabelText("Scenario JSON");
    fireEvent.change(textarea, { target: { value: "{ invalid json !!!" } });

    expect(screen.getByRole("alert")).toBeInTheDocument();

    const saveButton = screen.getByRole("button", { name: /save/i });
    expect(saveButton).toBeDisabled();
  });

  // Req 7.5: Save button calls onSave with parsed JSON
  it("Save button calls onSave with parsed JSON", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ScenarioEditorModal {...defaultProps} onSave={onSave} />);

    const saveButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1);
    });

    const savedArg = onSave.mock.calls[0][0];
    expect(savedArg).toEqual(sampleJson);
  });

  // Req 7.6: Save with validation error displays error inline (onSave rejects)
  it("displays backend validation error inline when onSave rejects", async () => {
    const onSave = vi.fn().mockRejectedValue(new Error("name: must be non-empty"));
    render(<ScenarioEditorModal {...defaultProps} onSave={onSave} />);

    const saveButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("name: must be non-empty")).toBeInTheDocument();
    });

    // Modal should still be open (not closed)
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  // Req 7.3: Cancel button calls onClose
  it("Cancel button calls onClose", () => {
    const onClose = vi.fn();
    render(<ScenarioEditorModal {...defaultProps} onClose={onClose} />);

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    fireEvent.click(cancelButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
