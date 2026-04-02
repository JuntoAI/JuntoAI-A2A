"use client";

import { useEffect, useState } from "react";

declare global {
  interface Window {
    gtag: (...args: unknown[]) => void;
  }
}

export default function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem("cookieConsent");
    if (!consent) {
      setVisible(true);
    }
  }, []);

  function accept() {
    localStorage.setItem("cookieConsent", "accepted");
    setVisible(false);
    window.gtag?.("consent", "update", { analytics_storage: "granted" });
  }

  function decline() {
    localStorage.setItem("cookieConsent", "declined");
    setVisible(false);
    window.gtag?.("consent", "update", { analytics_storage: "denied" });
  }

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-label="Cookie consent"
      className="fixed bottom-0 left-0 right-0 z-[10000] bg-brand-charcoal text-white shadow-[0_-4px_20px_rgba(0,0,0,0.3)]"
    >
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 p-4">
        <p className="min-w-[300px] flex-1 text-sm">
          We use cookies to improve your experience and analyze website traffic.{" "}
          <a
            href="https://juntoai.org/privacy-policy.html"
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand-green underline"
          >
            Learn more
          </a>
        </p>
        <div className="flex shrink-0 gap-3">
          <button
            onClick={accept}
            className="rounded bg-brand-blue px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
          >
            Accept
          </button>
          <button
            onClick={decline}
            className="rounded border border-gray-500 bg-transparent px-4 py-2 text-sm text-white transition-colors hover:border-gray-300"
          >
            Decline
          </button>
        </div>
      </div>
    </div>
  );
}
