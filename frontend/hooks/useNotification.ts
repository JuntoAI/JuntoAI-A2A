"use client";

import { useEffect, useRef } from "react";
import { buildNotificationContent } from "@/lib/notificationContent";

export interface UseNotificationOptions {
  sessionId: string;
  dealStatus: "Negotiating" | "Agreed" | "Blocked" | "Failed";
  finalSummary: Record<string, unknown> | null;
}

const TERMINAL_STATUSES = new Set(["Agreed", "Blocked", "Failed"]);
const ICON_PATH = "/juntoai_logo_500x500.png";

/**
 * Hook that fires a browser notification when a negotiation reaches a
 * terminal state while the tab is hidden. Handles permission requests,
 * click-to-focus, deduplication by session ID, and graceful degradation.
 */
export function useNotification(options: UseNotificationOptions): void {
  const { sessionId, dealStatus, finalSummary } = options;
  const sentRef = useRef<Set<string>>(new Set());

  // --- Notification API availability guard (sub-task 2.2) ---
  // If the API isn't available, bail out of all logic.
  // We still declare the hooks above so React's hook order is stable.

  useEffect(() => {
    if (typeof window === "undefined" || !window.Notification) return;

    // --- Permission request on mount (sub-task 2.3) ---
    if (Notification.permission === "default") {
      try {
        Notification.requestPermission().catch((err: unknown) => {
          console.error("useNotification: requestPermission failed", err);
        });
      } catch (err: unknown) {
        // Older browsers may not return a promise
        console.error("useNotification: requestPermission threw", err);
      }
    }
  }, []); // run once on mount

  useEffect(() => {
    if (typeof window === "undefined" || !window.Notification) return;

    // --- Notification dispatch on terminal state (sub-task 2.4) ---
    if (!TERMINAL_STATUSES.has(dealStatus)) return;
    if (Notification.permission !== "granted") return;

    // document.hidden undefined → treat as visible (don't fire)
    if (typeof document === "undefined" || document.hidden !== true) return;

    // --- Deduplication (sub-task 2.6) ---
    if (sentRef.current.has(sessionId)) return;

    const summary = finalSummary ?? {};
    const { title, body } = buildNotificationContent(
      dealStatus as "Agreed" | "Blocked" | "Failed",
      summary,
    );

    try {
      const notification = new Notification(title, {
        body,
        icon: ICON_PATH,
        tag: sessionId,
      });

      // --- Click handler (sub-task 2.5) ---
      notification.onclick = () => {
        window.focus();
        notification.close();
      };
    } catch (err: unknown) {
      // --- Error handling (sub-task 2.7) ---
      console.error("useNotification: Notification constructor threw", err);
    }

    // Mark as sent even if constructor threw to avoid retry loops
    sentRef.current.add(sessionId);
  }, [sessionId, dealStatus, finalSummary]);

  // --- Reset dedup set on unmount (sub-task 2.6) ---
  useEffect(() => {
    return () => {
      sentRef.current.clear();
    };
  }, []);
}
