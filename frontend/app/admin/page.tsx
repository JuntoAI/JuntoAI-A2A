import { cookies } from "next/headers";
import { backendFetch } from "@/lib/proxy";

interface ScenarioAnalytics {
  scenario_id: string;
  run_count: number;
  avg_tokens_used: number;
}

interface ModelPerformance {
  model_id: string;
  avg_latency_ms: number;
  avg_input_tokens: number;
  avg_output_tokens: number;
  error_count: number;
  total_calls: number;
}

interface RecentSimulation {
  session_id: string;
  scenario_id: string;
  deal_status: string;
  turn_count: number;
  total_tokens_used: number;
  owner_email: string | null;
  created_at: string | null;
}

interface OverviewData {
  total_users: number;
  simulations_today: number;
  active_sse_connections: number;
  ai_tokens_today: number;
  scenario_analytics: ScenarioAnalytics[];
  model_performance: ModelPerformance[];
  recent_simulations: RecentSimulation[];
}

async function fetchOverview(
  cookie: string
): Promise<{ data: OverviewData | null; error: string | null }> {
  try {
    const res = await backendFetch("/api/v1/admin/overview", {
      headers: { Cookie: `admin_session=${cookie}` },
      cache: "no-store",
    });
    if (!res.ok) {
      if (res.status === 401) return { data: null, error: "Session expired. Please log in again." };
      return { data: null, error: `API error: ${res.status}` };
    }
    const data: OverviewData = await res.json();
    return { data, error: null };
  } catch {
    return { data: null, error: "Failed to reach the API server." };
  }
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-brand-charcoal">
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    Agreed: "bg-green-100 text-green-800",
    Blocked: "bg-red-100 text-red-800",
    Failed: "bg-yellow-100 text-yellow-800",
  };
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? "bg-gray-100 text-gray-700"}`}
    >
      {status}
    </span>
  );
}

export default async function AdminOverviewPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get("admin_session");

  if (!session?.value) {
    return (
      <p className="text-sm text-gray-500">
        Not authenticated. Please <a href="/admin/login" className="text-brand-blue underline">log in</a>.
      </p>
    );
  }

  const { data, error } = await fetchOverview(session.value);

  if (error || !data) {
    return (
      <div className="rounded-lg bg-red-50 p-6 text-sm text-red-700">
        <p className="font-medium">Unable to load dashboard</p>
        <p className="mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold text-brand-charcoal">Overview</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total Users" value={data.total_users} />
        <StatCard label="Simulations Today" value={data.simulations_today} />
        <StatCard label="Active SSE Connections" value={data.active_sse_connections} />
        <StatCard label="AI Tokens Today" value={data.ai_tokens_today} />
      </div>

      {/* Scenario Analytics */}
      <section>
        <h3 className="mb-3 text-lg font-medium text-brand-charcoal">Scenario Analytics</h3>
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Scenario</th>
                <th className="px-4 py-3 text-right">Runs</th>
                <th className="px-4 py-3 text-right">Avg Tokens</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.scenario_analytics.length === 0 ? (
                <tr><td colSpan={3} className="px-4 py-6 text-center text-gray-400">No scenario data yet</td></tr>
              ) : (
                data.scenario_analytics.map((s) => (
                  <tr key={s.scenario_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-brand-charcoal">{s.scenario_id}</td>
                    <td className="px-4 py-3 text-right">{s.run_count}</td>
                    <td className="px-4 py-3 text-right">{s.avg_tokens_used.toFixed(1)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Model Performance */}
      <section>
        <h3 className="mb-3 text-lg font-medium text-brand-charcoal">Model Performance</h3>
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3 text-right">Avg Latency (ms)</th>
                <th className="px-4 py-3 text-right">Avg Input Tokens</th>
                <th className="px-4 py-3 text-right">Avg Output Tokens</th>
                <th className="px-4 py-3 text-right">Errors</th>
                <th className="px-4 py-3 text-right">Total Calls</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.model_performance.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-6 text-center text-gray-400">No model data yet</td></tr>
              ) : (
                data.model_performance.map((m) => (
                  <tr key={m.model_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-brand-charcoal">{m.model_id}</td>
                    <td className="px-4 py-3 text-right">{m.avg_latency_ms.toFixed(0)}</td>
                    <td className="px-4 py-3 text-right">{m.avg_input_tokens.toFixed(0)}</td>
                    <td className="px-4 py-3 text-right">{m.avg_output_tokens.toFixed(0)}</td>
                    <td className="px-4 py-3 text-right">
                      {m.error_count > 0 ? (
                        <span className="text-red-600">{m.error_count}</span>
                      ) : (
                        "0"
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">{m.total_calls}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Recent Simulations */}
      <section>
        <h3 className="mb-3 text-lg font-medium text-brand-charcoal">Recent Simulations</h3>
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Session</th>
                <th className="px-4 py-3">Scenario</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Turns</th>
                <th className="px-4 py-3 text-right">Tokens</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.recent_simulations.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-400">No simulations yet</td></tr>
              ) : (
                data.recent_simulations.map((sim) => (
                  <tr key={sim.session_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-brand-charcoal">
                      {sim.session_id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3">{sim.scenario_id}</td>
                    <td className="px-4 py-3"><StatusBadge status={sim.deal_status} /></td>
                    <td className="px-4 py-3 text-right">{sim.turn_count}</td>
                    <td className="px-4 py-3 text-right">{(sim.total_tokens_used ?? 0).toLocaleString()}</td>
                    <td className="px-4 py-3 text-gray-600">{sim.owner_email ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
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
      </section>
    </div>
  );
}
