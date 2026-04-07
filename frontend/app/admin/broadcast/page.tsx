"use client";

import { useState } from "react";

interface BroadcastResult {
  total_users: number;
  sent: number;
  failed: number;
  errors: string[];
}

interface PreviewData {
  recipients: string[];
  total_recipients: number;
  subject: string;
  body_html: string;
  sender: string;
}

export default function AdminBroadcastPage() {
  const [subject, setSubject] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [sending, setSending] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [result, setResult] = useState<BroadcastResult | null>(null);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const canSend = subject.trim().length > 0 && bodyText.trim().length > 0;

  const handlePreview = async () => {
    setPreviewing(true);
    setError(null);
    setPreview(null);
    setResult(null);

    try {
      const res = await fetch("/api/v1/admin/broadcast/preview", {
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

      const data = (await res.json()) as PreviewData;
      setPreview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setPreviewing(false);
    }
  };

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
      setPreview(null);
      setSubject("");
      setBodyText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <h2 className="mb-6 text-2xl font-semibold text-brand-charcoal">
        Broadcast Email
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        Send an email to all active users. Suspended and banned users are skipped.
      </p>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Compose panel */}
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
              onChange={(e) => { setSubject(e.target.value); setPreview(null); }}
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
              rows={12}
              maxLength={50000}
              value={bodyText}
              onChange={(e) => { setBodyText(e.target.value); setPreview(null); }}
              placeholder="Write your message here. Line breaks will be preserved."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              disabled={sending}
            />
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={handlePreview}
              disabled={!canSend || previewing || sending}
              className="rounded-md bg-gray-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {previewing ? "Loading preview…" : "Preview"}
            </button>
            <button
              type="button"
              onClick={() => setShowConfirm(true)}
              disabled={!canSend || sending}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {sending ? "Sending…" : "Send to All Users"}
            </button>
          </div>
        </div>

        {/* Preview panel */}
        <div className="space-y-4">
          {preview && (
            <>
              {/* Recipient list */}
              <div className="rounded-lg bg-white p-5 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-brand-charcoal">
                    Recipients
                  </h3>
                  <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                    {preview.total_recipients} user{preview.total_recipients !== 1 ? "s" : ""}
                  </span>
                </div>
                <p className="mb-2 text-xs text-gray-500">
                  From: {preview.sender}
                </p>
                <div className="max-h-48 overflow-y-auto rounded border border-gray-100 bg-gray-50 p-3">
                  {preview.recipients.length === 0 ? (
                    <p className="text-sm text-gray-400">No active users found.</p>
                  ) : (
                    <ul className="space-y-1">
                      {preview.recipients.map((email) => (
                        <li key={email} className="text-xs text-gray-700 font-mono">
                          {email}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {/* Email preview */}
              <div className="rounded-lg bg-white p-5 shadow-sm">
                <h3 className="mb-3 text-sm font-semibold text-brand-charcoal">
                  Email Preview
                </h3>
                <div className="rounded border border-gray-200 bg-gray-50">
                  <div className="border-b border-gray-200 px-4 py-2">
                    <p className="text-xs text-gray-500">Subject</p>
                    <p className="text-sm font-medium text-brand-charcoal">{preview.subject}</p>
                  </div>
                  <div
                    className="px-4 py-3 text-sm text-gray-700 leading-relaxed"
                    dangerouslySetInnerHTML={{ __html: preview.body_html }}
                  />
                </div>
              </div>
            </>
          )}

          {!preview && !error && !result && (
            <div className="flex items-center justify-center rounded-lg border-2 border-dashed border-gray-200 bg-gray-50 p-12">
              <p className="text-sm text-gray-400">
                Click "Preview" to see the recipient list and email preview.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Confirmation dialog */}
      {showConfirm && (
        <div className="mt-6 rounded-lg border border-yellow-300 bg-yellow-50 p-4">
          <p className="mb-3 text-sm font-medium text-yellow-800">
            Are you sure? This will send an email to {preview?.total_recipients ?? "all active"} user{preview?.total_recipients !== 1 ? "s" : ""}.
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
        <div className="mt-6 rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="mt-6 rounded-lg border border-green-300 bg-green-50 p-4 text-sm text-green-800">
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
