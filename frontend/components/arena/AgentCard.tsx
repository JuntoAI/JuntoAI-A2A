"use client";

import { SlidersHorizontal } from "lucide-react";

const AGENT_COLORS = [
  "#007BFF",
  "#00E676",
  "#FF6B6B",
  "#FFD93D",
  "#6C5CE7",
  "#A29BFE",
  "#FD79A8",
  "#00CEC9",
];

export interface AgentCardProps {
  name: string;
  role: string;
  goals: string[];
  modelId: string;
  index: number;
  hasCustomPrompt?: boolean;
  modelOverride?: string | null;
  hasStructuredMemory?: boolean;
  hasMilestoneSummaries?: boolean;
  onAdvancedConfig?: () => void;
}

export function AgentCard({
  name,
  role,
  goals,
  modelId,
  index,
  hasCustomPrompt = false,
  modelOverride = null,
  hasStructuredMemory = false,
  hasMilestoneSummaries = false,
  onAdvancedConfig = () => {},
}: AgentCardProps) {
  const color = AGENT_COLORS[index % AGENT_COLORS.length];
  const displayModel = modelOverride ?? modelId;

  return (
    <div
      className="rounded-xl border bg-white p-5 shadow-sm"
      style={{ borderLeftColor: color, borderLeftWidth: 4 }}
    >
      <h3 className="text-lg font-semibold text-gray-900">{name}</h3>
      <span
        className="mt-1 inline-block rounded-full px-3 py-0.5 text-xs font-medium text-white"
        style={{ backgroundColor: color }}
      >
        {role}
      </span>
      <ul className="mt-3 space-y-1">
        {goals.map((goal, i) => (
          <li key={i} className="text-sm text-gray-600">
            • {goal}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-gray-400">
        Model: {displayModel}
        {modelOverride && (
          <span className="ml-1 text-blue-500">(override)</span>
        )}
      </p>
      {hasStructuredMemory && (
        <p className="mt-1 text-xs text-green-600">
          ✦ Structured Memory
        </p>
      )}
      {hasMilestoneSummaries && (
        <p className="mt-1 text-xs text-blue-500">
          ✦ Milestone Summaries
        </p>
      )}
      <button
        type="button"
        onClick={onAdvancedConfig}
        className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-800"
      >
        <SlidersHorizontal className="h-3.5 w-3.5" />
        Advanced Config
        {hasCustomPrompt && (
          <span
            data-testid="custom-prompt-indicator"
            className="ml-1 inline-block h-2 w-2 rounded-full bg-green-500"
            aria-label="Custom prompt configured"
          />
        )}
      </button>
    </div>
  );
}
