"use client";

import { useMemo } from "react";
import { Trash2 } from "lucide-react";
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
  /** Callback invoked when the user wants to delete a custom scenario. */
  onDeleteCustom?: (scenarioId: string, scenarioName: string) => void;
  /** Whether a delete operation is in progress. */
  isDeleting?: boolean;
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
  onDeleteCustom,
  isDeleting = false,
}: ScenarioSelectorProps) {
  const categoryGroups = useMemo(() => groupByCategory(scenarios), [scenarios]);

  const isCustomSelected = customScenarios.some((s) => s.id === selectedId);
  const selectedCustomName =
    customScenarios.find((s) => s.id === selectedId)?.name ?? "this scenario";

  return (
    <div className="w-full">
      <div className="flex gap-2">
        <select
          className="min-w-0 flex-1 rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 shadow-sm transition-colors focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20 disabled:cursor-not-allowed disabled:opacity-50"
          value={selectedId ?? ""}
          disabled={isLoading || isDeleting}
          onChange={(e) => {
            const value = e.target.value;
            if (value === BUILD_YOUR_OWN_VALUE) {
              onBuildOwn?.();
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

        {isCustomSelected && onDeleteCustom && (
          <button
            type="button"
            disabled={isDeleting}
            onClick={() => onDeleteCustom(selectedId!, selectedCustomName)}
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-2 text-sm text-red-600 shadow-sm transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={`Delete custom scenario: ${selectedCustomName}`}
          >
            <Trash2 size={16} />
            <span className="hidden sm:inline">Delete</span>
          </button>
        )}
      </div>
      {error && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
