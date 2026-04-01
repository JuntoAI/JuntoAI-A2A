"use client";

import { useRouter } from "next/navigation";

export interface OutcomeReceiptProps {
  dealStatus: "Agreed" | "Blocked" | "Failed";
  finalSummary: Record<string, unknown>;
  elapsedTimeMs: number;
  scenarioOutcomeReceipt: {
    equivalent_human_time: string;
    process_label: string;
  } | null;
  scenarioId: string | null;
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
            <div>
              <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
                Final Terms
              </h3>
              <dl className="space-y-1">
                {Object.entries(finalSummary).map(([key, value]) => (
                  <div key={key} className="flex gap-2 text-sm">
                    <dt className="font-medium text-gray-700">{key}:</dt>
                    <dd className="text-gray-900">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {dealStatus === "Blocked" && (
            <div>
              <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
                Block Reason
              </h3>
              <p className="text-sm text-gray-900">
                {finalSummary.reason
                  ? String(finalSummary.reason)
                  : Object.entries(finalSummary)
                      .map(([k, v]) => `${k}: ${String(v)}`)
                      .join(", ")}
              </p>
            </div>
          )}

          {dealStatus === "Failed" && (
            <p className="text-sm text-gray-600">
              Negotiation reached maximum turns without agreement
            </p>
          )}
        </div>

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
        </div>
      </div>
    </div>
  );
}
