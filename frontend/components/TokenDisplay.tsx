"use client";

import { Coins } from "lucide-react";
import { useSession } from "@/context/SessionContext";
import { isLocalMode } from "@/lib/runMode";
import { formatTokenDisplay } from "@/lib/tokens";

export default function TokenDisplay() {
  const { tokenBalance, dailyLimit } = useSession();

  if (isLocalMode) {
    return (
      <div
        className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700 cursor-default"
        title="Local mode — unlimited tokens"
      >
        <Coins className="h-4 w-4 text-yellow-500" />
        <span>Unlimited</span>
      </div>
    );
  }

  const tierHint =
    dailyLimit < 50
      ? " Verify your email to unlock 50 tokens/day."
      : dailyLimit < 100
        ? " Complete your profile to unlock 100 tokens/day."
        : "";

  return (
    <div
      className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700 cursor-default"
      title={`1 token per 1,000 AI tokens used (rounded up). Resets daily at midnight UTC.${tierHint}`}
    >
      <Coins className="h-4 w-4 text-yellow-500" />
      <span>{formatTokenDisplay(tokenBalance, dailyLimit)}</span>
    </div>
  );
}
