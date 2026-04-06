"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = "";

interface SimulationItem {
  session_id: string;
  scenario_id: string;
  owner_email: string | null;
  deal_status: string;
  turn_count: number;
  max_turns: number;
  total_tokens_used: number;
  active_toggles: string[];
  model_overrides: Record<string, string>;
  created_at: string | null;
}

interface SimulationsResponse {
  simulations: SimulationItem[];
  next_cursor: string | null;
}

const STATUS_OPTIONS = [
  { label: "All Outcomes", value: "" },
  { label: "Agreed", value: "Agreed" },
  { label: "Blocked", value: "Blocked" },
  { label: "Failed", value: "Failed" },
  { label: "In Progress", value: "In Progress" },
];

function outcomeBadge(status: string) {
  const colors: Record<string, string> = {
    Agreed: "bg-green-100 text-green-800",
    Blocked: "bg-red-100 text-red-800",
    Failed: "bg-yellow-100 text-yellow-800",
    "In Progress": "bg-blue-100 text-blue-800",
  };
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? "bg-gray-100 text-gray-700"}`}
    >
      {status}
    </span>
  );
}

export default function AdminSimulationsPage() {
  const router = useRouter();
  const [simulations, setSimulations] = useState<SimulationItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [scenarioFilter, setScenarioFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [emailFilter, setEmailFilter] = useState("");

  const fetchSimulations = useCallback(
    async (cursor?: string) => {
      const params = new URLSearchParams();
      if (cursor) params.set("cursor", cursor);
      if (scenarioFilter) params.set("scenario_id", scenarioFilter);
      if (statusFilter) params.set("deal_status", statusFilter);
      if (emailFilter) params.set("owner_email", emailFilter);

      const qs = params.toString();
      const url = `${API_URL}/api/v1/admin/simulations${qs ? `?${qs}` : ""}`;

      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) {
        if (res.status === 401) throw new Error("Session expired. Please log in again.");
        throw new Error(`API error: ${res.status}`);
      }
      return (await res.json()) as SimulationsResponse;
    },
    [scenarioFilter, statusFilter, emailFilter]
  );

  // Initial load + filter changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchSimulations()
      .then((data) => {
        if (cancelled) return;
        setSimulations(data.simulations);
        setNextCursor(data.next_cursor);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load simulations");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [fetchSimulations]);

  async function loadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const data = await fetchSimulations(nextCursor);
      setSimulations((prev) => [...prev, ...data.simulations]);
      setNextCursor(data.next_cursor);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load more simulations");
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-brand-charcoal">Simulations</h2>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="scenario-filter" className="mb-1 block text-xs font-medium text-gray-500">
            Scenario
          </label>
          <input
            id="scenario-filter"
            type="text"
            placeholder="e.g. talent-war"
            value={scenarioFilter}
            onChange={(e) => setScenarioFilter(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-brand-charcoal shadow-sm focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
          />
        </div>
        <div>
          <label htmlFor="status-filter" className="mb-1 block text-xs font-medium text-gray-500">
            Outcome
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-brand-charcoal shadow-sm focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="email-filter" className="mb-1 block text-xs font-medium text-gray-500">
            Owner Email
          </label>
          <input
            id="email-filter"
            type="text"
            placeholder="user@example.com"
            value={emailFilter}
            onChange={(e) => setEmailFilter(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-brand-charcoal shadow-sm focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-4 py-3">Session ID</th>
              <th className="px-4 py-3">Scenario</th>
              <th className="px-4 py-3">User Email</th>
              <th className="px-4 py-3">Outcome</th>
              <th className="px-4 py-3 text-right">Turns</th>
              <th className="px-4 py-3 text-right">AI Tokens</th>
              <th className="px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">Loading…</td>
              </tr>
            ) : simulations.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">No simulations found</td>
              </tr>
            ) : (
              simulations.map((sim) => (
                <tr
                  key={sim.session_id}
                  onClick={() => router.push(`/admin/simulations/${sim.session_id}`)}
                  className="cursor-pointer hover:bg-gray-50"
                >
                  <td className="px-4 py-3 font-mono text-xs text-brand-charcoal">
                    {sim.session_id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-3">{sim.scenario_id}</td>
                  <td className="px-4 py-3 text-gray-600">{sim.owner_email ?? "—"}</td>
                  <td className="px-4 py-3">{outcomeBadge(sim.deal_status)}</td>
                  <td className="px-4 py-3 text-right">{sim.turn_count}</td>
                  <td className="px-4 py-3 text-right">{sim.total_tokens_used.toLocaleString()}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {sim.created_at
                      ? new Date(sim.created_at).toLocaleString("en-US", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Load More */}
      {nextCursor && !loading && (
        <div className="flex justify-center">
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="rounded-md bg-brand-charcoal px-4 py-2 text-sm font-medium text-white hover:bg-brand-charcoal/90 disabled:opacity-50"
          >
            {loadingMore ? "Loading…" : "Load More"}
          </button>
        </div>
      )}
    </div>
  );
}
