"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Coins } from "lucide-react";
import Link from "next/link";
import type { ArenaScenario } from "@/lib/api";
import type {
  HealthCheckFinding,
  HealthCheckFullReport,
} from "@/lib/builder/types";
import { saveScenario, type BuilderSaveCallbacks } from "@/lib/builder/api";
import { BuilderChat } from "@/components/builder/BuilderChat";
import { JsonPreview } from "@/components/builder/JsonPreview";
import { ProgressIndicator } from "@/components/builder/ProgressIndicator";
import { HealthCheckReport } from "@/components/builder/HealthCheckReport";
import { useSession } from "@/context/SessionContext";

function generateSessionId(): string {
  return `builder-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function BuilderPage() {
  const router = useRouter();
  const { email, tokenBalance } = useSession();

  const [sessionId] = useState(generateSessionId);
  const [scenarioJson, setScenarioJson] = useState<Partial<ArenaScenario>>({});
  const [highlightedSection, setHighlightedSection] = useState<string | null>(null);
  const [showConfirmLeave, setShowConfirmLeave] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isValid, setIsValid] = useState(false);
  const [healthFindings, setHealthFindings] = useState<HealthCheckFinding[]>([]);
  const [healthReport, setHealthReport] = useState<HealthCheckFullReport | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

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

  const handleJsonDelta = useCallback(
    (section: string, data: Record<string, unknown>) => {
      const unwrapped =
        "value" in data && Object.keys(data).length === 1
          ? data.value
          : data;
      setScenarioJson((prev) => ({ ...prev, [section]: unwrapped }));
      setHighlightedSection(section);
      setTimeout(() => setHighlightedSection(null), 2000);
    },
    [],
  );

  const handleHealthReport = useCallback((report: HealthCheckFullReport) => {
    setHealthReport(report);
    setHealthFindings(report.findings);
    setIsAnalyzing(false);
  }, []);

  const handleBack = useCallback(() => {
    if (hasProgress) {
      setShowConfirmLeave(true);
    } else {
      router.push("/arena");
    }
  }, [hasProgress, router]);

  const confirmLeave = useCallback(() => {
    setShowConfirmLeave(false);
    router.push("/arena");
  }, [router]);

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
        email ?? "",
        scenarioJson as Record<string, unknown>,
        callbacks,
      );
      setIsAnalyzing(false);
      router.push(`/arena?scenario=${result.scenario_id}`);
    } catch (err) {
      setIsAnalyzing(false);
      setSaveError(err instanceof Error ? err.message : "Failed to save scenario");
    } finally {
      setIsSaving(false);
    }
  }, [email, scenarioJson, router]);

  return (
    <div
      className="flex flex-col bg-[#1C1C1E] min-h-[calc(100vh-49px)]"
      data-testid="builder-page"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-6 py-3">
        <div className="flex items-center gap-4 flex-1">
          <button
            onClick={handleBack}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-400 hover:bg-gray-700 hover:text-white transition-colors"
            data-testid="back-button"
          >
            <ArrowLeft size={16} />
            Back to Arena
          </button>
          <h2 className="text-lg font-semibold text-white">
            AI Scenario Builder
          </h2>
          <div className="flex items-center gap-1.5 text-xs text-gray-400">
            <Coins size={14} />
            <span data-testid="token-balance">{tokenBalance} tokens</span>
          </div>
        </div>

        <div className="flex-1 max-w-md mx-4">
          <ProgressIndicator
            scenarioJson={scenarioJson}
            isValid={isValid}
            onSave={handleSave}
          />
        </div>
      </div>

      {/* Main content — split screen */}
      <div className="flex flex-1 min-h-0 flex-col lg:flex-row">
        <div className="lg:w-1/2 min-h-0 min-w-0 lg:border-r lg:border-gray-700 flex flex-col">
          <BuilderChat
            sessionId={sessionId}
            email={email ?? ""}
            onJsonDelta={handleJsonDelta}
            onHealthReport={handleHealthReport}
          />
        </div>

        <div className="lg:w-1/2 min-h-0 min-w-0 flex flex-col">
          <div className="flex-1 min-h-0 overflow-auto">
            <JsonPreview
              scenarioJson={scenarioJson}
              highlightedSection={highlightedSection}
            />
          </div>

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

      {/* Leave confirmation dialog */}
      {showConfirmLeave && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          data-testid="confirm-close-dialog"
        >
          <div className="rounded-xl bg-[#1C1C1E] border border-gray-700 p-6 max-w-sm mx-4 shadow-2xl">
            <h3 className="text-lg font-semibold text-white mb-2">
              Unsaved Progress
            </h3>
            <p className="text-sm text-gray-400 mb-6">
              You have unsaved progress. Are you sure you want to leave the
              builder?
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirmLeave(false)}
                className="flex-1 rounded-lg bg-[#007BFF] px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors"
                data-testid="continue-building-button"
              >
                Continue Building
              </button>
              <button
                onClick={confirmLeave}
                className="flex-1 rounded-lg border border-gray-600 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-800 transition-colors"
                data-testid="discard-close-button"
              >
                Discard &amp; Leave
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
