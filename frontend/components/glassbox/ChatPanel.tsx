"use client";

import { useRef, useEffect, useMemo } from "react";
import type { MessageEntry } from "@/lib/glassBoxReducer";

import { formatValue, type ValueFormat } from "@/lib/valueFormat";

export interface ChatPanelProps {
  messages: MessageEntry[];
  isConnected: boolean;
  valueFormat?: ValueFormat;
}

const AGENT_COLOR_PALETTE = [
  "#007BFF",
  "#00E676",
  "#FF6B6B",
  "#FFD93D",
  "#6C5CE7",
  "#A29BFE",
  "#FD79A8",
  "#00CEC9",
];

const REGULATOR_STATUS_COLORS: Record<string, string> = {
  CLEAR: "text-green-400 bg-green-900/30 border-green-700",
  WARNING: "text-yellow-400 bg-yellow-900/30 border-yellow-700",
  BLOCKED: "text-red-400 bg-red-900/30 border-red-700",
};

export default function ChatPanel({ messages, isConnected, valueFormat = "currency" }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Build a stable agent → color index map based on first-appearance order
  const agentColorMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const msg of messages) {
      if (!map.has(msg.agentName)) {
        map.set(msg.agentName, map.size % AGENT_COLOR_PALETTE.length);
      }
    }
    return map;
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div
      className="max-h-[60vh] overflow-y-auto rounded-lg bg-white p-4 space-y-3"
      data-testid="chat-panel"
    >
      {messages.map((msg, i) => {
        const colorIndex = agentColorMap.get(msg.agentName) ?? 0;
        const agentColor = AGENT_COLOR_PALETTE[colorIndex];

        // Regulator status → system message
        if (msg.regulatorStatus) {
          const statusClass =
            REGULATOR_STATUS_COLORS[msg.regulatorStatus] ?? "";
          return (
            <div
              key={i}
              className={`rounded-md border px-3 py-2 text-sm ${statusClass}`}
              data-testid="regulator-status-message"
            >
              <span className="font-semibold">{msg.agentName}</span>:{" "}
              {msg.regulatorStatus}
              {msg.publicMessage && (
                <span className="ml-1">— {msg.publicMessage}</span>
              )}
            </div>
          );
        }

        return (
          <div key={i} className="text-left">
            <p className="text-xs font-semibold mb-1" style={{ color: agentColor }}>
              {msg.agentName}
            </p>
            <div className="inline-block rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-900">
              <p>{msg.publicMessage}</p>
              {msg.proposedPrice !== undefined && (
                <span
                  className="mt-1 inline-block rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 text-xs font-semibold"
                  data-testid="proposed-price-badge"
                >
                  {formatValue(msg.proposedPrice, valueFormat)}
                </span>
              )}
            </div>
          </div>
        );
      })}

      {isConnected && messages.length > 0 && (
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 animate-spin rounded-full border-2 border-brand-blue/30 border-t-brand-blue" />
          <span className="text-gray-400 text-xs">Agent is thinking…</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
