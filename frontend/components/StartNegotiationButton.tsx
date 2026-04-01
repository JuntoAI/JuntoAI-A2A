"use client";

import { useSession } from "@/context/SessionContext";

interface StartNegotiationButtonProps {
  /** Token cost for this action. Defaults to 1. */
  cost?: number;
}

export default function StartNegotiationButton({
  cost = 1,
}: StartNegotiationButtonProps) {
  const { tokenBalance } = useSession();

  const insufficientTokens = tokenBalance < cost;

  return (
    <div>
      <button
        disabled={insufficientTokens}
        onClick={() => {
          // Placeholder — actual negotiation start wired in future spec
        }}
        className={`rounded-lg px-6 py-3 font-semibold text-white transition-colors ${
          insufficientTokens
            ? "cursor-not-allowed bg-gray-400"
            : "bg-brand-blue hover:bg-blue-600"
        }`}
      >
        Initialize A2A Protocol
      </button>
      {insufficientTokens && (
        <p className="mt-2 text-sm text-red-600">
          No tokens remaining. Resets at midnight UTC.
        </p>
      )}
    </div>
  );
}
