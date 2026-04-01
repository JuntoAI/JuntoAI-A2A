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

// Track EventSource instances for SSE assertions
let lastEventSource: {
  url: string;
  onopen: (() => void) | null;
  onmessage: ((e: { data: string }) => void) | null;
  onerror: (() => void) | null;
  close: ReturnType<typeof vi.fn>;
} | null = null;

class MockEventSource {
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    lastEventSource = this;
  }
}

vi.stubGlobal("EventSource", MockEventSource);

// Import AFTER mocks
import GlassBoxPage from "@/app/(protected)/arena/session/[sessionId]/page";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  return render(<GlassBoxPage />);
}

/** Simulate SSE connection open + fire events */
function openSSE() {
  act(() => {
    lastEventSource?.onopen?.();
  });
}

function sendSSEMessage(data: Record<string, unknown>) {
  act(() => {
    lastEventSource?.onmessage?.({ data: JSON.stringify(data) });
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Glass Box Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastEventSource = null;
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

  // Req 5.1: SSE connection opens with correct sessionId
  it("opens SSE connection with correct sessionId and email", () => {
    renderPage();

    expect(lastEventSource).not.toBeNull();
    expect(lastEventSource!.url).toContain("sess-abc-123");
    expect(lastEventSource!.url).toContain("email=user%40test.com");
  });

  // Req 10.7: OutcomeReceipt overlay renders when dealStatus is terminal
  it("renders OutcomeReceipt when dealStatus becomes Agreed", () => {
    renderPage();
    openSSE();

    // Send a negotiation_complete event
    sendSSEMessage({
      event_type: "negotiation_complete",
      deal_status: "Agreed",
      final_summary: { price: 100000 },
      session_id: "sess-abc-123",
    });

    expect(screen.getByTestId("outcome-receipt")).toBeInTheDocument();
    expect(screen.getByTestId("outcome-overlay")).toBeInTheDocument();
  });

  it("renders OutcomeReceipt when dealStatus becomes Blocked", () => {
    renderPage();
    openSSE();

    sendSSEMessage({
      event_type: "negotiation_complete",
      deal_status: "Blocked",
      final_summary: { reason: "Regulator blocked" },
      session_id: "sess-abc-123",
    });

    expect(screen.getByTestId("outcome-receipt")).toBeInTheDocument();
    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Blocked");
  });

  it("renders OutcomeReceipt when dealStatus becomes Failed", () => {
    renderPage();
    openSSE();

    sendSSEMessage({
      event_type: "negotiation_complete",
      deal_status: "Failed",
      final_summary: {},
      session_id: "sess-abc-123",
    });

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
    openSSE();

    sendSSEMessage({
      event_type: "error",
      message: "Session not found",
    });

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
  it("does not open SSE when sessionId is invalid", () => {
    mockParams.sessionId = "";

    renderPage();

    expect(lastEventSource).toBeNull();
  });
});
