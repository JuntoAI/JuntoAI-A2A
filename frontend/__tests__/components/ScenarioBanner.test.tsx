import { describe, it, expect } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { createElement } from "react";
import ScenarioBanner from "@/components/ScenarioBanner";

describe("ScenarioBanner", () => {
  afterEach(() => cleanup());

  it("renders scenario text items", () => {
    render(createElement(ScenarioBanner));
    // Each scenario appears twice (duplicated for infinite scroll)
    const items = screen.getAllByText(/landlord wants to raise rent/i);
    expect(items.length).toBe(2);
  });

  it("renders green bullet indicators", () => {
    render(createElement(ScenarioBanner));
    const bullets = screen.getAllByText("●");
    expect(bullets.length).toBeGreaterThan(0);
  });
});
