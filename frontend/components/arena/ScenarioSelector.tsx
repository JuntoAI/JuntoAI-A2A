"use client";

import { useMemo } from "react";
import type { ScenarioSummary } from "@/lib/api";

const DIFFICULTY_LABEL: Record<string, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
  fun: "Fun",
};

export interface ScenarioSelectorProps {
  scenarios: ScenarioSummary[];
  selectedId: string | null;
  onSelect: (scenarioId: string) => void;
  isLoading: boolean;
  error: string | null;
  /** Custom user-created scenarios shown in a "My Scenarios" group. */
  customScenarios?: ScenarioSummary[];
  /** Callback invoked when the user selects "Build Your Own Scenario". */
  onBuildOwn?: () => void;
}

const BUILD_YOUR_OWN_VALUE = "__build_your_own__";

/**
 * Group scenarios by category and return sorted category entries.
 * Categories are sorted alphabetically, with "General" always last.
 */
function groupByCategory(
  scenarios: ScenarioSummary[],
): [string, ScenarioSummary[]][] {
  const groups = new Map<string, ScenarioSummary[]>();
  for (const s of scenarios) {
    const cat = s.category || "General";
    const list = groups.get(cat);
    if (list) {
      list.push(s);
    } else {
      groups.set(cat, [s]);
    }
  }

  return Array.from(groups.entries()).sort(([a], [b]) => {
    if (a === "General") return 1;
    if (b === "General") return -1;
    return a.localeCompare(b);
  });
}

export function ScenarioSelector({
  scenarios,
  selectedId,
  onSelect,
  isLoading,
  error,
  customScenarios = [],
  onBuildOwn,
}: ScenarioSelectorProps) {
  const categoryGroups = useMemo(() => groupByCategory(scenarios), [scenarios]);

  return (
    <div className="w-full">
      <select
        className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 shadow-sm transition-colors focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20 disabled:cursor-not-allowed disabled:opacity-50"
        value={selectedId ?? ""}
        disabled={isLoading}
        onChange={(e) => {
          const value = e.target.value;
          if (value === BUILD_YOUR_OWN_VALUE) {
            onBuildOwn?.();
            // Reset select back so it doesn't stay on the "Build Your Own" option
            e.target.value = selectedId ?? "";
            return;
          }
          if (value) {
            onSelect(value);
          }
        }}
      >
        <option value="">Select Simulation Environment</option>

        {/* Pre-built scenarios grouped by category */}
        {categoryGroups.map(([category, items]) => (
          <optgroup key={category} label={category}>
            {items.map((s) => (
              <option key={s.id} value={s.id}>
                [{DIFFICULTY_LABEL[s.difficulty] ?? s.difficulty}] {s.name}
              </option>
            ))}
          </optgroup>
        ))}

        {/* My Scenarios group — only shown when custom scenarios exist */}
        {customScenarios.length > 0 && (
          <optgroup label="My Scenarios">
            {customScenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </optgroup>
        )}

        {/* Divider + Build Your Own */}
        <option disabled className="border-t border-gray-200">
          ────────────────
        </option>
        <option value={BUILD_YOUR_OWN_VALUE}>🛠 Build Your Own Scenario</option>
      </select>
      {error && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
