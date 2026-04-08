import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useNotification } from "@/hooks/useNotification";

// ---------------------------------------------------------------------------
// Mock setup
// ---------------------------------------------------------------------------

let notificationInstances: Array<{
  title: string;
  options: NotificationOptions;
  close: ReturnType<typeof vi.fn>;
  onclick: (() => void) | null;
}>;
let originalNotification: typeof globalThis.Notification;
let hiddenDescriptor: PropertyDescriptor | undefined;

function makeMockNotification(permission: NotificationPermission = "granted") {
  const MockNotification = vi.fn().mockImplementation(function (
    this: unknown,
    title: string,
    options: NotificationOptions,
  ) {
    const instance = { title, options, close: vi.fn(), onclick: null };
    notificationInstances.push(instance);
    return instance;
  }) as unknown as typeof Notification;

  MockNotification.permission = permission;
  MockNotification.requestPermission = vi.fn().mockResolvedValue(permission);

  Object.defineProperty(globalThis, "Notification", {
    value: MockNotification,
    writable: true,
    configurable: true,
  });

  return MockNotification;
}

function setDocumentHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", {
    value: hidden,
    writable: true,
    configurable: true,
  });
}

beforeEach(() => {
  notificationInstances = [];
  originalNotification = globalThis.Notification;
  hiddenDescriptor = Object.getOwnPropertyDescriptor(document, "hidden");
});

afterEach(() => {
  Object.defineProperty(globalThis, "Notification", {
    value: originalNotification,
    writable: true,
    configurable: true,
  });

  if (hiddenDescriptor) {
    Object.defineProperty(document, "hidden", hiddenDescriptor);
  } else {
    Object.defineProperty(document, "hidden", {
      value: true,
      writable: true,
      configurable: true,
    });
  }

  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useNotification", () => {
  // -----------------------------------------------------------------------
  // Permission request on mount
  // -----------------------------------------------------------------------

  describe("permission request on mount", () => {
    it("calls requestPermission when permission is 'default'", () => {
      const Mock = makeMockNotification("default" as NotificationPermission);

      const { unmount } = renderHook(() =>
        useNotification({
          sessionId: "s1",
          dealStatus: "Negotiating",
          finalSummary: null,
        }),
      );

      expect(Mock.requestPermission).toHaveBeenCalledOnce();
      unmount();
    });

    it("does NOT call requestPermission when permission is 'granted'", () => {
      const Mock = makeMockNotification("granted");

      const { unmount } = renderHook(() =>
        useNotification({
          sessionId: "s1",
          dealStatus: "Negotiating",
          finalSummary: null,
        }),
      );

      expect(Mock.requestPermission).not.toHaveBeenCalled();
      unmount();
    });

    it("does NOT call requestPermission when permission is 'denied'", () => {
      const Mock = makeMockNotification("denied");

      const { unmount } = renderHook(() =>
        useNotification({
          sessionId: "s1",
          dealStatus: "Negotiating",
          finalSummary: null,
        }),
      );

      expect(Mock.requestPermission).not.toHaveBeenCalled();
      unmount();
    });
  });

  // -----------------------------------------------------------------------
  // requestPermission rejection
  // -----------------------------------------------------------------------

  describe("requestPermission rejection", () => {
    it("logs error and does not throw when requestPermission rejects", () => {
      const Mock = makeMockNotification("default" as NotificationPermission);
      Mock.requestPermission = vi.fn().mockRejectedValue(new Error("denied by user"));
      const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

      const { unmount } = renderHook(() =>
        useNotification({
          sessionId: "s1",
          dealStatus: "Negotiating",
          finalSummary: null,
        }),
      );

      // The rejection is async — flush microtasks
      return new Promise<void>((resolve) => {
        setTimeout(() => {
          expect(errorSpy).toHaveBeenCalledWith(
            "useNotification: requestPermission failed",
            expect.any(Error),
          );
          unmount();
          resolve();
        }, 10);
      });
    });
  });

  // -----------------------------------------------------------------------
  // API unavailable
  // -----------------------------------------------------------------------

  describe("API unavailable", () => {
    it("does not throw when window.Notification is undefined", () => {
      Object.defineProperty(globalThis, "Notification", {
        value: undefined,
        writable: true,
        configurable: true,
      });

      expect(() => {
        const { unmount } = renderHook(() =>
          useNotification({
            sessionId: "s1",
            dealStatus: "Agreed",
            finalSummary: { current_offer: "$100" },
          }),
        );
        unmount();
      }).not.toThrow();
    });
  });

  // -----------------------------------------------------------------------
  // Click handler
  // -----------------------------------------------------------------------

  describe("click handler", () => {
    it("calls window.focus() and notification.close() on click", () => {
      makeMockNotification("granted");
      setDocumentHidden(true);
      const focusSpy = vi.spyOn(window, "focus").mockImplementation(() => {});

      const { unmount } = renderHook(() =>
        useNotification({
          sessionId: "click-test",
          dealStatus: "Agreed",
          finalSummary: { current_offer: "$500" },
        }),
      );

      expect(notificationInstances).toHaveLength(1);
      const notification = notificationInstances[0];

      // Simulate click
      expect(notification.onclick).toBeTypeOf("function");
      notification.onclick!();

      expect(focusSpy).toHaveBeenCalledOnce();
      expect(notification.close).toHaveBeenCalledOnce();
      unmount();
    });
  });

  // -----------------------------------------------------------------------
  // Permission denied skip
  // -----------------------------------------------------------------------

  describe("permission denied skip", () => {
    it("does not construct a notification when permission is denied", () => {
      makeMockNotification("denied");
      setDocumentHidden(true);

      const { unmount } = renderHook(() =>
        useNotification({
          sessionId: "denied-test",
          dealStatus: "Failed",
          finalSummary: { reason: "timeout" },
        }),
      );

      expect(notificationInstances).toHaveLength(0);
      unmount();
    });
  });

  // -----------------------------------------------------------------------
  // Constructor throws
  // -----------------------------------------------------------------------

  describe("constructor throws", () => {
    it("catches constructor error and logs to console", () => {
      const ThrowingNotification = vi.fn().mockImplementation(() => {
        throw new Error("SecurityError");
      }) as unknown as typeof Notification;

      ThrowingNotification.permission = "granted";
      ThrowingNotification.requestPermission = vi.fn().mockResolvedValue("granted");

      Object.defineProperty(globalThis, "Notification", {
        value: ThrowingNotification,
        writable: true,
        configurable: true,
      });

      setDocumentHidden(true);
      const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

      expect(() => {
        const { unmount } = renderHook(() =>
          useNotification({
            sessionId: "throw-test",
            dealStatus: "Blocked",
            finalSummary: { blocked_by: "Regulator" },
          }),
        );
        unmount();
      }).not.toThrow();

      expect(errorSpy).toHaveBeenCalledWith(
        "useNotification: Notification constructor threw",
        expect.any(Error),
      );
    });
  });

  // -----------------------------------------------------------------------
  // Unmount resets tracking
  // -----------------------------------------------------------------------

  describe("unmount resets tracking", () => {
    it("fires notification again after unmount and remount for same session", () => {
      makeMockNotification("granted");
      setDocumentHidden(true);

      // First mount — should fire
      const { unmount: unmount1 } = renderHook(() =>
        useNotification({
          sessionId: "reset-test",
          dealStatus: "Agreed",
          finalSummary: { current_offer: "$200" },
        }),
      );

      expect(notificationInstances).toHaveLength(1);
      unmount1();

      // Second mount with same session — should fire again because unmount cleared tracking
      const { unmount: unmount2 } = renderHook(() =>
        useNotification({
          sessionId: "reset-test",
          dealStatus: "Agreed",
          finalSummary: { current_offer: "$200" },
        }),
      );

      expect(notificationInstances).toHaveLength(2);
      unmount2();
    });
  });
});
