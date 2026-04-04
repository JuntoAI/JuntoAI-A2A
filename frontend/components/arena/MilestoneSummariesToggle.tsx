"use client";

export interface MilestoneSummariesToggleProps {
  enabled: boolean;
  structuredMemoryEnabled: boolean;
  onChange: (enabled: boolean) => void;
}

export function MilestoneSummariesToggle({
  enabled,
  structuredMemoryEnabled,
  onChange,
}: MilestoneSummariesToggleProps) {
  const isDisabled = !structuredMemoryEnabled;

  return (
    <div
      className={`rounded-lg border px-4 py-3 transition-colors ${
        isDisabled
          ? "border-gray-200 bg-gray-50 opacity-60"
          : "border-gray-200 bg-white shadow-sm"
      }`}
    >
      <label
        htmlFor="milestone-summaries-toggle"
        className={`flex items-start gap-3 text-sm ${
          isDisabled ? "cursor-not-allowed text-gray-400" : "cursor-pointer text-gray-700"
        }`}
      >
        <input
          id="milestone-summaries-toggle"
          type="checkbox"
          checked={enabled}
          disabled={isDisabled}
          onChange={(e) => onChange(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-gray-300 text-brand-blue focus:ring-brand-blue disabled:opacity-50"
        />
        <div>
          <span className="font-medium">Milestone Summaries</span>
          <p className="mt-0.5 text-xs text-gray-500">
            Generate periodic strategic summaries to compress negotiation history
            and cap token usage for long negotiations
          </p>
          {isDisabled && (
            <p className="mt-1 text-xs text-amber-600" data-testid="dependency-hint">
              Requires Structured Agent Memory to be enabled on at least one agent
            </p>
          )}
        </div>
      </label>
    </div>
  );
}
