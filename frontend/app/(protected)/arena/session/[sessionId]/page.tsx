"use client";

import { useReducer, useMemo } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { glassBoxReducer, createInitialState } from "@/lib/glassBoxReducer";
import { useSSE } from "@/hooks/useSSE";
import { useSession } from "@/context/SessionContext";
import MetricsDashboard from "@/components/glassbox/MetricsDashboard";
import TerminalPanel from "@/components/glassbox/TerminalPanel";
import ChatPanel from "@/components/glassbox/ChatPanel";
import OutcomeReceipt from "@/components/glassbox/OutcomeReceipt";

const TERMINAL_STATUSES = new Set(["Agreed", "Blocked", "Failed"]);

function isValidSessionId(id: unknown): id is string {
  return typeof id === "string" && id.length > 0;
}

export default function GlassBoxPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const { email, tokenBalance } = useSession();

  const sessionId = params?.sessionId;
  const maxTurns = Number(searchParams.get("max_turns")) || 10;
  const scenarioId = searchParams.get("scenario");
  const validSessionId = isValidSessionId(sessionId);

  const [state, dispatch] = useReducer(
    glassBoxReducer,
    maxTurns,
    createInitialState,
  );

  const { startTime } = useSSE(
    validSessionId ? (sessionId as string) : null,
    email ?? "",
    maxTurns,
    dispatch,
  );

  const isTerminal = TERMINAL_STATUSES.has(state.dealStatus);

  const elapsedTimeMs = useMemo(() => {
    if (!isTerminal || !startTime) return 0;
    return Date.now() - startTime;
  }, [isTerminal, startTime]);

  // Invalid or missing sessionId
  if (!validSessionId) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-8">
        <p className="text-red-600 text-lg font-medium" data-testid="session-error">
          Invalid or missing session ID.
        </p>
        <Link
          href="/arena"
          className="text-blue-600 underline hover:text-blue-800"
          data-testid="return-to-arena"
        >
          Return to Arena
        </Link>
      </div>
    );
  }

  // SSE / connection error
  if (state.error) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-8">
        <p className="text-red-600 text-lg font-medium" data-testid="sse-error">
          {state.error}
        </p>
        <Link
          href="/arena"
          className="text-blue-600 underline hover:text-blue-800"
          data-testid="return-to-arena"
        >
          Return to Arena
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full space-y-4 p-4">
      {/* Top: Metrics Dashboard */}
      <MetricsDashboard
        currentOffer={state.currentOffer}
        regulatorStatuses={state.regulatorStatuses}
        turnNumber={state.turnNumber}
        maxTurns={state.maxTurns}
        tokenBalance={tokenBalance}
      />

      {/* Terminal + Chat: responsive side-by-side (lg) or stacked */}
      <div className="flex flex-col lg:flex-row gap-4" data-testid="panels-container">
        <div className="flex-1 min-w-0">
          <TerminalPanel
            thoughts={state.thoughts}
            isConnected={state.isConnected}
            dealStatus={state.dealStatus}
          />
        </div>
        <div className="flex-1 min-w-0">
          <ChatPanel
            messages={state.messages}
            isConnected={state.isConnected}
          />
        </div>
      </div>

      {/* Outcome Receipt overlay when deal reaches terminal status */}
      {isTerminal && (
        <div className="mt-6" data-testid="outcome-overlay">
          <OutcomeReceipt
            dealStatus={state.dealStatus as "Agreed" | "Blocked" | "Failed"}
            finalSummary={state.finalSummary ?? {}}
            elapsedTimeMs={elapsedTimeMs}
            scenarioOutcomeReceipt={null}
            scenarioId={scenarioId}
          />
        </div>
      )}
    </div>
  );
}
