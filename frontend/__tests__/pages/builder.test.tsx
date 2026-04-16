import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks — must be declared before imports that use them
// ---------------------------------------------------------------------------

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

let mockPersona: string | null = "sales";

vi.mock("@/context/SessionContext", () => ({
  useSession: () => ({
    email: "test@example.com",
    tokenBalance: 50,
    persona: mockPersona,
  }),
}));

const mockStreamBuilderChat = vi.fn();

vi.mock("@/lib/builder/sse-client", () => ({
  streamBuilderChat: (...args: unknown[]) => mockStreamBuilderChat(...args),
}));

vi.mock("@/lib/builder/api", () => ({
  saveScenario: vi.fn(),
}));

// Import AFTER mocks
import BuilderPage from "@/app/(protected)/arena/builder/page";
import { BUILDER_TEMPLATES } from "@/lib/builder/templates";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Builder template pre-fill", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStreamBuilderChat.mockReturnValue({ abort: vi.fn() });
    mockPersona = "sales";
  });

  it("pre-fills sales template when persona is 'sales'", () => {
    mockPersona = "sales";
    render(<BuilderPage />);

    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    expect(input.value).toBe(BUILDER_TEMPLATES.sales);
  });

  it("pre-fills founder template when persona is 'founder'", () => {
    mockPersona = "founder";
    render(<BuilderPage />);

    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    expect(input.value).toBe(BUILDER_TEMPLATES.founder);
  });

  it("shows empty input when persona is null", () => {
    mockPersona = null;
    render(<BuilderPage />);

    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    expect(input.value).toBe("");
  });

  it("template is editable by the user", () => {
    mockPersona = "founder";
    render(<BuilderPage />);

    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    expect(input.value).toBe(BUILDER_TEMPLATES.founder);

    fireEvent.change(input, { target: { value: "My custom scenario" } });
    expect(input.value).toBe("My custom scenario");
  });

  it("template is not auto-sent (no messages rendered on load)", () => {
    mockPersona = "sales";
    render(<BuilderPage />);

    // No chat messages should be rendered — template is only in the input
    expect(screen.queryByTestId("chat-message-user")).not.toBeInTheDocument();
    expect(screen.queryByTestId("chat-message-assistant")).not.toBeInTheDocument();
    // SSE client should not have been called
    expect(mockStreamBuilderChat).not.toHaveBeenCalled();
  });

  it("BUILDER_TEMPLATES contains founder and sales keys", () => {
    expect(BUILDER_TEMPLATES).toHaveProperty("founder");
    expect(BUILDER_TEMPLATES).toHaveProperty("sales");
    expect(typeof BUILDER_TEMPLATES.founder).toBe("string");
    expect(typeof BUILDER_TEMPLATES.sales).toBe("string");
    expect(BUILDER_TEMPLATES.founder.length).toBeGreaterThan(0);
    expect(BUILDER_TEMPLATES.sales.length).toBeGreaterThan(0);
  });

  it("founder template includes expected placeholders", () => {
    expect(BUILDER_TEMPLATES.founder).toContain("[Your Name]");
    expect(BUILDER_TEMPLATES.founder).toContain("[Company Name]");
    expect(BUILDER_TEMPLATES.founder).toContain("[Your LinkedIn URL]");
    expect(BUILDER_TEMPLATES.founder).toContain("[Pitch Deck Link]");
    expect(BUILDER_TEMPLATES.founder).toContain("[Target Investor Name]");
    expect(BUILDER_TEMPLATES.founder).toContain("[VC Firm Name]");
  });

  it("sales template includes expected placeholders", () => {
    expect(BUILDER_TEMPLATES.sales).toContain("[Your Role]");
    expect(BUILDER_TEMPLATES.sales).toContain("[Company Name]");
    expect(BUILDER_TEMPLATES.sales).toContain("[Product/Service Description]");
    expect(BUILDER_TEMPLATES.sales).toContain("[Target Buyer Role]");
    expect(BUILDER_TEMPLATES.sales).toContain("[Deal Size");
    expect(BUILDER_TEMPLATES.sales).toContain("[Objection 1");
  });
});
