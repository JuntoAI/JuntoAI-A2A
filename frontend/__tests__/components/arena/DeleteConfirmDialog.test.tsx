import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DeleteConfirmDialog } from "@/components/arena/DeleteConfirmDialog";

// Mock the API module
vi.mock("@/lib/builder/api", () => ({
  getScenarioSessionCount: vi.fn(),
}));

import { getScenarioSessionCount } from "@/lib/builder/api";

const mockedGetCount = vi.mocked(getScenarioSessionCount);

describe("DeleteConfirmDialog", () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    scenarioId: "scenario-abc",
    scenarioName: "My Test Scenario",
    email: "user@example.com",
    onConfirm: vi.fn().mockResolvedValue(undefined),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetCount.mockResolvedValue({ count: 3 });
  });

  // Req 2.1: Does not render when isOpen=false
  it("does not render when isOpen=false", () => {
    render(<DeleteConfirmDialog {...defaultProps} isOpen={false} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  // Req 2.1: Shows loading state while fetching session count
  it("shows loading state while fetching session count", () => {
    // Never resolve so we stay in loading
    mockedGetCount.mockReturnValue(new Promise(() => {}));
    render(<DeleteConfirmDialog {...defaultProps} />);

    expect(screen.getByText(/checking connected simulations/i)).toBeInTheDocument();
  });

  // Req 2.1: Displays session count message
  it("displays session count message after fetch", async () => {
    mockedGetCount.mockResolvedValue({ count: 3 });
    render(<DeleteConfirmDialog {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText(/this will delete 3 connected simulations/i)).toBeInTheDocument();
    });
  });

  // Req 2.1: Displays "No connected simulations" when count is 0
  it('displays "No connected simulations" when count is 0', async () => {
    mockedGetCount.mockResolvedValue({ count: 0 });
    render(<DeleteConfirmDialog {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText(/no connected simulations/i)).toBeInTheDocument();
    });
  });

  // Req 2.2: Confirm button triggers onConfirm callback
  it("confirm button triggers onConfirm callback", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(<DeleteConfirmDialog {...defaultProps} onConfirm={onConfirm} />);

    // Wait for count to load so Delete button is enabled
    await waitFor(() => {
      expect(screen.getByText(/this will delete 3 connected simulations/i)).toBeInTheDocument();
    });

    const deleteButton = screen.getByRole("button", { name: /delete/i });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledTimes(1);
    });
  });

  // Req 2.3: Cancel button triggers onClose callback
  it("cancel button triggers onClose callback", async () => {
    const onClose = vi.fn();
    render(<DeleteConfirmDialog {...defaultProps} onClose={onClose} />);

    // Wait for session count to settle before clicking cancel
    await waitFor(() => {
      expect(screen.getByText(/this will delete 3 connected simulations/i)).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    fireEvent.click(cancelButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  // Error handling: Shows error when session count fetch fails
  it("shows error when session count fetch fails", async () => {
    mockedGetCount.mockRejectedValue(new Error("Network error"));
    render(<DeleteConfirmDialog {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });
});
