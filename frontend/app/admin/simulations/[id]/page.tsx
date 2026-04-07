import { cookies } from "next/headers";
import Link from "next/link";
import { backendFetch } from "@/lib/proxy";

interface SessionData {
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
  completed_at: string | null;
  duration_seconds: number | null;
}

async function fetchSession(
  id: string,
  cookie: string
): Promise<{ data: SessionData | null; error: string | null }> {
  try {
    const res = await backendFetch(`/api/v1/admin/simulations/${id}/json`, {
      headers: { Cookie: `admin_session=${cookie}` },
      cache: "no-store",
    });
    if (!res.ok) {
      if (res.status === 401) return { data: null, error: "Session expired. Please log in again." };
      if (res.status === 404) return { data: null, error: "Simulation not found." };
      return { data: null, error: `API error: ${res.status}` };
    }
    const data: SessionData = await res.json();
    return { data, error: null };
  } catch {
    return { data: null, error: "Failed to reach the API server." };
  }
}

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between border-b border-gray-100 py-2.5 text-sm last:border-0">
      <span className="font-medium text-gray-500">{label}</span>
      <span className="text-brand-charcoal">{children}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
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

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

export default async function SimulationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const cookieStore = await cookies();
  const session = cookieStore.get("admin_session");

  if (!session?.value) {
    return (
      <p className="text-sm text-gray-500">
        Not authenticated. Please <a href="/admin/login" className="text-brand-blue underline">log in</a>.
      </p>
    );
  }

  const { data, error } = await fetchSession(id, session.value);

  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link href="/admin/simulations" className="text-sm text-brand-blue hover:underline">
          ← Back to Simulations
        </Link>
        <div className="rounded-lg bg-red-50 p-6 text-sm text-red-700">
          <p className="font-medium">Unable to load simulation</p>
          <p className="mt-1">{error}</p>
        </div>
      </div>
    );
  }

  const transcriptUrl = `/api/v1/admin/simulations/${data.session_id}/transcript`;
  const jsonUrl = `/api/v1/admin/simulations/${data.session_id}/json`;

  return (
    <div className="space-y-6">
      <Link href="/admin/simulations" className="text-sm text-brand-blue hover:underline">
        ← Back to Simulations
      </Link>

      <div className="flex items-center gap-4">
        <h2 className="text-xl font-semibold text-brand-charcoal">
          Session <span className="font-mono">{data.session_id.slice(0, 8)}</span>
        </h2>
        <StatusBadge status={data.deal_status} />
      </div>

      {/* Download buttons */}
      <div className="flex gap-3">
        <a
          href={transcriptUrl}
          className="rounded-md bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue/90"
        >
          Download Transcript
        </a>
        <a
          href={jsonUrl}
          className="rounded-md bg-brand-charcoal px-4 py-2 text-sm font-medium text-white hover:bg-brand-charcoal/90"
        >
          Download JSON
        </a>
      </div>

      {/* Session Metadata */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-lg bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold uppercase text-gray-500">Session Metadata</h3>
          <MetaRow label="Session ID">
            <span className="font-mono text-xs">{data.session_id}</span>
          </MetaRow>
          <MetaRow label="Scenario">{data.scenario_id}</MetaRow>
          <MetaRow label="Owner Email">{data.owner_email ?? "—"}</MetaRow>
          <MetaRow label="Outcome"><StatusBadge status={data.deal_status} /></MetaRow>
          <MetaRow label="Turns">{data.turn_count} / {data.max_turns}</MetaRow>
          <MetaRow label="Total AI Tokens">{(data.total_tokens_used ?? 0).toLocaleString()}</MetaRow>
          <MetaRow label="Created">{formatDate(data.created_at)}</MetaRow>
          <MetaRow label="Completed">{formatDate(data.completed_at)}</MetaRow>
          <MetaRow label="Duration">{formatDuration(data.duration_seconds)}</MetaRow>
        </section>

        <section className="rounded-lg bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold uppercase text-gray-500">Agent Configuration</h3>

          <div className="mb-4">
            <p className="mb-1 text-xs font-medium text-gray-500">Model Overrides</p>
            {Object.keys(data.model_overrides).length === 0 ? (
              <p className="text-sm text-gray-400">None</p>
            ) : (
              <div className="space-y-1">
                {Object.entries(data.model_overrides).map(([role, model]) => (
                  <div key={role} className="flex justify-between text-sm">
                    <span className="font-medium text-brand-charcoal">{role}</span>
                    <span className="font-mono text-xs text-gray-600">{model}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <p className="mb-1 text-xs font-medium text-gray-500">Active Toggles</p>
            {data.active_toggles.length === 0 ? (
              <p className="text-sm text-gray-400">None</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {data.active_toggles.map((toggle) => (
                  <span
                    key={toggle}
                    className="inline-block rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700"
                  >
                    {toggle}
                  </span>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
