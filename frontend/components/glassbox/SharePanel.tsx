"use client";

import { useState, useCallback, useRef } from "react";
import {
  Linkedin,
  Twitter,
  Facebook,
  Link,
  Mail,
  Check,
  Loader2,
} from "lucide-react";
import { createShare, type CreateShareResponse } from "@/lib/share";

export interface SharePanelProps {
  sessionId: string;
  email: string;
}

type ShareTarget = "linkedin" | "twitter" | "facebook" | "copy" | "email";

export default function SharePanel({ sessionId, email }: SharePanelProps) {
  const [shareData, setShareData] = useState<CreateShareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTarget, setActiveTarget] = useState<ShareTarget | null>(null);
  const [copied, setCopied] = useState(false);
  const [clipboardFallback, setClipboardFallback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const executeShare = useCallback(
    async (target: ShareTarget) => {
      setError(null);

      let data = shareData;

      // Lazy creation: fetch share data on first click
      if (!data) {
        setLoading(true);
        setActiveTarget(target);
        try {
          data = await createShare(sessionId, email);
          setShareData(data);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to create share link");
          setLoading(false);
          setActiveTarget(null);
          return;
        }
        setLoading(false);
        setActiveTarget(null);
      }

      // Execute the platform-specific action
      const { share_url, social_post_text } = data;

      switch (target) {
        case "linkedin":
          window.open(
            `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(share_url)}`,
            "_blank",
            "noopener,noreferrer",
          );
          break;

        case "twitter":
          window.open(
            `https://twitter.com/intent/tweet?text=${encodeURIComponent(social_post_text.twitter)}&url=${encodeURIComponent(share_url)}`,
            "_blank",
            "noopener,noreferrer",
          );
          break;

        case "facebook":
          window.open(
            `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(share_url)}`,
            "_blank",
            "noopener,noreferrer",
          );
          break;

        case "copy":
          try {
            await navigator.clipboard.writeText(share_url);
            setCopied(true);
            setClipboardFallback(null);
            if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
            copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
          } catch {
            // Clipboard API unavailable — show selectable text input fallback
            setClipboardFallback(share_url);
          }
          break;

        case "email":
          window.location.href = data.social_post_text
            ? buildMailto(data)
            : `mailto:?subject=Check out this negotiation&body=${encodeURIComponent(share_url)}`;
          break;
      }
    },
    [shareData, sessionId, email],
  );

  const buttons: {
    target: ShareTarget;
    label: string;
    icon: typeof Linkedin;
    testId: string;
  }[] = [
    { target: "linkedin", label: "LinkedIn", icon: Linkedin, testId: "share-linkedin" },
    { target: "twitter", label: "X", icon: Twitter, testId: "share-twitter" },
    { target: "facebook", label: "Facebook", icon: Facebook, testId: "share-facebook" },
    { target: "copy", label: copied ? "Copied!" : "Copy Link", icon: copied ? Check : Link, testId: "share-copy" },
    { target: "email", label: "Email", icon: Mail, testId: "share-email" },
  ];

  return (
    <div data-testid="share-panel" className="mt-6 border-t border-gray-200 pt-4">
      <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
        Share Results
      </h3>

      <div className="grid grid-cols-2 gap-2 lg:flex lg:flex-row lg:gap-3">
        {buttons.map(({ target, label, icon: Icon, testId }) => {
          const isActive = loading && activeTarget === target;
          return (
            <button
              key={target}
              onClick={() => executeShare(target)}
              disabled={loading}
              data-testid={testId}
              className={`
                flex items-center justify-center gap-2 rounded-lg border px-4 py-2
                text-sm font-medium transition-colors
                ${loading
                  ? "cursor-not-allowed border-gray-200 bg-gray-50 text-gray-400"
                  : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                }
                ${copied && target === "copy" ? "border-green-300 bg-green-50 text-green-700" : ""}
              `}
            >
              {isActive ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Icon className="h-4 w-4" />
              )}
              <span className="hidden sm:inline">{label}</span>
            </button>
          );
        })}
      </div>

      {/* Clipboard fallback: selectable text input */}
      {clipboardFallback && (
        <div className="mt-3 flex items-center gap-2" data-testid="share-copy-fallback">
          <input
            type="text"
            readOnly
            value={clipboardFallback}
            className="flex-1 rounded-md border border-gray-300 bg-gray-50 px-3 py-1.5 text-sm text-gray-700 select-all focus:outline-none focus:ring-2 focus:ring-blue-500"
            onFocus={(e) => e.target.select()}
          />
        </div>
      )}

      {/* Error message */}
      {error && (
        <p className="mt-2 text-sm text-red-600" data-testid="share-error">
          {error}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildMailto(data: CreateShareResponse): string {
  const subject = `JuntoAI A2A Negotiation Results`;
  const body = [
    data.social_post_text.linkedin, // reuse the longer-form text
    "",
    data.share_url,
  ].join("\n");

  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
