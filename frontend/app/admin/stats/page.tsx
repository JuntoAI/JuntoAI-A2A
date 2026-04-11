import { cookies } from "next/headers";
import { backendFetch } from "@/lib/proxy";

interface OutcomeBreakdown {
  agreed: number;
  blocked: number;
  failed: number;
}

interface ModelTokenBreakdown {
  model_id: string;
  tokens_today: number;
  tokens_7d: number;
}

interface ModelPerformance {
  model_id: string;
  avg_response_time_today: number | null;
  avg_response_time_7d: number | null;
}

interface ScenarioPopularity {
  scenario_id: string;
  scenario_name: string;
  count_today: number;
  count_7d: number;
}

interface StatsData {
  unique_users_today: number;
  unique_users_7d: number;
  simulations_today: number;
  simulations_7d: number;
  active_simulations: number;
  outcomes_today: OutcomeBreakdown;
  outcomes_7d: OutcomeBreakdown;
  total_tokens_today: number;
  total_tokens_7d: number;
  model_tokens: ModelTokenBreakdown[];
  model_performance: ModelPerformance[];
  scenario_popularity: ScenarioPopularity[];
  avg_turns_today: number | null;
  avg_turns_7d: number | null;
  custom_scenarios_today: number;
  custom_scenarios_7d: number;
  custom_scenarios_all_time: number;
  custom_agent_sessions_today: number;
  custom_agent_sessions_7d: number;
  custom_agent_sessions_all_time: number;
  generated_at: string;
}

async function fetchStats(
  cookie: string
): Promise<{ data: StatsData | null; error: string | null }> {
  try {
    const res = await backendFetch("/api/v1/admin/stats", {
      headers: { Cookie: `admin_session=${cookie}` },
      cache: "no-store",
    });
    if (!res.ok) {
      if (res.status === 401)
        return { data: null, error: "Session expired. Please log in again." };
      return { data: null, error: `API error: ${res.status}` };
    }
    const data: StatsData = await res.json();
    return { data, error: null };
  } catch {
    return { data: null, error: "Failed to reach the API server." };
  }
}

function fmt(n: number): string {
  return n.toLocaleString("en-US");
}

function fmtAvg(n: number | null): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function StatCard({
  label,
  today,
  sevenDay,
  suffix,
}: {
  label: string;
  today: string;
  sevenDay: string;
  suffix?: string;
}) {
  return (
    <div className="rounded-lg bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <div className="mt-2 flex items-baseline gap-4">
        <div>
          <p className="text-2xl font-semibold text-brand-charcoal">
            {today}
            {suffix && (
              <span className="ml-1 text-sm font-normal text-gray-400">
                {suffix}
              </span>
            )}
          </p>
          <p className="text-xs text-gray-400">Today</p>
        </div>
        <div className="border-l pl-4">
          <p className="text-lg font-semibold text-gray-600">
            {sevenDay}
            {suffix && (
              <span className="ml-1 text-sm font-normal text-gray-400">
                {suffix}
              </span>
            )}
          </p>
          <p className="text-xs text-gray-400">7 days</p>
        </div>
      </div>
    </div>
  );
}

function OutcomeBadge({
  label,
  count,
  color,
}: {
  label: string;
  count: number;
  color: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}
    >
      {label}: {fmt(count)}
    </span>
  );
}

export default async function AdminStatsPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get("admin_session");

  if (!session?.value) {
    return (
      <p className="text-sm text-gray-500">
        Not authenticated. Please{" "}
        <a href="/admin/login" className="text-brand-blue underline">
          log in
        </a>
        .
      </p>
    );
  }

  const { data, error } = await fetchStats(session.value);

  if (error || !data) {
    return (
      <div className="rounded-lg bg-red-50 p-6 text-sm text-red-700">
        <p className="font-medium">Unable to load stats</p>
        <p className="mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-brand-charcoal">
          Platform Stats
        </h2>
        <p className="text-xs text-gray-400">
          Generated{" "}
          {data.generated_at
            ? new Date(data.generated_at).toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })
            : "—"}
        </p>
      </div>

      {/* Top-level metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Unique Users"
          today={fmt(data.unique_users_today)}
          sevenDay={fmt(data.unique_users_7d)}
        />
        <StatCard
          label="Simulations"
          today={fmt(data.simulations_today)}
          sevenDay={fmt(data.simulations_7d)}
        />
        <StatCard
          label="Total Tokens"
          today={fmt(data.total_tokens_today)}
          sevenDay={fmt(data.total_tokens_7d)}
        />
        <StatCard
          label="Avg Turns to Resolution"
          today={fmtAvg(data.avg_turns_today)}
          sevenDay={fmtAvg(data.avg_turns_7d)}
        />
      </div>

      {/* Active + Outcomes */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500">
            Active Simulations
          </p>
          <p className="mt-1 text-2xl font-semibold text-brand-blue">
            {fmt(data.active_simulations)}
          </p>
        </div>
        <div className="rounded-lg bg-white p-5 shadow-sm">
          <p className="mb-2 text-sm font-medium text-gray-500">
            Outcomes Today
          </p>
          <div className="flex flex-wrap gap-2">
            <OutcomeBadge
              label="Agreed"
              count={data.outcomes_today.agreed}
              color="bg-green-100 text-green-800"
            />
            <OutcomeBadge
              label="Blocked"
              count={data.outcomes_today.blocked}
              color="bg-red-100 text-red-800"
            />
            <OutcomeBadge
              label="Failed"
              count={data.outcomes_today.failed}
              color="bg-yellow-100 text-yellow-800"
            />
          </div>
        </div>
        <div className="rounded-lg bg-white p-5 shadow-sm">
          <p className="mb-2 text-sm font-medium text-gray-500">
            Outcomes 7 Days
          </p>
          <div className="flex flex-wrap gap-2">
            <OutcomeBadge
              label="Agreed"
              count={data.outcomes_7d.agreed}
              color="bg-green-100 text-green-800"
            />
            <OutcomeBadge
              label="Blocked"
              count={data.outcomes_7d.blocked}
              color="bg-red-100 text-red-800"
            />
            <OutcomeBadge
              label="Failed"
              count={data.outcomes_7d.failed}
              color="bg-yellow-100 text-yellow-800"
            />
          </div>
        </div>
      </div>

      {/* Custom metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-lg bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Custom Scenarios</p>
          <div className="mt-2 flex items-baseline gap-4">
            <div>
              <p className="text-2xl font-semibold text-brand-charcoal">
                {fmt(data.custom_scenarios_today)}
              </p>
              <p className="text-xs text-gray-400">Today</p>
            </div>
            <div className="border-l pl-4">
              <p className="text-lg font-semibold text-gray-600">
                {fmt(data.custom_scenarios_7d)}
              </p>
              <p className="text-xs text-gray-400">7 days</p>
            </div>
            <div className="border-l pl-4">
              <p className="text-lg font-semibold text-gray-600">
                {fmt(data.custom_scenarios_all_time)}
              </p>
              <p className="text-xs text-gray-400">All time</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500">
            Custom Agent Sessions (BYOA)
          </p>
          <div className="mt-2 flex items-baseline gap-4">
            <div>
              <p className="text-2xl font-semibold text-brand-charcoal">
                {fmt(data.custom_agent_sessions_today)}
              </p>
              <p className="text-xs text-gray-400">Today</p>
            </div>
            <div className="border-l pl-4">
              <p className="text-lg font-semibold text-gray-600">
                {fmt(data.custom_agent_sessions_7d)}
              </p>
              <p className="text-xs text-gray-400">7 days</p>
            </div>
            <div className="border-l pl-4">
              <p className="text-lg font-semibold text-gray-600">
                {fmt(data.custom_agent_sessions_all_time)}
              </p>
              <p className="text-xs text-gray-400">All time</p>
            </div>
          </div>
        </div>
      </div>

      {/* Scenario Popularity */}
      <section>
        <h3 className="mb-3 text-lg font-medium text-brand-charcoal">
          Scenario Popularity
        </h3>
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Scenario</th>
                <th className="px-4 py-3 text-right">Today</th>
                <th className="px-4 py-3 text-right">7 Days</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.scenario_popularity.length === 0 ? (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-6 text-center text-gray-400"
                  >
                    No scenario data yet
                  </td>
                </tr>
              ) : (
                data.scenario_popularity.map((s) => (
                  <tr key={s.scenario_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-brand-charcoal">
                      {s.scenario_name}
                    </td>
                    <td className="px-4 py-3 text-right">{fmt(s.count_today)}</td>
                    <td className="px-4 py-3 text-right">{fmt(s.count_7d)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Per-Model Token Breakdown */}
      <section>
        <h3 className="mb-3 text-lg font-medium text-brand-charcoal">
          Token Usage by Model
        </h3>
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3 text-right">Tokens Today</th>
                <th className="px-4 py-3 text-right">Tokens 7 Days</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.model_tokens.length === 0 ? (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-6 text-center text-gray-400"
                  >
                    No model token data yet
                  </td>
                </tr>
              ) : (
                data.model_tokens.map((m) => (
                  <tr key={m.model_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-brand-charcoal">
                      {m.model_id}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {fmt(m.tokens_today)}
                    </td>
                    <td className="px-4 py-3 text-right">{fmt(m.tokens_7d)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Model Performance */}
      <section>
        <h3 className="mb-3 text-lg font-medium text-brand-charcoal">
          Model Response Times
        </h3>
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3 text-right">Avg Response (ms) Today</th>
                <th className="px-4 py-3 text-right">Avg Response (ms) 7 Days</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.model_performance.length === 0 ? (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-6 text-center text-gray-400"
                  >
                    No performance data yet
                  </td>
                </tr>
              ) : (
                data.model_performance.map((m) => (
                  <tr key={m.model_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-brand-charcoal">
                      {m.model_id}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {fmtAvg(m.avg_response_time_today)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {fmtAvg(m.avg_response_time_7d)}
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
