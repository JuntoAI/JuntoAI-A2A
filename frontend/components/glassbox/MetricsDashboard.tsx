"use client";

import { formatValue, type ValueFormat } from "@/lib/valueFormat";

export interface MetricsDashboardProps {
  currentOffer: number;
  regulatorStatuses: Record<string, "CLEAR" | "WARNING" | "BLOCKED">;
  turnNumber: number;
  maxTurns: number;
  tokenBalance: number;
  valueLabel?: string;
  valueFormat?: ValueFormat;
}

const STATUS_COLORS: Record<string, string> = {
  CLEAR: "bg-green-500",
  WARNING: "bg-yellow-500",
  BLOCKED: "bg-red-500",
};

export default function MetricsDashboard({
  currentOffer,
  regulatorStatuses,
  turnNumber,
  maxTurns,
  tokenBalance,
  valueLabel = "Current Offer",
  valueFormat = "currency",
}: MetricsDashboardProps) {
  const regulatorEntries = Object.entries(regulatorStatuses);

  return (
    <div
      className="w-full rounded-lg bg-gray-50 p-4"
      data-testid="metrics-dashboard"
    >
      <div className="flex flex-wrap gap-4">
        {/* Current Offer */}
        <div className="flex-1 min-w-[140px] rounded-lg bg-white p-3 shadow-sm">
          <p className="text-xs text-gray-500 uppercase tracking-wide">
            {valueLabel}
          </p>
          <p
            className="text-2xl font-bold text-gray-900 transition-all duration-300"
            data-testid="current-offer"
          >
            {formatValue(currentOffer, valueFormat)}
          </p>
        </div>

        {/* Regulator Traffic Lights */}
        {regulatorEntries.length > 0 && (
          <div className="flex-1 min-w-[140px] rounded-lg bg-white p-3 shadow-sm">
            <p className="text-xs text-gray-500 uppercase tracking-wide">
              Regulator Status
            </p>
            <div className="flex flex-wrap gap-3 mt-1">
              {regulatorEntries.map(([name, status]) => (
                <div
                  key={name}
                  className="flex items-center gap-1.5"
                  data-testid="regulator-traffic-light"
                >
                  <span
                    className={`inline-block h-3 w-3 rounded-full animate-pulse ${STATUS_COLORS[status] ?? "bg-gray-400"}`}
                    data-testid={`traffic-light-${status?.toLowerCase() ?? "unknown"}`}
                  />
                  <span className="text-sm text-gray-700">{name}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Turn Counter */}
        <div className="flex-1 min-w-[140px] rounded-lg bg-white p-3 shadow-sm group relative">
          <p className="text-xs text-gray-500 uppercase tracking-wide flex items-center gap-1">
            Turn Counter
            <span
              className="inline-flex items-center justify-center h-3.5 w-3.5 rounded-full bg-gray-200 text-[9px] font-bold text-gray-500 cursor-help"
              aria-label="What is a turn?"
            >
              ?
            </span>
          </p>
          <p
            className="text-2xl font-bold text-gray-900"
            data-testid="turn-counter"
          >
            Turn: {turnNumber} / {maxTurns}
          </p>
          {/* Tooltip */}
          <div
            role="tooltip"
            className="invisible group-hover:visible absolute left-0 top-full mt-1 z-10 w-64 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg"
          >
            A turn = one negotiator speaking. Regulators and observers respond
            between turns but don&apos;t count as separate turns.
          </div>
        </div>

        {/* Token Balance */}
        <div className="flex-1 min-w-[140px] rounded-lg bg-white p-3 shadow-sm">
          <p className="text-xs text-gray-500 uppercase tracking-wide">
            Token Balance
          </p>
          <p
            className="text-2xl font-bold text-gray-900"
            data-testid="token-balance"
          >
            Tokens: {tokenBalance} / 100
          </p>
        </div>
      </div>
    </div>
  );
}
