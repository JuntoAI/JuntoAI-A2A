"use client";

import { useState } from "react";
import type { UsageSummary, PersonaUsageStats } from "@/types/sse";

interface UsageSummaryCardProps {
  usageSummary: UsageSummary;
}

function formatRatio(input: number, output: number): string {
  if (output === 0) return "∞:1";
  return `${(input / output).toFixed(1)}:1`;
}

function formatDuration(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}

function getMostVerboseIndex(personas: PersonaUsageStats[]): number | null {
  if (personas.length < 2) return null;
  let maxIdx = 0;
  for (let i = 1; i < personas.length; i++) {
    if (personas[i].tokens_per_message > personas[maxIdx].tokens_per_message) {
      maxIdx = i;
    }
  }
  return maxIdx;
}

export default function UsageSummaryCard({ usageSummary }: UsageSummaryCardProps) {
  const [isOpen, setIsOpen] = useState(false);

  const sortedPersonas = [...usageSummary.per_persona].sort(
    (a, b) => b.total_tokens - a.total_tokens,
  );

  const mostVerboseIdx = getMostVerboseIndex(sortedPersonas);

  return (
    <div
      className="border-t border-gray-200 pt-4 mb-6"
      data-testid="usage-summary-section"
    >
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-2 text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3 hover:text-gray-800 transition-colors"
        data-testid="usage-summary-toggle"
      >
        <span className={`inline-block transition-transform ${isOpen ? "rotate-90" : ""}`}>
          ▶
        </span>
        LLM Usage
      </button>

      {isOpen && (
        <div className="space-y-4">
          {/* Session-wide totals */}
          <div className="text-sm text-gray-600 flex flex-wrap gap-4">
            <span>Total Tokens: <span className="font-medium text-gray-900">{usageSummary.total_tokens.toLocaleString("en-US")}</span></span>
            <span>LLM Calls: <span className="font-medium text-gray-900">{usageSummary.total_calls}</span></span>
            {usageSummary.total_errors > 0 && (
              <span>Errors: <span className="font-medium text-red-600">{usageSummary.total_errors}</span></span>
            )}
            <span>Avg Latency: <span className="font-medium text-gray-900">{usageSummary.avg_latency_ms}ms</span></span>
            <span>Duration: <span className="font-medium text-gray-900">{formatDuration(usageSummary.negotiation_duration_ms)}</span></span>
          </div>

          {/* Responsive table layout: stacked on mobile, side-by-side at lg */}
          <div className="lg:grid lg:grid-cols-2 lg:gap-4 space-y-4 lg:space-y-0">
            {/* Per-persona breakdown */}
            <div>
              <h4 className="text-xs text-gray-500 uppercase tracking-wide mb-2">Per Persona</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="text-xs text-gray-500 uppercase border-b border-gray-200">
                      <th className="py-1 pr-2">Role</th>
                      <th className="py-1 pr-2">Model</th>
                      <th className="py-1 pr-2 text-right">Tokens</th>
                      <th className="py-1 pr-2 text-right">Calls</th>
                      <th className="py-1 pr-2 text-right">Latency</th>
                      <th className="py-1 pr-2 text-right">Tok/Msg</th>
                      <th className="py-1 text-right">I:O</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedPersonas.map((p, i) => (
                      <tr key={p.agent_role} className="border-b border-gray-100">
                        <td className="py-1.5 pr-2 text-gray-700 font-medium">
                          {p.agent_role}
                          {mostVerboseIdx === i && (
                            <span
                              className="ml-1 inline-block px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded"
                              data-testid="most-verbose-badge"
                            >
                              Most Verbose
                            </span>
                          )}
                        </td>
                        <td className="py-1.5 pr-2 text-gray-500">{p.model_id}</td>
                        <td className="py-1.5 pr-2 text-right text-gray-700">{p.total_tokens.toLocaleString("en-US")}</td>
                        <td className="py-1.5 pr-2 text-right text-gray-700">{p.call_count}</td>
                        <td className="py-1.5 pr-2 text-right text-gray-700">{p.avg_latency_ms}ms</td>
                        <td className="py-1.5 pr-2 text-right text-gray-700">{p.tokens_per_message}</td>
                        <td className="py-1.5 text-right text-gray-700">{formatRatio(p.total_input_tokens, p.total_output_tokens)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Per-model breakdown */}
            <div>
              <h4 className="text-xs text-gray-500 uppercase tracking-wide mb-2">Per Model</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="text-xs text-gray-500 uppercase border-b border-gray-200">
                      <th className="py-1 pr-2">Model</th>
                      <th className="py-1 pr-2 text-right">Tokens</th>
                      <th className="py-1 pr-2 text-right">Calls</th>
                      <th className="py-1 pr-2 text-right">Latency</th>
                      <th className="py-1 text-right">Tok/Msg</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usageSummary.per_model.map((m) => (
                      <tr key={m.model_id} className="border-b border-gray-100">
                        <td className="py-1.5 pr-2 text-gray-700 font-medium">{m.model_id}</td>
                        <td className="py-1.5 pr-2 text-right text-gray-700">{m.total_tokens.toLocaleString("en-US")}</td>
                        <td className="py-1.5 pr-2 text-right text-gray-700">{m.call_count}</td>
                        <td className="py-1.5 pr-2 text-right text-gray-700">{m.avg_latency_ms}ms</td>
                        <td className="py-1.5 text-right text-gray-700">{m.tokens_per_message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
