import { render, screen, fireEvent } from "@testing-library/react";
import {
  AdvancedConfigModal,
  type AdvancedConfigModalProps,
} from "@/components/arena/AdvancedConfigModal";

const defaultModels = [
  { model_id: "gemini-3-flash-preview", family: "gemini" },
  { model_id: "claude-3-5-sonnet", family: "claude" },
  { model_id: "gemini-2.5-pro", family: "gemini" },
];

const baseProps: AdvancedConfigModalProps = {
  isOpen: true,
  agentName: "Recruiter",
  agentRole: "recruiter",
  defaultModelId: "gemini-3-flash-preview",
  availableModels: defaultModels,
  initialCustomPrompt: "",
  initialModelOverride: null,
  initialMemoryStrategy: "structured",
  milestoneSummariesEnabled: false,
  onMilestoneSummariesChange: vi.fn(),
  onSave: vi.fn(),
  onCancel: vi.fn(),
};

function renderModal(overrides: Partial<AdvancedConfigModalProps> = {}) {
  const onSave = vi.fn();
  const onCancel = vi.fn();
  const props = { ...baseProps, onSave, onCancel, ...overrides };
  const result = render(<AdvancedConfigModal {...props} />);
  return { ...result, onSave: props.onSave, onCancel: props.onCancel };
}

describe("AdvancedConfigModal", () => {
  // Req 2.6, 2.7: Modal renders when isOpen is true, does not render when false
  describe("open/close rendering", () => {
    it("renders modal content when isOpen is true", () => {
      renderModal({ isOpen: true });
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText("Advanced Config")).toBeInTheDocument();
    });

    it("does not render anything when isOpen is false", () => {
      renderModal({ isOpen: false });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  // Req 2.7: Cancel button calls onCancel
  describe("Cancel button", () => {
    it("calls onCancel when Cancel button is clicked", () => {
      const { onCancel } = renderModal();
      fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
      expect(onCancel).toHaveBeenCalledTimes(1);
    });
  });

  // Req 2.8: Escape key calls onCancel
  describe("Escape key", () => {
    it("calls onCancel when Escape key is pressed", () => {
      const { onCancel } = renderModal();
      fireEvent.keyDown(document, { key: "Escape" });
      expect(onCancel).toHaveBeenCalledTimes(1);
    });
  });

  // Req 2.10: Backdrop overlay
  describe("backdrop overlay", () => {
    it("renders a fixed backdrop overlay div", () => {
      const { container } = renderModal();
      const backdrop = container.querySelector(".fixed.inset-0");
      expect(backdrop).toBeInTheDocument();
    });

    it("calls onCancel when backdrop is clicked", () => {
      const { container, onCancel } = renderModal();
      const backdrop = container.querySelector(".fixed.inset-0") as HTMLElement;
      fireEvent.click(backdrop);
      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it("does NOT call onCancel when modal dialog content is clicked", () => {
      const { onCancel } = renderModal();
      fireEvent.click(screen.getByRole("dialog"));
      expect(onCancel).not.toHaveBeenCalled();
    });
  });

  // Req 2.6: Save button calls onSave with current values
  describe("Save button", () => {
    it("calls onSave with empty prompt and null model override for defaults", () => {
      const { onSave } = renderModal();
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
      expect(onSave).toHaveBeenCalledWith("", null, "structured");
    });

    it("calls onSave with typed prompt and selected model override", () => {
      const { onSave } = renderModal();
      const textarea = screen.getByPlaceholderText(/Be more aggressive/);
      fireEvent.change(textarea, { target: { value: "Be firm" } });

      const select = screen.getByLabelText("Model");
      fireEvent.change(select, { target: { value: "claude-3-5-sonnet" } });

      fireEvent.click(screen.getByRole("button", { name: /save/i }));
      expect(onSave).toHaveBeenCalledWith("Be firm", "claude-3-5-sonnet", "structured");
    });

    it("calls onSave with null model override when default model is re-selected", () => {
      const { onSave } = renderModal({ initialModelOverride: "claude-3-5-sonnet" });
      const select = screen.getByLabelText("Model");
      fireEvent.change(select, { target: { value: "gemini-3-flash-preview" } });

      fireEvent.click(screen.getByRole("button", { name: /save/i }));
      expect(onSave).toHaveBeenCalledWith("", null, "structured");
    });
  });

  // Req 2.9: Focus trap
  describe("focus trap", () => {
    it("wraps focus from last focusable element to first on Tab", () => {
      renderModal();
      const dialog = screen.getByRole("dialog");
      const focusable = dialog.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      expect(focusable.length).toBeGreaterThan(0);

      const last = focusable[focusable.length - 1];
      last.focus();
      expect(document.activeElement).toBe(last);

      fireEvent.keyDown(document, { key: "Tab" });
      expect(document.activeElement).toBe(focusable[0]);
    });

    it("wraps focus from first focusable element to last on Shift+Tab", () => {
      renderModal();
      const dialog = screen.getByRole("dialog");
      const focusable = dialog.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      expect(focusable.length).toBeGreaterThan(0);

      const first = focusable[0];
      first.focus();
      expect(document.activeElement).toBe(first);

      fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
      expect(document.activeElement).toBe(focusable[focusable.length - 1]);
    });
  });

  // Req 2.4: Placeholder text
  describe("placeholder text", () => {
    it('displays placeholder text containing "e.g., Be more aggressive" in textarea', () => {
      renderModal();
      const textarea = screen.getByPlaceholderText(/e\.g\., Be more aggressive/);
      expect(textarea).toBeInTheDocument();
    });
  });
});
