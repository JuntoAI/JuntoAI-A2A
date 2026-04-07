"use client";

import { useRouter } from "next/navigation";
import { formatValue, type ValueFormat } from "@/lib/valueFormat";
import UsageSummaryCard from "./UsageSummaryCard";
import type { UsageSummary } from "@/types/sse";

export interface OutcomeReceiptProps {
  dealStatus: "Agreed" | "Blocked" | "Failed";
  finalSummary: Record<string, unknown>;
  elapsedTimeMs: number;
  scenarioOutcomeReceipt: {
    equivalent_human_time: string;
    process_label: string;
  } | null;
  scenarioId: string | null;
  valueFormat?: ValueFormat;
  valueLabel?: string;
  onDownloadTranscript?: () => void;
}

const STATUS_CONFIG: Record<
  OutcomeReceiptProps["dealStatus"],
  { heading: string; borderColor: string; bgColor: string; textColor: string }
> = {
  Agreed: {
    heading: "Deal Agreed",
    borderColor: "border-green-500",
    bgColor: "bg-green-50",
    textColor: "text-green-800",
  },
  Blocked: {
    heading: "Deal Blocked",
    borderColor: "border-yellow-500",
    bgColor: "bg-yellow-50",
    textColor: "text-yellow-800",
  },
  Failed: {
    heading: "Negotiation Failed",
    borderColor: "border-gray-400",
    bgColor: "bg-gray-50",
    textColor: "text-gray-700",
  },
};

export default function OutcomeReceipt({
  dealStatus,
  finalSummary,
  elapsedTimeMs,
  scenarioOutcomeReceipt,
  scenarioId,
  valueFormat = "currency",
  valueLabel = "Price",
  onDownloadTranscript,
}: OutcomeReceiptProps) {
  const router = useRouter();
  const config = STATUS_CONFIG[dealStatus];
  const elapsedSeconds = Math.round(elapsedTimeMs / 1000);

  return (
    <div
      className="animate-fadeIn"
      data-testid="outcome-receipt"
    >
      <div
        className={`rounded-lg border-2 ${config.borderColor} ${config.bgColor} p-6`}
      >
        {/* Status heading */}
        <h2
          className={`text-2xl font-bold mb-4 ${config.textColor}`}
          data-testid="outcome-heading"
        >
          {config.heading}
        </h2>

        {/* Deal content */}
        <div className="mb-6" data-testid="outcome-content">
          {dealStatus === "Agreed" && (
            <div className="space-y-3">
              {finalSummary.outcome ? (
                <p className="text-sm font-medium text-green-900">
                  {String(finalSummary.outcome)}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-4 text-sm text-gray-700">
                {finalSummary.current_offer != null && Number(finalSummary.current_offer) > 0 && (
                  <span>Final {valueLabel}: <span className="font-semibold">{formatValue(Number(finalSummary.current_offer), valueFormat)}</span></span>
                )}
                {finalSummary.turns_completed != null && (
                  <span>Turns: {String(finalSummary.turns_completed)}</span>
                )}
                {finalSummary.total_warnings != null && Number(finalSummary.total_warnings) > 0 && (
                  <span>Warnings: {String(finalSummary.total_warnings)}</span>
                )}
              </div>
            </div>
          )}

          {dealStatus === "Blocked" && (
            <div className="space-y-3">
              {finalSummary.blocked_by ? (
                <p className="text-sm font-semibold text-yellow-900">
                  Blocked by: {String(finalSummary.blocked_by)}
                </p>
              ) : null}
              {finalSummary.reason ? (
                <p className="text-sm text-gray-800 leading-relaxed">
                  {String(finalSummary.reason)}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                {finalSummary.current_offer != null && Number(finalSummary.current_offer) > 0 && (
                  <span>Last Offer: {formatValue(Number(finalSummary.current_offer), valueFormat)}</span>
                )}
                {finalSummary.total_warnings != null && (
                  <span>Total Warnings: {String(finalSummary.total_warnings)}</span>
                )}
              </div>

              {/* Actionable advice for re-running with better outcome */}
              {Array.isArray(finalSummary.advice) && (finalSummary.advice as Array<Record<string, unknown>>).length > 0 && (
                <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 p-4" data-testid="block-advice">
                  <h4 className="text-sm font-semibold text-blue-900 mb-2">
                    How to get a different outcome
                  </h4>
                  {(finalSummary.advice as Array<Record<string, unknown>>).map((item, i) => (
                    <div key={i} className="mb-3 last:mb-0">
                      <p className="text-xs font-medium text-blue-800 mb-1">
                        Adjust <span className="font-bold">{String(item.agent_role)}</span>
                        {item.issue ? ` — ${String(item.issue).slice(0, 120)}` : ""}
                      </p>
                      {item.suggested_prompt ? (
                        <div className="relative">
                          <pre className="text-xs bg-white border border-blue-100 rounded p-2 whitespace-pre-wrap text-gray-700 leading-relaxed">
                            {String(item.suggested_prompt)}
                          </pre>
                          <p className="text-xs text-blue-600 mt-1 italic">
                            Paste this into Advanced Options → {String(item.agent_role)} prompt, then re-run.
                          </p>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {dealStatus === "Failed" && (
            <div className="space-y-3">
              <p className="text-sm text-gray-700">
                {finalSummary.reason
                  ? String(finalSummary.reason)
                  : "Negotiation reached maximum turns without agreement"}
              </p>
              <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                {finalSummary.current_offer != null && Number(finalSummary.current_offer) > 0 && (
                  <span>Last Offer: {formatValue(Number(finalSummary.current_offer), valueFormat)}</span>
                )}
                {finalSummary.total_warnings != null && Number(finalSummary.total_warnings) > 0 && (
                  <span>Warnings: {String(finalSummary.total_warnings)}</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Per-agent argument summaries */}
        {Array.isArray(finalSummary.participant_summaries) && (finalSummary.participant_summaries as Array<Record<string, unknown>>).length > 0 && (
          <div className="border-t border-gray-200 pt-4 mb-6" data-testid="participant-summaries">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
              Participant Summary
            </h3>
            <div className="space-y-2">
              {(finalSummary.participant_summaries as Array<Record<string, unknown>>).map((p, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    p.agent_type === "regulator"
                      ? "bg-red-100 text-red-700"
                      : p.agent_type === "observer"
                        ? "bg-purple-100 text-purple-700"
                        : "bg-blue-100 text-blue-700"
                  }`}>
                    {String(p.name)}
                  </span>
                  <span className="text-gray-700">{String(p.summary)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* LLM Usage Summary */}
        {finalSummary.usage_summary &&
         (finalSummary.usage_summary as UsageSummary).total_calls > 0 && (
          <UsageSummaryCard usageSummary={finalSummary.usage_summary as UsageSummary} />
        )}

        {/* Tipping Point Analysis */}
        {typeof finalSummary.tipping_point === "string" && finalSummary.tipping_point.length > 0 && (
          <div className="border-t border-gray-200 pt-4 mb-6" data-testid="tipping-point-section">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
              Tipping Point
            </h3>
            <p className="text-sm text-gray-700 leading-relaxed">
              {String(finalSummary.tipping_point)}
            </p>
          </div>
        )}

        {/* Evaluation Score */}
        {typeof finalSummary.evaluation === "object" && finalSummary.evaluation !== null && (
          <div className="border-t border-gray-200 pt-4 mb-6" data-testid="evaluation-section">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
              Negotiation Evaluation
            </h3>

            {/* Overall score */}
            {(() => {
              const eval_ = finalSummary.evaluation as Record<string, unknown>;
              const score = Number(eval_.overall_score ?? 0);
              const scoreColor =
                score >= 9 ? "text-emerald-400" :
                score >= 7 ? "text-green-500" :
                score >= 4 ? "text-amber-500" :
                "text-red-500";
              return (
                <div className="flex items-baseline gap-2 mb-4" data-testid="evaluation-score">
                  <span className={`text-4xl font-bold ${scoreColor}`}>{score}</span>
                  <span className="text-lg text-gray-400">/ 10</span>
                </div>
              );
            })()}

            {/* Dimensions */}
            {(() => {
              const eval_ = finalSummary.evaluation as Record<string, unknown>;
              const dims = eval_.dimensions as Record<string, number> | undefined;
              if (!dims) return null;
              return (
                <div className="grid grid-cols-2 gap-3 mb-4" data-testid="evaluation-dimensions">
                  {Object.entries(dims).map(([key, val]) => (
                    <div key={key} className="text-sm">
                      <div className="flex justify-between mb-1">
                        <span className="text-gray-600 capitalize">{key.replace(/_/g, " ")}</span>
                        <span className="font-medium text-gray-800">{val}/10</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            val >= 7 ? "bg-green-500" : val >= 4 ? "bg-amber-400" : "bg-red-400"
                          }`}
                          style={{ width: `${val * 10}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}

            {/* Verdict */}
            {(() => {
              const eval_ = finalSummary.evaluation as Record<string, unknown>;
              if (!eval_.verdict) return null;
              return (
                <p className="text-sm text-gray-700 leading-relaxed mb-4" data-testid="evaluation-verdict">
                  {String(eval_.verdict)}
                </p>
              );
            })()}

            {/* Per-participant satisfaction */}
            {(() => {
              const eval_ = finalSummary.evaluation as Record<string, unknown>;
              const interviews = eval_.participant_interviews as Array<Record<string, unknown>> | undefined;
              if (!interviews || interviews.length === 0) return null;
              return (
                <div className="space-y-2" data-testid="evaluation-participants">
                  {interviews.map((p, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="font-medium text-gray-700">{String(p.role)}</span>
                      <span className={`font-semibold ${
                        Number(p.satisfaction_rating) >= 7 ? "text-green-600" :
                        Number(p.satisfaction_rating) >= 4 ? "text-amber-600" :
                        "text-red-600"
                      }`}>
                        {String(p.satisfaction_rating)}/10
                      </span>
                      {p.criticism ? (
                        <span className="text-gray-500">{String(p.criticism)}</span>
                      ) : null}
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        )}

        {/* ROI Metrics */}
        <div className="border-t border-gray-200 pt-4 mb-6">
          <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
            Performance Metrics
          </h3>

          {/* Measured metrics */}
          <div className="mb-3" data-testid="measured-metrics">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
              Measured
            </p>
            <p className="text-sm font-medium text-gray-900">
              Time Elapsed: {elapsedSeconds}s
            </p>
            {finalSummary.ai_tokens_used != null && Number(finalSummary.ai_tokens_used) > 0 && (
              <p className="text-sm font-medium text-gray-900">
                AI Tokens: {Number(finalSummary.ai_tokens_used).toLocaleString("en-US")} ({Math.max(1, Math.ceil(Number(finalSummary.ai_tokens_used) / 1000))} credits used)
              </p>
            )}
          </div>

          {/* Scenario-estimated metrics */}
          {scenarioOutcomeReceipt && (
            <div data-testid="estimated-metrics">
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-1 italic">
                Industry Estimate
              </p>
              <p className="text-sm text-gray-500 italic">
                Equivalent Human Time: {scenarioOutcomeReceipt.equivalent_human_time}
              </p>
              <p className="text-sm text-gray-500 italic">
                {scenarioOutcomeReceipt.process_label}
              </p>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => router.push("/arena")}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            data-testid="run-another-btn"
          >
            Run Another Scenario
          </button>
          <button
            onClick={() =>
              router.push(
                scenarioId ? `/arena?scenario=${scenarioId}` : "/arena",
              )
            }
            className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            data-testid="reset-variables-btn"
          >
            Reset with Different Variables
          </button>
          {onDownloadTranscript && (
            <button
              onClick={onDownloadTranscript}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              data-testid="download-transcript-btn"
            >
              Download Full Transcript
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
