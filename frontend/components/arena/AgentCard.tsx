"use client";

import { useState } from "react";
import { SlidersHorizontal, ChevronDown, ChevronUp } from "lucide-react";
import type { MemoryStrategy } from "./AdvancedConfigModal";

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
  memoryStrategy?: MemoryStrategy;
  onAdvancedConfig?: () => void;
  personaPrompt?: string;
  tone?: string;
  budget?: { min: number; max: number; target: number };
  outputFields?: string[];
  agentType?: "negotiator" | "regulator" | "observer";
}

export function AgentCard({
  name,
  role,
  goals,
  modelId,
  index,
  hasCustomPrompt = false,
  modelOverride = null,
  memoryStrategy = "structured",
  onAdvancedConfig = () => {},
  personaPrompt,
  tone,
  budget,
  outputFields,
  agentType,
}: AgentCardProps) {
  const color = AGENT_COLORS[index % AGENT_COLORS.length];
  const displayModel = modelOverride ?? modelId;
  const [expanded, setExpanded] = useState(false);

  const hasDetails = personaPrompt || tone || budget || (outputFields && outputFields.length > 0);

  return (
    <div
      className="rounded-xl border bg-white p-5 shadow-sm"
      style={{ borderLeftColor: color, borderLeftWidth: 4 }}
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{name}</h3>
          <div className="mt-1 flex items-center gap-2">
            <span
              className="inline-block rounded-full px-3 py-0.5 text-xs font-medium text-white"
              style={{ backgroundColor: color }}
            >
              {role}
            </span>
            {agentType && agentType !== "negotiator" && (
              <span className="inline-block rounded-full border border-gray-300 px-2 py-0.5 text-xs text-gray-500">
                {agentType}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Goals */}
      <ul className="mt-3 space-y-1">
        {goals.map((goal, i) => (
          <li key={i} className="text-sm text-gray-600">
            • {goal}
          </li>
        ))}
      </ul>

      {/* Budget range — always visible when present */}
      {budget && (
        <div className="mt-3 flex items-center gap-3 rounded-md bg-gray-50 px-3 py-2">
          <span className="text-xs font-medium text-gray-500">Budget range</span>
          <div className="flex items-center gap-1.5 text-xs text-gray-700">
            <span>{budget.min}</span>
            <span className="text-gray-300">→</span>
            <span className="font-semibold" style={{ color }}>{budget.target}</span>
            <span className="text-gray-300">→</span>
            <span>{budget.max}</span>
          </div>
        </div>
      )}

      {/* Expandable persona details */}
      {hasDetails && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="flex w-full items-center gap-1 text-xs font-medium text-gray-500 transition-colors hover:text-gray-700"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {expanded ? "Hide persona details" : "Show persona details"}
          </button>

          {expanded && (
            <div className="mt-2 space-y-3 border-t border-gray-100 pt-3">
              {/* Tone */}
              {tone && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Tone</p>
                  <p className="mt-0.5 text-sm italic text-gray-600">{tone}</p>
                </div>
              )}

              {/* Persona prompt */}
              {personaPrompt && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Persona</p>
                  <p className="mt-0.5 max-h-40 overflow-y-auto text-sm leading-relaxed text-gray-600">
                    {personaPrompt}
                  </p>
                </div>
              )}

              {/* Output fields */}
              {outputFields && outputFields.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Output fields</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {outputFields.map((field) => (
                      <span
                        key={field}
                        className="rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                      >
                        {field}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <p className="mt-3 text-xs text-gray-400">
        Model: {displayModel}
        {modelOverride && (
          <span className="ml-1 text-blue-500">(override)</span>
        )}
      </p>
      {memoryStrategy === "none" && (
        <p className="mt-1 text-xs text-red-500" data-testid="memory-indicator">
          ⚠ No Memory
        </p>
      )}
      {memoryStrategy === "full_transcript" && (
        <p className="mt-1 text-xs text-gray-500" data-testid="memory-indicator">
          ✦ Full Transcript
        </p>
      )}
      {memoryStrategy === "structured" && (
        <p className="mt-1 text-xs text-green-600" data-testid="memory-indicator">
          ✦ Structured Memory
        </p>
      )}
      {memoryStrategy === "structured_milestones" && (
        <p className="mt-1 text-xs text-blue-500" data-testid="memory-indicator">
          ✦ Structured Memory + Milestones
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
