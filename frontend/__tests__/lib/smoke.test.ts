import { describe, it, expect } from "vitest";

describe("Vitest setup", () => {
  it("runs a basic test", () => {
    expect(1 + 1).toBe(2);
  });

  it("has jsdom environment", () => {
    expect(typeof document).toBe("object");
    expect(typeof window).toBe("object");
  });

  it("has testing-library matchers available", () => {
    const div = document.createElement("div");
    div.textContent = "hello";
    document.body.appendChild(div);
    expect(div).toBeInTheDocument();
    document.body.removeChild(div);
  });

  it("has firebase mocks loaded", async () => {
    const { initializeApp, getApps } = await import("firebase/app");
    expect(initializeApp).toBeDefined();
    expect(getApps).toBeDefined();
    expect(getApps()).toEqual([]);
  });

  it("has firestore mocks loaded", async () => {
    const { getFirestore, doc, getDoc, setDoc } = await import("firebase/firestore");
    expect(getFirestore).toBeDefined();
    expect(doc).toBeDefined();
    expect(getDoc).toBeDefined();
    expect(setDoc).toBeDefined();
  });
});
