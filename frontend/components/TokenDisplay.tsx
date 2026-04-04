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

  return (
    <div
      className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700 cursor-default"
      title="Each negotiation costs 1 token. Tokens reset daily at midnight UTC."
    >
      <Coins className="h-4 w-4 text-yellow-500" />
      <span>{formatTokenDisplay(tokenBalance, dailyLimit)}</span>
    </div>
  );
}
