import type { ThoughtEntry, MessageEntry } from "@/lib/glassBoxReducer";
import { formatValue, type ValueFormat } from "@/lib/valueFormat";

export interface TranscriptOutcome {
  dealStatus: string;
  finalSummary: Record<string, unknown> | null;
  elapsedTimeMs: number;
  tokensUsed?: number;
}

export function buildTranscript(
  thoughts: ThoughtEntry[],
  messages: MessageEntry[],
  valueFormat: ValueFormat = "currency",
  outcome?: TranscriptOutcome,
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
      if (m.price != null) lines.push(`  → Proposed: ${formatValue(m.price, valueFormat)}`);
      if (m.status) lines.push(`  → Status: ${m.status}`);
    }
    lines.push("");
  }

  // Outcome section
  if (outcome) {
    lines.push("=== Outcome ===");
    lines.push(`Result: ${outcome.dealStatus}`);
    if (outcome.finalSummary) {
      const summary = outcome.finalSummary;
      if (summary.reason) lines.push(`Reason: ${summary.reason}`);
      if (summary.current_offer != null) {
        lines.push(`Final Value: ${formatValue(Number(summary.current_offer), valueFormat)}`);
      }
      if (summary.turns_completed != null) lines.push(`Turns Completed: ${summary.turns_completed}`);
      if (summary.total_warnings != null) lines.push(`Total Warnings: ${summary.total_warnings}`);

      // Participant summaries
      const participantSummaries = summary.participant_summaries as
        | Array<Record<string, unknown>>
        | undefined;
      if (Array.isArray(participantSummaries) && participantSummaries.length > 0) {
        lines.push("");
        lines.push("--- Participant Summaries ---");
        for (const p of participantSummaries) {
          lines.push(`[${p.name ?? p.role}] ${p.summary}`);
        }
      }

      // Tipping Point
      const tippingPoint = summary.tipping_point as string | undefined;
      if (tippingPoint) {
        lines.push("");
        lines.push("--- Tipping Point ---");
        lines.push(tippingPoint);
      }

      // Evaluation
      const evaluation = summary.evaluation as Record<string, unknown> | undefined;
      if (evaluation && typeof evaluation === "object") {
        lines.push("");
        lines.push("--- Negotiation Evaluation ---");
        if (evaluation.overall_score != null) {
          lines.push(`Overall Score: ${evaluation.overall_score}/10`);
        }
        const dims = evaluation.dimensions as Record<string, number> | undefined;
        if (dims) {
          for (const [key, val] of Object.entries(dims)) {
            lines.push(`  ${key.replace(/_/g, " ")}: ${val}/10`);
          }
        }
        if (evaluation.verdict) {
          lines.push(`Verdict: ${evaluation.verdict}`);
        }
        const interviews = evaluation.participant_interviews as
          | Array<Record<string, unknown>>
          | undefined;
        if (Array.isArray(interviews) && interviews.length > 0) {
          lines.push("");
          lines.push("Participant Satisfaction:");
          for (const p of interviews) {
            const parts = [`${p.role}: ${p.satisfaction_rating}/10`];
            if (p.criticism) parts.push(String(p.criticism));
            lines.push(`  ${parts.join(" — ")}`);
          }
        }
      }
    }
    const elapsedSec = Math.round(outcome.elapsedTimeMs / 1000);
    lines.push(`Time Elapsed: ${elapsedSec}s`);
    if (outcome.tokensUsed != null) {
      const credits = Math.max(1, Math.ceil(outcome.tokensUsed / 1000));
      lines.push(`AI Tokens: ${outcome.tokensUsed.toLocaleString("en-US")} (${credits} credits used)`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

export function downloadTranscript(
  thoughts: ThoughtEntry[],
  messages: MessageEntry[],
  valueFormat: ValueFormat = "currency",
  outcome?: TranscriptOutcome,
): void {
  const text = buildTranscript(thoughts, messages, valueFormat, outcome);
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `negotiation-transcript-${Date.now()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}
