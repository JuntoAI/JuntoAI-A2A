"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  fetchScenarios,
  fetchScenarioDetail,
  startNegotiation,
  TokenLimitError,
  type ArenaScenario,
  type ScenarioSummary,
} from "@/lib/api";
import { useSession } from "@/context/SessionContext";
import { ScenarioSelector } from "@/components/arena/ScenarioSelector";
import { AgentCard } from "@/components/arena/AgentCard";
import { InformationToggle } from "@/components/arena/InformationToggle";
import { InitializeButton } from "@/components/arena/InitializeButton";

function ArenaPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { email, tokenBalance, updateTokenBalance } = useSession();

  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(
    null,
  );
  const [scenarioDetail, setScenarioDetail] = useState<ArenaScenario | null>(
    null,
  );
  const [activeToggles, setActiveToggles] = useState<string[]>([]);
  const [isLoadingScenarios, setIsLoadingScenarios] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch scenarios on mount
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoadingScenarios(true);
      try {
        const list = await fetchScenarios();
        if (!cancelled) {
          setScenarios(list);
          // Pre-select from URL query param
          const preselect = searchParams.get("scenario");
          if (preselect && list.some((s) => s.id === preselect)) {
            handleScenarioSelect(preselect);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load scenarios. Please try again.",
          );
        }
      } finally {
        if (!cancelled) setIsLoadingScenarios(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch scenario detail on selection
  const handleScenarioSelect = useCallback(async (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setScenarioDetail(null);
    setActiveToggles([]);
    setError(null);
    setIsLoadingDetail(true);
    try {
      const detail = await fetchScenarioDetail(scenarioId);
      setScenarioDetail(detail);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not load scenario details.",
      );
    } finally {
      setIsLoadingDetail(false);
    }
  }, []);

  // Toggle handler
  const handleToggleChange = useCallback(
    (id: string, checked: boolean) => {
      setActiveToggles((prev) =>
        checked ? [...prev, id] : prev.filter((t) => t !== id),
      );
    },
    [],
  );

  // Initialize negotiation
  const handleInitialize = useCallback(async () => {
    if (!email || !selectedScenarioId) return;
    setIsStarting(true);
    setError(null);
    try {
      const result = await startNegotiation(
        email,
        selectedScenarioId,
        activeToggles,
      );
      updateTokenBalance(result.tokens_remaining);
      router.push(
        `/arena/session/${result.session_id}?max_turns=${result.max_turns}`,
      );
    } catch (err) {
      if (err instanceof TokenLimitError) {
        updateTokenBalance(0);
        setError("Token limit reached. Resets at midnight UTC.");
      } else {
        setError(
          err instanceof Error ? err.message : "Failed to start negotiation.",
        );
      }
    } finally {
      setIsStarting(false);
    }
  }, [
    email,
    selectedScenarioId,
    activeToggles,
    updateTokenBalance,
    router,
  ]);

  const insufficientTokens = tokenBalance <= 0;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900">
        Arena Control Panel
      </h1>

      <ScenarioSelector
        scenarios={scenarios}
        selectedId={selectedScenarioId}
        onSelect={handleScenarioSelect}
        isLoading={isLoadingScenarios}
        error={
          error && !selectedScenarioId && !isStarting ? error : null
        }
      />

      {isLoadingDetail && (
        <p className="text-sm text-gray-500">Loading scenario details…</p>
      )}

      {scenarioDetail && (
        <>
          {/* Agent Cards */}
          <section>
            <h2 className="mb-4 text-lg font-semibold text-gray-800">
              Agents
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {scenarioDetail.agents.map((agent, i) => (
                <AgentCard
                  key={agent.name}
                  name={agent.name}
                  role={agent.role}
                  goals={agent.goals}
                  modelId={agent.model_id}
                  index={i}
                />
              ))}
            </div>
          </section>

          {/* Information Toggles */}
          {scenarioDetail.toggles.length > 0 && (
            <section>
              <h2 className="mb-4 text-lg font-semibold text-gray-800">
                Information Toggles
              </h2>
              <div className="flex flex-wrap gap-3">
                {scenarioDetail.toggles.map((toggle) => (
                  <InformationToggle
                    key={toggle.id}
                    id={toggle.id}
                    label={toggle.label}
                    checked={activeToggles.includes(toggle.id)}
                    onChange={handleToggleChange}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* Error display for start/detail errors */}
      {error && (selectedScenarioId || isStarting) && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <InitializeButton
        onClick={handleInitialize}
        disabled={!selectedScenarioId || isLoadingDetail}
        isLoading={isStarting}
        insufficientTokens={insufficientTokens}
      />
    </div>
  );
}

export default function ArenaPage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-500">Loading…</div>}>
      <ArenaPageContent />
    </Suspense>
  );
}
