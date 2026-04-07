"use client";

import { useState } from "react";

interface BroadcastResult {
  total_users: number;
  sent: number;
  failed: number;
  errors: string[];
}

export default function AdminBroadcastPage() {
  const [subject, setSubject] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<BroadcastResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const handleSend = async () => {
    setShowConfirm(false);
    setSending(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/v1/admin/broadcast", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, body_text: bodyText }),
      });

      if (!res.ok) {
        if (res.status === 401) throw new Error("Session expired. Please log in again.");
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail ?? `API error: ${res.status}`);
      }

      const data = (await res.json()) as BroadcastResult;
      setResult(data);
      setSubject("");
      setBodyText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSending(false);
    }
  };

  const canSend = subject.trim().length > 0 && bodyText.trim().length > 0;

  return (
    <div className="mx-auto max-w-2xl">
      <h2 className="mb-6 text-2xl font-semibold text-brand-charcoal">
        Broadcast Email
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        Send an email to all active users. Suspended and banned users are skipped.
      </p>

      <div className="space-y-4 rounded-lg bg-white p-6 shadow-sm">
        <div>
          <label htmlFor="subject" className="mb-1 block text-sm font-medium text-gray-700">
            Subject
          </label>
          <input
            id="subject"
            type="text"
            maxLength={200}
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="e.g. JuntoAI v1.2 is live!"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={sending}
          />
        </div>

        <div>
          <label htmlFor="body" className="mb-1 block text-sm font-medium text-gray-700">
            Message
          </label>
          <textarea
            id="body"
            rows={10}
            maxLength={50000}
            value={bodyText}
            onChange={(e) => setBodyText(e.target.value)}
            placeholder="Write your message here. Line breaks will be preserved."
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={sending}
          />
        </div>

        <button
          type="button"
          onClick={() => setShowConfirm(true)}
          disabled={!canSend || sending}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {sending ? "Sending…" : "Send to All Users"}
        </button>
      </div>

      {/* Confirmation dialog */}
      {showConfirm && (
        <div className="mt-4 rounded-lg border border-yellow-300 bg-yellow-50 p-4">
          <p className="mb-3 text-sm font-medium text-yellow-800">
            Are you sure? This will send an email to every active user.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleSend}
              className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
            >
              Yes, send it
            </button>
            <button
              type="button"
              onClick={() => setShowConfirm(false)}
              className="rounded-md bg-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="mt-4 rounded-lg border border-green-300 bg-green-50 p-4 text-sm text-green-800">
          <p className="font-medium">
            Sent {result.sent} / {result.total_users} emails
            {result.failed > 0 && ` (${result.failed} failed)`}
          </p>
          {result.errors.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-xs text-red-600">
              {result.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
