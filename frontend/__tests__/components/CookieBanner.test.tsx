import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { createElement } from "react";
import CookieBanner from "@/components/CookieBanner";

describe("CookieBanner", () => {
  let getItemSpy: ReturnType<typeof vi.spyOn>;
  let setItemSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    getItemSpy = vi.spyOn(Storage.prototype, "getItem");
    setItemSpy = vi.spyOn(Storage.prototype, "setItem");
    window.gtag = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows banner when no consent stored", () => {
    getItemSpy.mockReturnValue(null);
    render(createElement(CookieBanner));
    expect(screen.getByRole("dialog", { name: /cookie consent/i })).toBeInTheDocument();
  });

  it("hides banner when consent already accepted", () => {
    getItemSpy.mockReturnValue("accepted");
    render(createElement(CookieBanner));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("hides banner when consent already declined", () => {
    getItemSpy.mockReturnValue("declined");
    render(createElement(CookieBanner));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("accept button stores consent and hides banner", () => {
    getItemSpy.mockReturnValue(null);
    render(createElement(CookieBanner));
    fireEvent.click(screen.getByText("Accept"));
    expect(setItemSpy).toHaveBeenCalledWith("cookieConsent", "accepted");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.gtag).toHaveBeenCalledWith("consent", "update", { analytics_storage: "granted" });
  });

  it("decline button stores consent and hides banner", () => {
    getItemSpy.mockReturnValue(null);
    render(createElement(CookieBanner));
    fireEvent.click(screen.getByText("Decline"));
    expect(setItemSpy).toHaveBeenCalledWith("cookieConsent", "declined");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.gtag).toHaveBeenCalledWith("consent", "update", { analytics_storage: "denied" });
  });

  it("works when gtag is not defined", () => {
    delete (window as Record<string, unknown>).gtag;
    getItemSpy.mockReturnValue(null);
    render(createElement(CookieBanner));
    expect(() => fireEvent.click(screen.getByText("Accept"))).not.toThrow();
  });
});
