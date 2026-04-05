"use client";

import { useReducer, useMemo, useCallback, useState, useEffect } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { glassBoxReducer, createInitialState } from "@/lib/glassBoxReducer";
import { useSSE } from "@/hooks/useSSE";
import { useSession } from "@/context/SessionContext";
import { downloadTranscript } from "@/lib/transcript";
import { fetchScenarioDetail } from "@/lib/api";
import type { ValueFormat } from "@/lib/valueFormat";
import MetricsDashboard from "@/components/glassbox/MetricsDashboard";
import TerminalPanel from "@/components/glassbox/TerminalPanel";
import ChatPanel from "@/components/glassbox/ChatPanel";
import OutcomeReceipt from "@/components/glassbox/OutcomeReceipt";
import { Spinner } from "@/components/ui/Spinner";

const TERMINAL_STATUSES = new Set(["Agreed", "Blocked", "Failed"]);

function isValidSessionId(id: unknown): id is string {
  return typeof id === "string" && id.length > 0;
}

export default function GlassBoxPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const { email, tokenBalance, dailyLimit } = useSession();

  const sessionId = params?.sessionId;
  const maxTurns = Number(searchParams.get("max_turns")) || 10;
  const scenarioId = searchParams.get("scenario");
  const validSessionId = isValidSessionId(sessionId);

  // Value display config from scenario
  const [valueLabel, setValueLabel] = useState("Current Offer");
  const [valueFormat, setValueFormat] = useState<ValueFormat>("currency");

  useEffect(() => {
    if (!scenarioId) return;
    let cancelled = false;
    fetchScenarioDetail(scenarioId, email ?? undefined)
      .then((detail) => {
        if (cancelled) return;
        const params = detail.negotiation_params;
        if (params.value_label) setValueLabel(params.value_label);
        if (params.value_format) setValueFormat(params.value_format);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [scenarioId]);

  const [state, dispatch] = useReducer(
    glassBoxReducer,
    maxTurns,
    createInitialState,
  );

  const { startTime, stop } = useSSE(
    validSessionId ? (sessionId as string) : null,
    email ?? "",
    maxTurns,
    dispatch,
  );

  const isTerminal = TERMINAL_STATUSES.has(state.dealStatus);
  const isWaitingForFirstEvent =
    state.isConnected &&
    state.thoughts.length === 0 &&
    state.messages.length === 0 &&
    !isTerminal;

  const elapsedTimeMs = useMemo(() => {
    if (!isTerminal || !startTime) return 0;
    return Date.now() - startTime;
  }, [isTerminal, startTime]);

  const handleStop = useCallback(() => {
    stop();
    dispatch({
      type: "NEGOTIATION_COMPLETE",
      payload: {
        event_type: "negotiation_complete",
        session_id: sessionId as string,
        deal_status: "Failed",
        final_summary: {
          reason: "Negotiation ended by user",
          current_offer: state.currentOffer,
          turns_completed: state.turnNumber,
          total_warnings: Object.keys(state.regulatorStatuses).length,
        },
      },
    });
  }, [stop, dispatch, sessionId, state.currentOffer, state.turnNumber, state.regulatorStatuses]);

  const handleDownloadTranscript = useCallback(() => {
    const elapsed = startTime ? Date.now() - startTime : 0;
    const tokensUsed = state.finalSummary?.total_tokens_used as number | undefined;
    downloadTranscript(state.thoughts, state.messages, valueFormat, {
      dealStatus: state.dealStatus,
      finalSummary: state.finalSummary,
      elapsedTimeMs: elapsed,
      tokensUsed,
    });
  }, [state.thoughts, state.messages, state.dealStatus, state.finalSummary, valueFormat, startTime]);

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
      {/* Connecting spinner — before SSE opens */}
      {!state.isConnected && !isTerminal && !state.error && (
        <Spinner message="Connecting to negotiation server…" size="lg" />
      )}

      {/* Warming up spinner — SSE open but no events yet */}
      {isWaitingForFirstEvent && (
        <Spinner message="Agents are warming up… first response incoming" size="lg" />
      )}

      {/* Top: Metrics Dashboard */}
      <MetricsDashboard
        currentOffer={state.currentOffer}
        regulatorStatuses={state.regulatorStatuses}
        turnNumber={state.turnNumber}
        maxTurns={state.maxTurns}
        tokenBalance={tokenBalance}
        dailyLimit={dailyLimit}
        valueLabel={valueLabel}
        valueFormat={valueFormat}
      />

      {/* Terminal + Chat: responsive side-by-side (lg) or stacked */}
      <div className="flex flex-col lg:flex-row gap-4" data-testid="panels-container">
        <div className="flex-1 min-w-0">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Agent Inner Thoughts
          </h2>
          <TerminalPanel
            thoughts={state.thoughts}
            isConnected={state.isConnected}
            dealStatus={state.dealStatus}
          />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Public Conversation
          </h2>
          <ChatPanel
            messages={state.messages}
            isConnected={state.isConnected}
            valueFormat={valueFormat}
          />
        </div>
      </div>

      {/* Stop button — visible while negotiation is running */}
      {!isTerminal && state.isConnected && (
        <div className="flex justify-center">
          <button
            onClick={handleStop}
            className="rounded-lg border border-red-300 bg-white px-6 py-2 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
            data-testid="stop-btn"
          >
            Stop Negotiation
          </button>
        </div>
      )}

      {/* Outcome Receipt overlay when deal reaches terminal status */}
      {isTerminal && (
        <div className="mt-6 space-y-4" data-testid="outcome-overlay">
          <OutcomeReceipt
            dealStatus={state.dealStatus as "Agreed" | "Blocked" | "Failed"}
            finalSummary={state.finalSummary ?? {}}
            elapsedTimeMs={elapsedTimeMs}
            scenarioOutcomeReceipt={null}
            scenarioId={scenarioId}
            valueFormat={valueFormat}
            valueLabel={valueLabel}
          />
          <div className="flex justify-center">
            <button
              onClick={handleDownloadTranscript}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              data-testid="download-transcript-btn"
            >
              Download Full Transcript
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
