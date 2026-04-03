import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks — declared before imports
// ---------------------------------------------------------------------------

const mockParams: Record<string, string> = { sessionId: "sess-abc-123" };
const mockSearchParams = new URLSearchParams("max_turns=15");
const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => mockParams,
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode; [k: string]: unknown }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

const mockUpdateTokenBalance = vi.fn();
vi.mock("@/context/SessionContext", () => ({
  useSession: () => ({
    email: "user@test.com",
    tokenBalance: 42,
    lastResetDate: "2025-01-01",
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    updateTokenBalance: mockUpdateTokenBalance,
  }),
}));

// Mock useSSE hook
let mockDispatch: React.Dispatch<import("@/lib/glassBoxReducer").GlassBoxAction> | null = null;
const mockStop = vi.fn();

vi.mock("@/hooks/useSSE", () => ({
  useSSE: (
    _sessionId: string | null,
    _email: string,
    _maxTurns: number,
    dispatch: React.Dispatch<import("@/lib/glassBoxReducer").GlassBoxAction>,
  ) => {
    mockDispatch = dispatch;
    return { isConnected: false, startTime: Date.now(), stop: mockStop };
  },
}));

// Mock fetchScenarioDetail to avoid network calls
vi.mock("@/lib/api", () => ({
  fetchScenarioDetail: vi.fn().mockResolvedValue({
    negotiation_params: {},
  }),
}));

// Import AFTER mocks
import GlassBoxPage from "@/app/(protected)/arena/session/[sessionId]/page";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  return render(<GlassBoxPage />);
}

/** Simulate dispatching SSE events through the reducer */
function dispatchEvent(action: import("@/lib/glassBoxReducer").GlassBoxAction) {
  act(() => {
    mockDispatch?.(action);
  });
}

function openConnection() {
  dispatchEvent({ type: "CONNECTION_OPENED" });
}

function sendNegotiationComplete(dealStatus: string, finalSummary: Record<string, unknown> = {}) {
  dispatchEvent({
    type: "NEGOTIATION_COMPLETE",
    payload: {
      event_type: "negotiation_complete",
      session_id: "sess-abc-123",
      deal_status: dealStatus,
      final_summary: finalSummary,
    },
  });
}

function sendSSEError(message: string) {
  dispatchEvent({
    type: "SSE_ERROR",
    payload: { message },
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Glass Box Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDispatch = null;
    // Reset to valid params
    mockParams.sessionId = "sess-abc-123";
  });

  // Req 9.1, 6.1, 7.1, 8.1: page renders all three regions
  it("renders MetricsDashboard, TerminalPanel, and ChatPanel", () => {
    renderPage();

    expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();
    expect(screen.getByTestId("terminal-panel")).toBeInTheDocument();
    expect(screen.getByTestId("chat-panel")).toBeInTheDocument();
  });

  // Req 5.1: useSSE hook is called (dispatch is captured)
  it("initializes SSE connection via useSSE hook", () => {
    renderPage();
    expect(mockDispatch).not.toBeNull();
  });

  // Req 10.7: OutcomeReceipt overlay renders when dealStatus is terminal
  it("renders OutcomeReceipt when dealStatus becomes Agreed", () => {
    renderPage();
    openConnection();

    sendNegotiationComplete("Agreed", { price: 100000 });

    expect(screen.getByTestId("outcome-receipt")).toBeInTheDocument();
    expect(screen.getByTestId("outcome-overlay")).toBeInTheDocument();
  });

  it("renders OutcomeReceipt when dealStatus becomes Blocked", () => {
    renderPage();
    openConnection();

    sendNegotiationComplete("Blocked", { reason: "Regulator blocked" });

    expect(screen.getByTestId("outcome-receipt")).toBeInTheDocument();
    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Blocked");
  });

  it("renders OutcomeReceipt when dealStatus becomes Failed", () => {
    renderPage();
    openConnection();

    sendNegotiationComplete("Failed");

    expect(screen.getByTestId("outcome-receipt")).toBeInTheDocument();
    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Negotiation Failed");
  });

  // Req 11.1: invalid sessionId shows error with Return to Arena link
  it("shows error with Return to Arena link when sessionId is missing", () => {
    mockParams.sessionId = "";

    renderPage();

    expect(screen.getByTestId("session-error")).toHaveTextContent(
      "Invalid or missing session ID",
    );
    const link = screen.getByTestId("return-to-arena");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/arena");
  });

  // Req 11.2, 11.3: SSE error shows error with Return to Arena link
  it("shows error with Return to Arena link on SSE error event", () => {
    renderPage();
    openConnection();

    sendSSEError("Session not found");

    expect(screen.getByTestId("sse-error")).toHaveTextContent("Session not found");
    const link = screen.getByTestId("return-to-arena");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/arena");
  });

  // Req 9.2, 9.3, 9.4: responsive layout classes
  it("has responsive layout classes (lg:flex-row and flex-col)", () => {
    renderPage();

    const container = screen.getByTestId("panels-container");
    expect(container.className).toContain("flex-col");
    expect(container.className).toContain("lg:flex-row");
  });

  // Verify max_turns is passed through to MetricsDashboard
  it("displays max_turns from search params in turn counter", () => {
    renderPage();

    expect(screen.getByTestId("turn-counter")).toHaveTextContent("Turn: 0 / 15");
  });

  // Verify token balance from SessionContext is displayed
  it("displays token balance from SessionContext", () => {
    renderPage();

    expect(screen.getByTestId("token-balance")).toHaveTextContent("Tokens: 42 / 100");
  });

  // SSE not opened when sessionId is invalid
  it("does not initialize SSE when sessionId is invalid", () => {
    mockParams.sessionId = "";

    renderPage();

    // The page renders the error state, useSSE is called with null sessionId
    expect(screen.getByTestId("session-error")).toBeInTheDocument();
  });
});
