"use client";

import type { ScenarioSummary } from "@/lib/api";

export interface ScenarioSelectorProps {
  scenarios: ScenarioSummary[];
  selectedId: string | null;
  onSelect: (scenarioId: string) => void;
  isLoading: boolean;
  error: string | null;
}

export function ScenarioSelector({
  scenarios,
  selectedId,
  onSelect,
  isLoading,
  error,
}: ScenarioSelectorProps) {
  return (
    <div className="w-full">
      <select
        className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 shadow-sm transition-colors focus:border-[#007BFF] focus:outline-none focus:ring-2 focus:ring-[#007BFF]/20 disabled:cursor-not-allowed disabled:opacity-50"
        value={selectedId ?? ""}
        disabled={isLoading}
        onChange={(e) => {
          if (e.target.value) {
            onSelect(e.target.value);
          }
        }}
      >
        <option value="">Select Simulation Environment</option>
        {scenarios.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
      {error && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
