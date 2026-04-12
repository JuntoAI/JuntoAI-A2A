import { describe, it, expect } from "vitest";
import {
  generateWhatIfPrompts,
  buildDeepLinkUrl,
  type PromptGeneratorInput,
} from "@/lib/whatIfPrompts";
import type { ToggleDefinition, AgentDefinition } from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeToggle = (
  id: string,
  label: string,
  role: string,
): ToggleDefinition => ({ id, label, target_agent_role: role });

const makeAgent = (name: string, role: string): AgentDefinition => ({
  name,
  role,
  goals: [],
  model_id: "gemini-3-flash-preview",
  type: "negotiator",
});

const baseInput = (overrides: Partial<PromptGeneratorInput> = {}): PromptGeneratorInput => ({
  toggles: [
    makeToggle("t1", "Competing Offer", "candidate"),
    makeToggle("t2", "Deadline Pressure", "recruiter"),
    makeToggle("t3", "Remote Only", "candidate"),
  ],
  activeToggleIds: ["t1"],
  agents: [makeAgent("Alex", "candidate"), makeAgent("Jordan", "recruiter")],
  dealStatus: "Agreed",
  finalSummary: { current_offer: 125000, turns_completed: 6 },
  scenarioId: "talent_war",
  ...overrides,
});

// ---------------------------------------------------------------------------
// generateWhatIfPrompts
// ---------------------------------------------------------------------------

describe("generateWhatIfPrompts", () => {
  it("Agreed deal with 2 inactive toggles → 2 prompt cards with offer value in text", () => {
    const input = baseInput({ activeToggleIds: ["t1"] });
    const prompts = generateWhatIfPrompts(input);

    expect(prompts).toHaveLength(2);
    for (const p of prompts) {
      expect(p.text).toContain("125000");
    }
  });

  it("Blocked deal → prompt text references block", () => {
    const input = baseInput({
      dealStatus: "Blocked",
      finalSummary: { blocked_by: "EU Regulator", reason: "Compliance" },
    });
    const prompts = generateWhatIfPrompts(input);

    expect(prompts.length).toBeGreaterThan(0);
    for (const p of prompts) {
      expect(p.text.toLowerCase()).toContain("blocked");
    }
  });

  it("Failed deal → prompt text references turns", () => {
    const input = baseInput({
      dealStatus: "Failed",
      finalSummary: { turns_completed: 8 },
    });
    const prompts = generateWhatIfPrompts(input);

    expect(prompts.length).toBeGreaterThan(0);
    for (const p of prompts) {
      expect(p.text).toContain("8");
      expect(p.text.toLowerCase()).toContain("failed");
    }
  });

  it("0 toggles in scenario → empty array returned", () => {
    const input = baseInput({ toggles: [], activeToggleIds: [] });
    const prompts = generateWhatIfPrompts(input);

    expect(prompts).toEqual([]);
  });

  it("exactly 3 inactive toggles → all 3 returned, no selection needed", () => {
    const input = baseInput({ activeToggleIds: [] });
    const prompts = generateWhatIfPrompts(input);

    expect(prompts).toHaveLength(3);
  });

  it("toggle with unresolvable target_agent_role → skipped", () => {
    const input = baseInput({
      toggles: [
        makeToggle("t1", "Competing Offer", "candidate"),
        makeToggle("t_bad", "Ghost Toggle", "nonexistent_role"),
      ],
      activeToggleIds: [],
    });
    const prompts = generateWhatIfPrompts(input);

    expect(prompts).toHaveLength(1);
    expect(prompts[0].toggleLabel).toBe("Competing Offer");
  });

  it("baseline prompt when all toggles are active", () => {
    const input = baseInput({ activeToggleIds: ["t1", "t2", "t3"] });
    const prompts = generateWhatIfPrompts(input);

    expect(prompts).toHaveLength(1);
    expect(prompts[0].toggleIds).toEqual([]);
    expect(prompts[0].text).toContain("all variables active");
    expect(prompts[0].text).toContain("clean baseline");
  });
});

// ---------------------------------------------------------------------------
// buildDeepLinkUrl
// ---------------------------------------------------------------------------

describe("buildDeepLinkUrl", () => {
  it("builds URL with scenario and toggles", () => {
    const url = buildDeepLinkUrl("talent_war", ["t1", "t2"]);
    expect(url).toBe("/arena?scenario=talent_war&toggles=t1,t2");
  });

  it("builds URL without toggles param when toggleIds is empty", () => {
    const url = buildDeepLinkUrl("talent_war", []);
    expect(url).toBe("/arena?scenario=talent_war");
  });
});
