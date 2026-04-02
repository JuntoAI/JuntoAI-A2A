"use client";

import { useRef, useEffect } from "react";
import type { ThoughtEntry } from "@/lib/glassBoxReducer";

export interface TerminalPanelProps {
  thoughts: ThoughtEntry[];
  isConnected: boolean;
  dealStatus: string;
}

export default function TerminalPanel({
  thoughts,
  isConnected,
  dealStatus,
}: TerminalPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thoughts]);

  return (
    <div
      className="max-h-[60vh] overflow-y-auto rounded-lg p-4 font-mono text-sm"
      style={{ backgroundColor: "var(--dark-charcoal)" }}
      data-testid="terminal-panel"
    >
      {thoughts.length === 0 && isConnected && (
        <p className="text-gray-400 italic">Awaiting agent initialization...</p>
      )}

      {thoughts.map((entry, i) => (
        <div key={i} className="mb-2">
          <span className="text-green-400 font-semibold">
            [{entry.agentName}]
          </span>{" "}
          <span className="text-white">{entry.innerThought}</span>
        </div>
      ))}

      {isConnected && dealStatus === "Negotiating" && (
        <div className="flex items-center gap-2 mt-2">
          <div className="h-3 w-3 animate-spin rounded-full border-2 border-green-400/30 border-t-green-400" />
          <span className="text-green-400/70 text-xs">Agent is thinking…</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
