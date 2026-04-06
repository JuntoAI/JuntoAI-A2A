"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = "";

interface UserItem {
  email: string;
  signed_up_at: string | null;
  token_balance: number;
  last_reset_date: string | null;
  tier: number;
  user_status: string;
}

interface UsersResponse {
  users: UserItem[];
  next_cursor: string | null;
  total_count: number | null;
}

const TIER_OPTIONS = [
  { label: "All Tiers", value: "" },
  { label: "Tier 1", value: "1" },
  { label: "Tier 2", value: "2" },
  { label: "Tier 3", value: "3" },
];

const STATUS_OPTIONS = [
  { label: "All Statuses", value: "" },
  { label: "Active", value: "active" },
  { label: "Suspended", value: "suspended" },
  { label: "Banned", value: "banned" },
];

function tierBadge(tier: number) {
  const colors: Record<number, string> = {
    1: "bg-gray-100 text-gray-700",
    2: "bg-blue-100 text-blue-800",
    3: "bg-green-100 text-green-800",
  };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[tier] ?? "bg-gray-100 text-gray-700"}`}>
      Tier {tier}
    </span>
  );
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    active: "bg-green-100 text-green-800",
    suspended: "bg-yellow-100 text-yellow-800",
    banned: "bg-red-100 text-red-800",
  };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? "bg-gray-100 text-gray-700"}`}>
      {status}
    </span>
  );
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [tierFilter, setTierFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const fetchUsers = useCallback(
    async (cursor?: string) => {
      const params = new URLSearchParams();
      if (cursor) params.set("cursor", cursor);
      if (tierFilter) params.set("tier", tierFilter);
      if (statusFilter) params.set("status", statusFilter);

      const qs = params.toString();
      const url = `${API_URL}/api/v1/admin/users${qs ? `?${qs}` : ""}`;

      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) {
        if (res.status === 401) throw new Error("Session expired. Please log in again.");
        throw new Error(`API error: ${res.status}`);
      }
      return (await res.json()) as UsersResponse;
    },
    [tierFilter, statusFilter]
  );

  // Initial load + filter changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchUsers()
      .then((data) => {
        if (cancelled) return;
        setUsers(data.users);
        setNextCursor(data.next_cursor);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load users");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [fetchUsers]);

  async function loadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const data = await fetchUsers(nextCursor);
      setUsers((prev) => [...prev, ...data.users]);
      setNextCursor(data.next_cursor);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load more users");
    } finally {
      setLoadingMore(false);
    }
  }

  async function adjustTokens(email: string, currentBalance: number) {
    const input = prompt(`Adjust token balance for ${email}\nCurrent: ${currentBalance}\n\nEnter new balance:`);
    if (input === null) return;
    const newBalance = parseInt(input, 10);
    if (isNaN(newBalance) || newBalance < 0) {
      alert("Token balance must be a non-negative integer.");
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/v1/admin/users/${encodeURIComponent(email)}/tokens`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token_balance: newBalance }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        alert(body?.detail ?? `Failed to update tokens: ${res.status}`);
        return;
      }
      setUsers((prev) =>
        prev.map((u) => (u.email === email ? { ...u, token_balance: newBalance } : u))
      );
    } catch {
      alert("Network error while updating tokens.");
    }
  }

  async function changeStatus(email: string, currentStatus: string) {
    const options = ["active", "suspended", "banned"].filter((s) => s !== currentStatus);
    const input = prompt(
      `Change status for ${email}\nCurrent: ${currentStatus}\n\nEnter new status (${options.join(", ")}):`
    );
    if (input === null) return;
    const newStatus = input.trim().toLowerCase();
    if (!["active", "suspended", "banned"].includes(newStatus)) {
      alert("Status must be one of: active, suspended, banned.");
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/v1/admin/users/${encodeURIComponent(email)}/status`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_status: newStatus }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        alert(body?.detail ?? `Failed to update status: ${res.status}`);
        return;
      }
      setUsers((prev) =>
        prev.map((u) => (u.email === email ? { ...u, user_status: newStatus } : u))
      );
    } catch {
      alert("Network error while updating status.");
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-brand-charcoal">Users</h2>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-brand-charcoal shadow-sm focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
        >
          {TIER_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-brand-charcoal shadow-sm focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
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
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Tier</th>
              <th className="px-4 py-3 text-right">Token Balance</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Signed Up</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading…</td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">No users found</td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.email} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-brand-charcoal">{user.email}</td>
                  <td className="px-4 py-3">{tierBadge(user.tier)}</td>
                  <td className="px-4 py-3 text-right">{user.token_balance}</td>
                  <td className="px-4 py-3">{statusBadge(user.user_status)}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {user.signed_up_at
                      ? new Date(user.signed_up_at).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => adjustTokens(user.email, user.token_balance)}
                        className="rounded bg-brand-blue/10 px-2 py-1 text-xs font-medium text-brand-blue hover:bg-brand-blue/20"
                      >
                        Tokens
                      </button>
                      <button
                        onClick={() => changeStatus(user.email, user.user_status)}
                        className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
                      >
                        Status
                      </button>
                    </div>
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
