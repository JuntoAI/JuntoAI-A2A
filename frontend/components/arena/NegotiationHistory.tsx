"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  fetchNegotiationHistory,
  type SessionHistoryResponse,
  type DayGroup,
  type SessionHistoryItem,
} from "@/lib/history";

export interface NegotiationHistoryProps {
  email: string;
  dailyLimit: number;
}

/** Format a YYYY-MM-DD date string as a human-readable label. */
function formatDateLabel(dateStr: string): string {
  const now = new Date();
  const todayUTC = now.toISOString().slice(0, 10);

  const yesterday = new Date(now);
  yesterday.setUTCDate(yesterday.getUTCDate() - 1);
  const yesterdayUTC = yesterday.toISOString().slice(0, 10);

  if (dateStr === todayUTC) return "Today";
  if (dateStr === yesterdayUTC) return "Yesterday";

  // Parse as UTC to avoid timezone shifts
  const [year, month, day] = dateStr.split("-").map(Number);
  const d = new Date(Date.UTC(year, month - 1, day));
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** Return the limit display string — "∞" for Infinity, otherwise the number. */
function formatLimit(dailyLimit: number): string {
  return Number.isFinite(dailyLimit) ? String(dailyLimit) : "∞";
}

const STATUS_STYLES: Record<string, string> = {
  Agreed: "bg-green-100 text-green-800",
  Failed: "bg-red-100 text-red-800",
  Blocked: "bg-yellow-100 text-yellow-800",
};

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-800";
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${style}`}
    >
      {status}
    </span>
  );
}

function SessionRow({ session }: { session: SessionHistoryItem }) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-gray-100 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-900">
          {session.scenario_name}
        </p>
        <p className="text-xs text-gray-500">
          {session.token_cost} {session.token_cost === 1 ? "token" : "tokens"}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <StatusBadge status={session.deal_status} />
        <Link
          href={`/arena/session/${session.session_id}?mode=replay&scenario=${encodeURIComponent(session.scenario_id)}`}
          className="text-xs font-medium text-[#007BFF] hover:underline"
        >
          View
        </Link>
      </div>
    </div>
  );
}

function DayGroupSection({
  group,
  dailyLimit,
  defaultExpanded,
}: {
  group: DayGroup;
  dailyLimit: number;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-500" />
          )}
          <span className="text-sm font-semibold text-[#1C1C1E]">
            {formatDateLabel(group.date)}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          {group.total_token_cost} / {formatLimit(dailyLimit)} tokens used
        </span>
      </button>
      {expanded && (
        <div>
          {group.sessions.map((session) => (
            <SessionRow key={session.session_id} session={session} />
          ))}
        </div>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2].map((i) => (
        <div
          key={i}
          className="animate-pulse rounded-lg border border-gray-200 bg-white p-4"
        >
          <div className="flex items-center justify-between">
            <div className="h-4 w-24 rounded bg-gray-200" />
            <div className="h-3 w-32 rounded bg-gray-200" />
          </div>
          <div className="mt-3 space-y-2">
            <div className="h-3 w-full rounded bg-gray-100" />
            <div className="h-3 w-3/4 rounded bg-gray-100" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function NegotiationHistory({ email, dailyLimit }: NegotiationHistoryProps) {
  const [data, setData] = useState<SessionHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchNegotiationHistory(email);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, [email]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const todayUTC = new Date().toISOString().slice(0, 10);

  return (
    <div
      data-testid="negotiation-history"
      className="mx-auto w-full max-w-4xl space-y-3"
    >
      {loading && <LoadingSkeleton />}

      {!loading && error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-center">
          <p className="text-sm text-red-700">{error}</p>
          <button
            type="button"
            onClick={loadHistory}
            className="mt-2 rounded-md bg-[#007BFF] px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && data && data.days.length === 0 && (
        <p className="py-6 text-center text-sm text-gray-500">
          No negotiations yet. Start one above.
        </p>
      )}

      {!loading &&
        !error &&
        data &&
        data.days.map((group) => (
          <DayGroupSection
            key={group.date}
            group={group}
            dailyLimit={dailyLimit}
            defaultExpanded={group.date === todayUTC}
          />
        ))}
    </div>
  );
}
