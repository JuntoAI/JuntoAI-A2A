import { describe, it, expect } from "vitest";
import { buildTranscript } from "@/lib/transcript";
import type { ThoughtEntry, MessageEntry } from "@/lib/glassBoxReducer";

describe("buildTranscript", () => {
  const thought: ThoughtEntry = {
    agentName: "Recruiter",
    turnNumber: 1,
    innerThought: "I should offer €100k",
    timestamp: 1000,
  };

  const message: MessageEntry = {
    agentName: "Recruiter",
    turnNumber: 1,
    publicMessage: "I offer €100k",
    proposedPrice: 100000,
    timestamp: 2000,
  };

  it("includes header line", () => {
    const text = buildTranscript([], []);
    expect(text).toContain("=== JuntoAI A2A — Negotiation Transcript ===");
  });

  it("includes thoughts and messages sorted by timestamp", () => {
    const text = buildTranscript([thought], [message]);
    const thoughtIdx = text.indexOf("THOUGHT");
    const messageIdx = text.indexOf("MESSAGE");
    expect(thoughtIdx).toBeLessThan(messageIdx);
  });

  it("formats proposed price in message entries", () => {
    const text = buildTranscript([], [message], "currency");
    expect(text).toContain("→ Proposed: €100,000");
  });

  it("includes regulator status when present", () => {
    const msgWithStatus: MessageEntry = {
      ...message,
      regulatorStatus: "warning",
    };
    const text = buildTranscript([], [msgWithStatus]);
    expect(text).toContain("→ Status: warning");
  });

  it("includes outcome section when provided", () => {
    const text = buildTranscript([], [], "currency", {
      dealStatus: "agreed",
      finalSummary: {
        reason: "Both parties agreed",
        current_offer: 100000,
        turns_completed: 5,
        total_warnings: 1,
      },
      elapsedTimeMs: 30000,
      tokensUsed: 5000,
    });
    expect(text).toContain("=== Outcome ===");
    expect(text).toContain("Result: agreed");
    expect(text).toContain("Reason: Both parties agreed");
    expect(text).toContain("Final Value: €100,000");
    expect(text).toContain("Turns Completed: 5");
    expect(text).toContain("Total Warnings: 1");
    expect(text).toContain("Time Elapsed: 30s");
    expect(text).toContain("AI Tokens: 5,000 (5 credits used)");
  });

  it("handles outcome without finalSummary", () => {
    const text = buildTranscript([], [], "currency", {
      dealStatus: "failed",
      finalSummary: null,
      elapsedTimeMs: 10000,
    });
    expect(text).toContain("Result: failed");
    expect(text).toContain("Time Elapsed: 10s");
  });

  it("includes participant summaries when present", () => {
    const text = buildTranscript([], [], "currency", {
      dealStatus: "agreed",
      finalSummary: {
        participant_summaries: [
          { name: "Alice", role: "buyer", summary: "Got a good deal" },
          { role: "seller", summary: "Acceptable outcome" },
        ],
      },
      elapsedTimeMs: 5000,
    });
    expect(text).toContain("--- Participant Summaries ---");
    expect(text).toContain("[Alice] Got a good deal");
    expect(text).toContain("[seller] Acceptable outcome");
  });

  it("includes tipping point when present", () => {
    const text = buildTranscript([], [], "currency", {
      dealStatus: "agreed",
      finalSummary: {
        tipping_point: "Buyer revealed competing offer",
      },
      elapsedTimeMs: 5000,
    });
    expect(text).toContain("--- Tipping Point ---");
    expect(text).toContain("Buyer revealed competing offer");
  });

  it("includes evaluation section with dimensions and interviews", () => {
    const text = buildTranscript([], [], "currency", {
      dealStatus: "agreed",
      finalSummary: {
        evaluation: {
          overall_score: 7,
          dimensions: {
            fairness: 8,
            mutual_respect: 6,
          },
          verdict: "A balanced negotiation",
          participant_interviews: [
            { role: "Buyer", satisfaction_rating: 8, criticism: "Took too long" },
            { role: "Seller", satisfaction_rating: 6, criticism: null },
          ],
        },
      },
      elapsedTimeMs: 5000,
    });
    expect(text).toContain("--- Negotiation Evaluation ---");
    expect(text).toContain("Overall Score: 7/10");
    expect(text).toContain("fairness: 8/10");
    expect(text).toContain("mutual respect: 6/10");
    expect(text).toContain("Verdict: A balanced negotiation");
    expect(text).toContain("Participant Satisfaction:");
    expect(text).toContain("Buyer: 8/10 — Took too long");
    expect(text).toContain("Seller: 6/10");
  });

  it("handles outcome without tokensUsed", () => {
    const text = buildTranscript([], [], "currency", {
      dealStatus: "failed",
      finalSummary: null,
      elapsedTimeMs: 2000,
    });
    expect(text).not.toContain("AI Tokens");
  });

  it("uses percent value format", () => {
    const msg: MessageEntry = {
      ...message,
      proposedPrice: 0.75,
    };
    const text = buildTranscript([], [msg], "percent");
    expect(text).toContain("→ Proposed:");
  });
});
