"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  fetchScenarios,
  fetchScenarioDetail,
  fetchAvailableModels,
  startNegotiation,
  TokenLimitError,
  type ArenaScenario,
  type ScenarioSummary,
  type ModelInfo,
} from "@/lib/api";
import { useSession } from "@/context/SessionContext";
import { ScenarioSelector } from "@/components/arena/ScenarioSelector";
import { AgentCard } from "@/components/arena/AgentCard";
import { InformationToggle } from "@/components/arena/InformationToggle";
import { InitializeButton } from "@/components/arena/InitializeButton";
import { AdvancedConfigModal, type MemoryStrategy } from "@/components/arena/AdvancedConfigModal";
import { Spinner } from "@/components/ui/Spinner";

function ArenaPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { email, tokenBalance, updateTokenBalance } = useSession();

  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [scenarioDetail, setScenarioDetail] = useState<ArenaScenario | null>(null);
  const [activeToggles, setActiveToggles] = useState<string[]>([]);
  const [isLoadingScenarios, setIsLoadingScenarios] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Advanced config state
  const [customPrompts, setCustomPrompts] = useState<Record<string, string>>({});
  const [modelOverrides, setModelOverrides] = useState<Record<string, string>>({});
  const [memoryStrategies, setMemoryStrategies] = useState<Record<string, MemoryStrategy>>({});
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [milestoneSummariesEnabled, setMilestoneSummariesEnabled] = useState(false);
  const [advancedConfigAgent, setAdvancedConfigAgent] = useState<{
    name: string;
    role: string;
    defaultModelId: string;
  } | null>(null);

  // Fetch scenarios on mount
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoadingScenarios(true);
      try {
        const list = await fetchScenarios(email ?? undefined);
        if (!cancelled) {
          setScenarios(list);
          const preselect = searchParams.get("scenario");
          if (preselect && list.some((s) => s.id === preselect)) {
            handleScenarioSelect(preselect);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load scenarios. Please try again.");
        }
      } finally {
        if (!cancelled) setIsLoadingScenarios(false);
      }
    }
    load();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch available models on mount
  useEffect(() => {
    let cancelled = false;
    async function loadModels() {
      try {
        const models = await fetchAvailableModels();
        if (!cancelled) setAvailableModels(models);
      } catch {
        if (!cancelled) setAvailableModels([]);
      }
    }
    loadModels();
    return () => { cancelled = true; };
  }, []);

  // Reset on scenario change
  useEffect(() => {
    setCustomPrompts({});
    setModelOverrides({});
    setMemoryStrategies({});
    setMilestoneSummariesEnabled(false);
  }, [selectedScenarioId]);

  const handleScenarioSelect = useCallback(async (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setScenarioDetail(null);
    setActiveToggles([]);
    setMemoryStrategies({});
    setMilestoneSummariesEnabled(false);
    setError(null);
    setIsLoadingDetail(true);
    try {
      const detail = await fetchScenarioDetail(scenarioId, email ?? undefined);
      setScenarioDetail(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load scenario details.");
    } finally {
      setIsLoadingDetail(false);
    }
  }, [email]);

  const handleToggleChange = useCallback(
    (id: string, checked: boolean) => {
      setActiveToggles((prev) => checked ? [...prev, id] : prev.filter((t) => t !== id));
    },
    [],
  );

  // Derive structured memory roles and no-memory roles from memory strategies.
  // Default strategy is "structured", so agents without an explicit strategy
  // get structured memory enabled.
  const allAgentRoles = scenarioDetail?.agents.map((a) => a.role) ?? [];

  const structuredMemoryRoles = allAgentRoles.filter((role) => {
    const strategy = memoryStrategies[role] ?? "structured";
    return strategy === "structured" || strategy === "structured_milestones";
  });

  const noMemoryRoles = allAgentRoles.filter((role) => {
    return memoryStrategies[role] === "none";
  });

  const handleInitialize = useCallback(async () => {
    if (!email || !selectedScenarioId) return;
    setIsStarting(true);
    setError(null);
    try {
      const filteredPrompts: Record<string, string> = {};
      for (const [role, prompt] of Object.entries(customPrompts)) {
        if (prompt.trim()) filteredPrompts[role] = prompt;
      }
      const filteredOverrides: Record<string, string> = {};
      for (const [role, modelId] of Object.entries(modelOverrides)) {
        if (modelId) filteredOverrides[role] = modelId;
      }

      const result = await startNegotiation(
        email,
        selectedScenarioId,
        activeToggles,
        Object.keys(filteredPrompts).length > 0 ? filteredPrompts : undefined,
        Object.keys(filteredOverrides).length > 0 ? filteredOverrides : undefined,
        structuredMemoryRoles.length > 0 ? structuredMemoryRoles : undefined,
        milestoneSummariesEnabled,
        noMemoryRoles.length > 0 ? noMemoryRoles : undefined,
      );
      updateTokenBalance(result.tokens_remaining);
      router.push(
        `/arena/session/${result.session_id}?max_turns=${result.max_turns}&scenario=${selectedScenarioId}`,
      );
    } catch (err) {
      if (err instanceof TokenLimitError) {
        updateTokenBalance(0);
        setError("Token limit reached. Resets at midnight UTC.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to start negotiation.");
      }
    } finally {
      setIsStarting(false);
    }
  }, [
    email, selectedScenarioId, activeToggles, customPrompts, modelOverrides,
    structuredMemoryRoles, milestoneSummariesEnabled, noMemoryRoles, updateTokenBalance, router,
  ]);

  const insufficientTokens = tokenBalance <= 0;

  const handleMilestoneSummariesChange = useCallback(
    (enabled: boolean) => {
      setMilestoneSummariesEnabled(enabled);
    },
    [],
  );

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900">Arena Control Panel</h1>

      {isLoadingScenarios ? (
        <Spinner message="Loading scenarios…" />
      ) : (
        <ScenarioSelector
          scenarios={scenarios}
          selectedId={selectedScenarioId}
          onSelect={handleScenarioSelect}
          isLoading={isLoadingScenarios}
          error={error && !selectedScenarioId && !isStarting ? error : null}
        />
      )}

      {isLoadingDetail && <Spinner message="Loading scenario details…" size="sm" />}

      {scenarioDetail && (
        <>
          <p className="text-sm leading-relaxed text-gray-600">{scenarioDetail.description}</p>

          <section>
            <h2 className="mb-4 text-lg font-semibold text-gray-800">Agents</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {scenarioDetail.agents.map((agent, i) => (
                <AgentCard
                  key={agent.name}
                  name={agent.name}
                  role={agent.role}
                  goals={agent.goals}
                  modelId={agent.model_id}
                  index={i}
                  hasCustomPrompt={!!customPrompts[agent.role]?.trim()}
                  modelOverride={modelOverrides[agent.role] ?? null}
                  memoryStrategy={memoryStrategies[agent.role] ?? "structured"}
                  onAdvancedConfig={() =>
                    setAdvancedConfigAgent({
                      name: agent.name,
                      role: agent.role,
                      defaultModelId: agent.model_id,
                    })
                  }
                />
              ))}
            </div>
          </section>

          {scenarioDetail.toggles.length > 0 && (
            <section>
              <h2 className="mb-1 text-lg font-semibold text-gray-800">Hidden Variables</h2>
              <p className="mb-3 text-sm text-gray-500">
                Give agents secret context that changes how they negotiate. These are optional.
                Try running with and without to see how outcomes differ.
              </p>
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

      {error && (selectedScenarioId || isStarting) && (
        <p className="text-sm text-red-600" role="alert">{error}</p>
      )}

      <InitializeButton
        onClick={handleInitialize}
        disabled={!selectedScenarioId || isLoadingDetail}
        isLoading={isStarting}
        insufficientTokens={insufficientTokens}
      />

      {advancedConfigAgent && (
        <AdvancedConfigModal
          isOpen={true}
          agentName={advancedConfigAgent.name}
          agentRole={advancedConfigAgent.role}
          defaultModelId={advancedConfigAgent.defaultModelId}
          availableModels={availableModels}
          initialCustomPrompt={customPrompts[advancedConfigAgent.role] ?? ""}
          initialModelOverride={modelOverrides[advancedConfigAgent.role] ?? null}
          initialMemoryStrategy={memoryStrategies[advancedConfigAgent.role] ?? "structured"}
          milestoneSummariesEnabled={milestoneSummariesEnabled}
          onMilestoneSummariesChange={handleMilestoneSummariesChange}
          onSave={(customPrompt, modelOverride, memoryStrategy) => {
            const role = advancedConfigAgent.role;
            setCustomPrompts((prev) => {
              const next = { ...prev };
              if (customPrompt.trim()) { next[role] = customPrompt; } else { delete next[role]; }
              return next;
            });
            setModelOverrides((prev) => {
              const next = { ...prev };
              if (modelOverride) { next[role] = modelOverride; } else { delete next[role]; }
              return next;
            });
            setMemoryStrategies((prev) => ({ ...prev, [role]: memoryStrategy }));
            setAdvancedConfigAgent(null);
          }}
          onCancel={() => setAdvancedConfigAgent(null)}
        />
      )}
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
