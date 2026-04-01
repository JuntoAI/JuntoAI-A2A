"use client";

import { Coins } from "lucide-react";
import { useSession } from "@/context/SessionContext";
import { formatTokenDisplay } from "@/lib/tokens";

export default function TokenDisplay() {
  const { tokenBalance } = useSession();

  return (
    <div className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700">
      <Coins className="h-4 w-4 text-yellow-500" />
      <span>{formatTokenDisplay(tokenBalance)}</span>
    </div>
  );
}
