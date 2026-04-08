import type { ToggleDefinition, AgentDefinition } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WhatIfPrompt {
  text: string;
  toggleIds: string[];
  targetAgentName: string;
  toggleLabel: string;
}

export interface PromptGeneratorInput {
  toggles: ToggleDefinition[];
  activeToggleIds: string[];
  agents: AgentDefinition[];
  dealStatus: "Agreed" | "Blocked" | "Failed";
  finalSummary: Record<string, unknown>;
  scenarioId: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const BASELINE_TEXT =
  "You ran with all variables active. Try the clean baseline — no hidden context — and see how the agents negotiate on their own.";

function resolveAgentName(
  role: string,
  agents: AgentDefinition[],
): string | null {
  const agent = agents.find((a) => a.role === role);
  return agent ? agent.name : null;
}

function buildPromptText(
  toggle: ToggleDefinition,
  agentName: string,
  dealStatus: "Agreed" | "Blocked" | "Failed",
  finalSummary: Record<string, unknown>,
): string {
  const label = toggle.label;

  switch (dealStatus) {
    case "Agreed": {
      const offer = finalSummary.current_offer;
      if (offer != null && offer !== 0) {
        return `This deal closed at €${offer}. Toggle ${label} and see what changes.`;
      }
      return `This deal closed. Toggle ${label} and see what changes.`;
    }
    case "Blocked":
      return `The deal was blocked. Turn on ${label} and see if the outcome shifts.`;
    case "Failed": {
      const turns = finalSummary.turns_completed;
      if (turns != null) {
        return `Negotiation failed after ${turns} turns. Enable ${label} and see if ${agentName} behaves differently.`;
      }
      return `Negotiation failed. Enable ${label} and see if ${agentName} behaves differently.`;
    }
  }
}

/**
 * Select up to 3 prompts prioritizing diversity across target_agent_role.
 * Covers at least min(3, uniqueRoleCount) distinct roles.
 */
function selectDiverse(prompts: WhatIfPrompt[], toggles: ToggleDefinition[]): WhatIfPrompt[] {
  if (prompts.length <= 3) return prompts;

  // Build a map from toggle ID → toggle for role lookup
  const toggleById = new Map<string, ToggleDefinition>();
  for (const t of toggles) {
    toggleById.set(t.id, t);
  }

  // Group prompts by their target_agent_role
  const byRole = new Map<string, WhatIfPrompt[]>();
  for (const p of prompts) {
    const toggleId = p.toggleIds[0];
    const toggle = toggleId ? toggleById.get(toggleId) : undefined;
    const role = toggle?.target_agent_role ?? "";
    const group = byRole.get(role) ?? [];
    group.push(p);
    byRole.set(role, group);
  }

  const selected: WhatIfPrompt[] = [];
  const roles = Array.from(byRole.keys());

  // Round-robin: pick one from each role until we have 3
  let roleIdx = 0;
  while (selected.length < 3) {
    const role = roles[roleIdx % roles.length];
    const group = byRole.get(role)!;
    if (group.length > 0) {
      selected.push(group.shift()!);
    }
    roleIdx++;
    // Safety: if all groups are empty, break
    if (roles.every((r) => (byRole.get(r)?.length ?? 0) === 0)) break;
  }

  return selected;
}

// ---------------------------------------------------------------------------
// Main generator
// ---------------------------------------------------------------------------

export function generateWhatIfPrompts(input: PromptGeneratorInput): WhatIfPrompt[] {
  const { toggles, activeToggleIds, agents, dealStatus, finalSummary } = input;

  // All toggles active → baseline prompt
  if (toggles.length > 0 && toggles.every((t) => activeToggleIds.includes(t.id))) {
    return [
      {
        text: BASELINE_TEXT,
        toggleIds: [],
        targetAgentName: "",
        toggleLabel: "",
      },
    ];
  }

  // Compute inactive toggles
  const inactive = toggles.filter((t) => !activeToggleIds.includes(t.id));

  // Generate one prompt per inactive toggle (skip unresolvable roles)
  const prompts: WhatIfPrompt[] = [];
  for (const toggle of inactive) {
    const agentName = resolveAgentName(toggle.target_agent_role, agents);
    if (!agentName) continue; // skip unresolvable

    prompts.push({
      text: buildPromptText(toggle, agentName, dealStatus, finalSummary),
      toggleIds: [toggle.id],
      targetAgentName: agentName,
      toggleLabel: toggle.label,
    });
  }

  // Cap at 3, with role diversity selection
  return selectDiverse(prompts, toggles);
}

// ---------------------------------------------------------------------------
// Deep-link builder
// ---------------------------------------------------------------------------

export function buildDeepLinkUrl(scenarioId: string, toggleIds: string[]): string {
  if (toggleIds.length === 0) {
    return `/arena?scenario=${scenarioId}`;
  }
  return `/arena?scenario=${scenarioId}&toggles=${toggleIds.join(",")}`;
}

// ---------------------------------------------------------------------------
// Advice deep-link builder
// ---------------------------------------------------------------------------

export function buildAdviceDeepLinkUrl(
  scenarioId: string,
  agentRole: string,
  suggestedPrompt: string,
): string {
  const promptMap: Record<string, string> = { [agentRole]: suggestedPrompt };
  const encoded = btoa(JSON.stringify(promptMap));
  return `/arena?scenario=${scenarioId}&customPrompts=${encodeURIComponent(encoded)}`;
}
