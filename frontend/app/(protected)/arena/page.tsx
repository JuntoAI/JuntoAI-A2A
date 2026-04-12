"use client";

import { useEffect, useState, useCallback, useRef, Suspense } from "react";
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
import { NegotiationHistory } from "@/components/arena/NegotiationHistory";
import { AdvancedConfigModal, type MemoryStrategy } from "@/components/arena/AdvancedConfigModal";
import { BuilderModal } from "@/components/builder/BuilderModal";
import { listCustomScenarios, deleteCustomScenario, updateCustomScenario, type CustomScenarioSummary } from "@/lib/builder/api";
import { ScenarioEditorModal, type SaveCallbacks } from "@/components/arena/ScenarioEditorModal";
import { Spinner } from "@/components/ui/Spinner";

function ArenaPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { email, tokenBalance, updateTokenBalance, dailyLimit, updateTier } = useSession();

  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [scenarioDetail, setScenarioDetail] = useState<ArenaScenario | null>(null);
  const [activeToggles, setActiveToggles] = useState<string[]>([]);
  const [isLoadingScenarios, setIsLoadingScenarios] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Builder state
  const [customScenarios, setCustomScenarios] = useState<ScenarioSummary[]>([]);
  const [showBuilder, setShowBuilder] = useState(false);
  const [isDeletingScenario, setIsDeletingScenario] = useState(false);
  const customScenariosRaw = useRef<CustomScenarioSummary[]>([]);

  // Editor modal state
  const [editorScenarioId, setEditorScenarioId] = useState<string | null>(null);
  const [editorScenarioJson, setEditorScenarioJson] = useState<Record<string, unknown>>({});

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

  // Fetch custom scenarios
  const refreshCustomScenarios = useCallback(async () => {
    if (!email) return;
    try {
      const list = await listCustomScenarios(email);
      customScenariosRaw.current = list;
      setCustomScenarios(
        list.map((cs) => {
          const json = cs.scenario_json as Record<string, string>;
          return {
            id: cs.scenario_id,
            name: json.name ?? "Custom Scenario",
            description: json.description ?? "",
            difficulty: "intermediate" as const,
            category: (json.category as string) ?? "General",
          };
        }),
      );
    } catch {
      // Non-critical — custom scenarios just won't show
    }
  }, [email]);

  // Fetch token balance + custom scenarios on mount
  useEffect(() => {
    if (email) {
      import("@/lib/profile").then(({ getProfile }) => {
        getProfile(email).then((p) => {
          updateTier(p.tier, p.daily_limit, p.token_balance);
        }).catch(() => {});
      });
      refreshCustomScenarios();
    }
  }, [email, updateTier, refreshCustomScenarios]);

  // Delete a custom scenario
  const handleDeleteCustomScenario = useCallback(
    async (scenarioId: string, scenarioName: string) => {
      if (!email) return;
      const confirmed = confirm(
        `Delete "${scenarioName}"?\n\nThis cannot be undone.`,
      );
      if (!confirmed) return;

      setIsDeletingScenario(true);
      setError(null);
      try {
        await deleteCustomScenario(email, scenarioId);
        if (selectedScenarioId === scenarioId) {
          setSelectedScenarioId(null);
          setScenarioDetail(null);
          setActiveToggles([]);
        }
        await refreshCustomScenarios();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to delete scenario.",
        );
      } finally {
        setIsDeletingScenario(false);
      }
    },
    [email, selectedScenarioId, refreshCustomScenarios],
  );

  // Edit a custom scenario
  const handleEditCustomScenario = useCallback(
    (scenarioId: string, _scenarioName: string) => {
      const raw = customScenariosRaw.current.find((cs) => cs.scenario_id === scenarioId);
      if (!raw) return;
      setEditorScenarioId(scenarioId);
      setEditorScenarioJson(raw.scenario_json);
    },
    [],
  );

  const handleSaveEditedScenario = useCallback(
    async (updated: Record<string, unknown>, callbacks: SaveCallbacks) => {
      if (!email || !editorScenarioId) return;
      await updateCustomScenario(email, editorScenarioId, updated, {
        onHealthStart: callbacks.onHealthStart,
        onHealthFinding: callbacks.onHealthFinding,
        onHealthComplete: callbacks.onHealthComplete,
        onError: callbacks.onError,
      });
      await refreshCustomScenarios();
      // Refresh detail if the edited scenario is currently selected
      if (selectedScenarioId === editorScenarioId) {
        setScenarioDetail({ id: editorScenarioId, ...updated } as ArenaScenario);
      }
      // Don't close modal here — let the user see health check results.
      // Modal shows a "Done" button after successful save.
    },
    [email, editorScenarioId, refreshCustomScenarios, selectedScenarioId],
  );

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

  // Track whether deep-link toggles/customPrompts have been applied (once per page load)
  const togglesAppliedRef = useRef(false);
  const customPromptsAppliedRef = useRef(false);

  // Reset on scenario change
  useEffect(() => {
    setCustomPrompts({});
    setModelOverrides({});
    setMemoryStrategies({});
    setMilestoneSummariesEnabled(false);
  }, [selectedScenarioId]);

  // Deep-link: parse `toggles` query param and activate valid toggles
  useEffect(() => {
    if (togglesAppliedRef.current) return;
    if (!scenarioDetail || !selectedScenarioId) return;

    const scenarioParam = searchParams.get("scenario");
    if (!scenarioParam) return; // Ignore toggles param when no scenario param

    const togglesParam = searchParams.get("toggles");
    if (!togglesParam) return;

    const requestedIds = togglesParam.split(",").filter(Boolean);
    const validIds = requestedIds.filter((id) =>
      scenarioDetail.toggles.some((t) => t.id === id),
    );

    if (validIds.length > 0) {
      setActiveToggles(validIds);
    }

    togglesAppliedRef.current = true;
  }, [scenarioDetail, selectedScenarioId, searchParams]);

  // Deep-link: parse `customPrompts` query param and prefill valid custom prompts
  useEffect(() => {
    if (customPromptsAppliedRef.current) return;
    if (!scenarioDetail || !selectedScenarioId) return;

    const scenarioParam = searchParams.get("scenario");
    if (!scenarioParam) return; // Ignore customPrompts param when no scenario param

    const customPromptsParam = searchParams.get("customPrompts");
    if (!customPromptsParam) return;

    try {
      const decoded: Record<string, string> = JSON.parse(atob(decodeURIComponent(customPromptsParam)));
      const validRoles = new Set(scenarioDetail.agents.map((a) => a.role));
      const filtered: Record<string, string> = {};
      for (const [role, prompt] of Object.entries(decoded)) {
        if (validRoles.has(role) && typeof prompt === "string" && prompt.trim()) {
          filtered[role] = prompt;
        }
      }
      if (Object.keys(filtered).length > 0) {
        setCustomPrompts(filtered);
      }
    } catch {
      console.warn("Invalid customPrompts query parameter — ignoring");
    }

    customPromptsAppliedRef.current = true;
  }, [scenarioDetail, selectedScenarioId, searchParams]);

  const handleScenarioSelect = useCallback(async (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setScenarioDetail(null);
    setActiveToggles([]);
    setMemoryStrategies({});
    setMilestoneSummariesEnabled(false);
    setError(null);
    setIsLoadingDetail(true);
    try {
      // Custom scenarios aren't in the main /scenarios registry — use stored JSON
      const customRaw = customScenariosRaw.current.find((cs) => cs.scenario_id === scenarioId);
      if (customRaw) {
        const json = customRaw.scenario_json as Record<string, unknown>;
        setScenarioDetail({ id: scenarioId, ...json } as ArenaScenario);
      } else {
        const detail = await fetchScenarioDetail(scenarioId, email ?? undefined);
        setScenarioDetail(detail);
      }
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
      const sessionUrl = `/arena/session/${result.session_id}?max_turns=${result.max_turns}&scenario=${selectedScenarioId}${activeToggles.length > 0 ? `&toggles=${activeToggles.join(",")}` : ""}`;
      router.push(sessionUrl);
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
          customScenarios={customScenarios}
          onBuildOwn={() => setShowBuilder(true)}
          onDeleteCustom={handleDeleteCustomScenario}
          isDeleting={isDeletingScenario}
          onEditCustom={handleEditCustomScenario}
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
                  personaPrompt={agent.persona_prompt}
                  tone={agent.tone}
                  budget={agent.budget}
                  outputFields={agent.output_fields}
                  agentType={agent.type}
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

      {email && (
        <NegotiationHistory email={email} dailyLimit={dailyLimit} />
      )}

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
          examplePrompt={scenarioDetail?.agents.find((a) => a.role === advancedConfigAgent.role)?.example_prompt}
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

      {/* Builder Modal */}
      <BuilderModal
        isOpen={showBuilder}
        onClose={() => setShowBuilder(false)}
        onScenarioSaved={(scenarioId) => {
          setShowBuilder(false);
          refreshCustomScenarios();
          // Auto-select the newly saved custom scenario
          handleScenarioSelect(scenarioId);
        }}
        email={email ?? ""}
        tokenBalance={tokenBalance}
      />

      {/* Scenario Editor Modal */}
      <ScenarioEditorModal
        isOpen={editorScenarioId !== null}
        onClose={() => setEditorScenarioId(null)}
        scenarioId={editorScenarioId ?? ""}
        scenarioJson={editorScenarioJson}
        onSave={handleSaveEditedScenario}
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
