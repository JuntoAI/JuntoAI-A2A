import { describe, it, expect, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { createElement } from "react";

// Mock SessionContext to avoid full provider setup
vi.mock("@/context/SessionContext", () => ({
  SessionProvider: ({ children }: { children: React.ReactNode }) =>
    createElement("div", { "data-testid": "session-provider" }, children),
}));

import Providers from "@/components/Providers";

describe("Providers", () => {
  afterEach(() => cleanup());

  it("renders children inside SessionProvider", () => {
    const { getByTestId, getByText } = render(
      createElement(Providers, null, createElement("span", null, "child content"))
    );
    expect(getByTestId("session-provider")).toBeInTheDocument();
    expect(getByText("child content")).toBeInTheDocument();
  });
});
