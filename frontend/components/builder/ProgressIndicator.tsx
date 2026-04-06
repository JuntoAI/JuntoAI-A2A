"use client";

import { useMemo } from "react";
import { Save } from "lucide-react";
import type { ArenaScenario } from "@/lib/api";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ProgressIndicatorProps {
  scenarioJson: Partial<ArenaScenario>;
  isValid: boolean;
  onSave: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTIONS: (keyof ArenaScenario)[] = [
  "id",
  "name",
  "description",
  "agents",
  "toggles",
  "negotiation_params",
  "outcome_receipt",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isPopulated(value: unknown): boolean {
  if (value === undefined || value === null || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as object).length > 0;
  return true;
}

export function computeProgress(partial: Partial<ArenaScenario>): number {
  let count = 0;
  for (const key of SECTIONS) {
    if (isPopulated(partial[key])) count++;
  }
  return Math.round((count / 7) * 100);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ProgressIndicator({
  scenarioJson,
  isValid,
  onSave,
}: ProgressIndicatorProps) {
  const progress = useMemo(() => computeProgress(scenarioJson), [scenarioJson]);
  const isComplete = progress === 100 && isValid;

  return (
    <div className="flex items-center gap-4" data-testid="progress-indicator">
      {/* Progress bar */}
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-gray-300">
            Scenario Progress
          </span>
          <span className="text-xs font-medium text-gray-300">
            {progress}%
          </span>
        </div>
        <div className="h-2 w-full rounded-full bg-gray-700">
          <div
            className="h-2 rounded-full bg-[#007BFF] transition-all duration-300"
            style={{ width: `${progress}%` }}
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      </div>

      {/* Section indicators */}
      <div className="hidden sm:flex items-center gap-1">
        {SECTIONS.map((section) => (
          <div
            key={section}
            className={`h-2 w-2 rounded-full ${
              isPopulated(scenarioJson[section])
                ? "bg-green-500"
                : "bg-gray-600"
            }`}
            title={section}
          />
        ))}
      </div>

      {/* Save button */}
      <button
        onClick={onSave}
        disabled={!isComplete}
        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
          isComplete
            ? "bg-[#007BFF] text-white hover:bg-blue-600 cursor-pointer"
            : "bg-gray-700 text-gray-500 cursor-not-allowed"
        }`}
        data-testid="save-button"
      >
        <Save size={16} />
        Save Scenario
      </button>
    </div>
  );
}
