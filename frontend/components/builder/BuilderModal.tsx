"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { X, Coins } from "lucide-react";
import type { ArenaScenario } from "@/lib/api";
import type {
  HealthCheckFinding,
  HealthCheckFullReport,
} from "@/lib/builder/types";
import { saveScenario, type BuilderSaveCallbacks } from "@/lib/builder/api";
import { BuilderChat } from "./BuilderChat";
import { JsonPreview } from "./JsonPreview";
import { ProgressIndicator } from "./ProgressIndicator";
import { HealthCheckReport } from "./HealthCheckReport";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface BuilderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onScenarioSaved: (scenarioId: string) => void;
  email: string;
  tokenBalance: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function generateSessionId(): string {
  return `builder-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BuilderModal({
  isOpen,
  onClose,
  onScenarioSaved,
  email,
  tokenBalance,
}: BuilderModalProps) {
  const [sessionId, setSessionId] = useState("");
  const [scenarioJson, setScenarioJson] = useState<Partial<ArenaScenario>>({});
  const [highlightedSection, setHighlightedSection] = useState<string | null>(null);
  const [showConfirmClose, setShowConfirmClose] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isValid, setIsValid] = useState(false);
  const [healthFindings, setHealthFindings] = useState<HealthCheckFinding[]>([]);
  const [healthReport, setHealthReport] = useState<HealthCheckFullReport | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Generate session ID on open
  useEffect(() => {
    if (isOpen) {
      setSessionId(generateSessionId());
      setScenarioJson({});
      setHighlightedSection(null);
      setShowConfirmClose(false);
      setHealthFindings([]);
      setHealthReport(null);
      setIsAnalyzing(false);
      setSaveError(null);
    }
  }, [isOpen]);

  // Check validity whenever scenario changes
  useEffect(() => {
    const s = scenarioJson;
    const hasAllSections =
      !!s.id && !!s.name && !!s.description &&
      Array.isArray(s.agents) && s.agents.length >= 2 &&
      Array.isArray(s.toggles) &&
      !!s.negotiation_params && !!s.outcome_receipt;
    setIsValid(hasAllSections);
  }, [scenarioJson]);

  const hasProgress = useMemo(
    () => Object.keys(scenarioJson).length > 0,
    [scenarioJson],
  );

  // Handle JSON delta from chat
  const handleJsonDelta = useCallback(
    (section: string, data: Record<string, unknown>) => {
      // The backend wraps non-dict values (arrays, strings) in {"value": ...}.
      // Unwrap so the scenario JSON stays in the correct ArenaScenario shape.
      const unwrapped =
        "value" in data && Object.keys(data).length === 1
          ? data.value
          : data;
      setScenarioJson((prev) => ({ ...prev, [section]: unwrapped }));
      setHighlightedSection(section);
      // Clear highlight after 2 seconds
      setTimeout(() => setHighlightedSection(null), 2000);
    },
    [],
  );

  // Handle health report from chat
  const handleHealthReport = useCallback((report: HealthCheckFullReport) => {
    setHealthReport(report);
    setHealthFindings(report.findings);
    setIsAnalyzing(false);
  }, []);

  // Handle close with confirmation
  const handleClose = useCallback(() => {
    if (hasProgress) {
      setShowConfirmClose(true);
    } else {
      onClose();
    }
  }, [hasProgress, onClose]);

  const confirmClose = useCallback(() => {
    setShowConfirmClose(false);
    onClose();
  }, [onClose]);

  // Handle save
  const handleSave = useCallback(async () => {
    setIsSaving(true);
    setIsAnalyzing(true);
    setSaveError(null);
    setHealthFindings([]);
    setHealthReport(null);

    const callbacks: BuilderSaveCallbacks = {
      onHealthFinding: (finding) => {
        setHealthFindings((prev) => [...prev, finding]);
      },
      onHealthComplete: (report) => {
        setHealthReport(report);
        setHealthFindings(report.findings);
        setIsAnalyzing(false);
      },
      onError: (message) => {
        setSaveError(message);
      },
    };

    try {
      const result = await saveScenario(
        email,
        scenarioJson as Record<string, unknown>,
        callbacks,
      );
      setIsAnalyzing(false);
      onScenarioSaved(result.scenario_id);
    } catch (err) {
      setIsAnalyzing(false);
      setSaveError(err instanceof Error ? err.message : "Failed to save scenario");
    } finally {
      setIsSaving(false);
    }
  }, [email, scenarioJson, onScenarioSaved]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-x-0 bottom-0 top-[49px] z-40 flex flex-col bg-[#1C1C1E]/95 backdrop-blur-sm"
      data-testid="builder-modal"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-6 py-3">
        <div className="flex items-center gap-4 flex-1">
          <h2 className="text-lg font-semibold text-white">
            AI Scenario Builder
          </h2>
          <div className="flex items-center gap-1.5 text-xs text-gray-400">
            <Coins size={14} />
            <span data-testid="token-balance">{tokenBalance} tokens</span>
          </div>
        </div>

        {/* Progress indicator */}
        <div className="flex-1 max-w-md mx-4">
          <ProgressIndicator
            scenarioJson={scenarioJson}
            isValid={isValid}
            onSave={handleSave}
          />
        </div>

        <button
          onClick={handleClose}
          className="rounded-lg p-2 text-gray-400 hover:bg-gray-700 hover:text-white transition-colors"
          aria-label="Close builder"
          data-testid="close-button"
        >
          <X size={20} />
        </button>
      </div>

      {/* Main content — split screen */}
      <div className="flex flex-1 min-h-0 flex-col lg:flex-row">
        {/* Left: Chat */}
        <div className="lg:w-1/2 min-h-0 min-w-0 lg:border-r lg:border-gray-700 flex flex-col">
          <BuilderChat
            sessionId={sessionId}
            email={email}
            onJsonDelta={handleJsonDelta}
            onHealthReport={handleHealthReport}
          />
        </div>

        {/* Right: JSON Preview + Health Report */}
        <div className="lg:w-1/2 min-h-0 min-w-0 flex flex-col">
          <div className="flex-1 min-h-0 overflow-auto">
            <JsonPreview
              scenarioJson={scenarioJson}
              highlightedSection={highlightedSection}
            />
          </div>

          {/* Health check report (shown after save attempt) */}
          {(isAnalyzing || healthReport || healthFindings.length > 0) && (
            <div className="border-t border-gray-700 p-4 max-h-[40%] overflow-auto">
              <HealthCheckReport
                findings={healthFindings}
                report={healthReport}
                isAnalyzing={isAnalyzing}
                onRetry={handleSave}
              />
            </div>
          )}
        </div>
      </div>

      {/* Save error */}
      {saveError && (
        <div className="border-t border-red-500/30 bg-red-500/10 px-6 py-2">
          <p className="text-sm text-red-400">{saveError}</p>
        </div>
      )}

      {/* Close confirmation dialog */}
      {showConfirmClose && (
        <div
          className="fixed inset-x-0 bottom-0 top-[49px] z-[45] flex items-center justify-center bg-black/60"
          data-testid="confirm-close-dialog"
        >
          <div className="rounded-xl bg-[#1C1C1E] border border-gray-700 p-6 max-w-sm mx-4 shadow-2xl">
            <h3 className="text-lg font-semibold text-white mb-2">
              Unsaved Progress
            </h3>
            <p className="text-sm text-gray-400 mb-6">
              You have unsaved progress. Are you sure you want to close the
              builder?
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirmClose(false)}
                className="flex-1 rounded-lg bg-[#007BFF] px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors"
                data-testid="continue-building-button"
              >
                Continue Building
              </button>
              <button
                onClick={confirmClose}
                className="flex-1 rounded-lg border border-gray-600 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-800 transition-colors"
                data-testid="discard-close-button"
              >
                Discard &amp; Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
