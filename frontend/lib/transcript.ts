import type { ThoughtEntry, MessageEntry } from "@/lib/glassBoxReducer";

export function buildTranscript(
  thoughts: ThoughtEntry[],
  messages: MessageEntry[],
): string {
  // Merge and sort by timestamp
  const entries = [
    ...thoughts.map((t) => ({
      time: t.timestamp,
      type: "thought" as const,
      agent: t.agentName,
      turn: t.turnNumber,
      text: t.innerThought,
    })),
    ...messages.map((m) => ({
      time: m.timestamp,
      type: "message" as const,
      agent: m.agentName,
      turn: m.turnNumber,
      text: m.publicMessage,
      price: m.proposedPrice,
      status: m.regulatorStatus,
    })),
  ].sort((a, b) => a.time - b.time);

  const lines: string[] = [
    "=== JuntoAI A2A — Negotiation Transcript ===",
    `Generated: ${new Date().toISOString()}`,
    "",
  ];

  for (const e of entries) {
    const label = e.type === "thought" ? "THOUGHT" : "MESSAGE";
    lines.push(`[Turn ${e.turn}] [${label}] ${e.agent}`);
    lines.push(e.text);
    if (e.type === "message") {
      const m = e as typeof e & { price?: number; status?: string };
      if (m.price != null) lines.push(`  → Proposed: $${m.price.toLocaleString()}`);
      if (m.status) lines.push(`  → Status: ${m.status}`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

export function downloadTranscript(
  thoughts: ThoughtEntry[],
  messages: MessageEntry[],
): void {
  const text = buildTranscript(thoughts, messages);
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `negotiation-transcript-${Date.now()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}
