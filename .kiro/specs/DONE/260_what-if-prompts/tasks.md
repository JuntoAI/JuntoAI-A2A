# Tasks: What-If Prompts

## Task 1: Extend ToggleDefinition and create Prompt Generator module

- [x] 1.1 Add `target_agent_role: string` to `ToggleDefinition` interface in `frontend/lib/api.ts`
    - The backend already returns this field; the frontend was ignoring it
    - _Requirements: 1.3, 5.4_
- [x] 1.2 Create `frontend/lib/whatIfPrompts.ts` with types and `generateWhatIfPrompts()` function
    - Export `WhatIfPrompt` interface: `{ text: string; toggleIds: string[]; targetAgentName: string; toggleLabel: string }`
    - Export `PromptGeneratorInput` interface: `{ toggles: ToggleDefinition[]; activeToggleIds: string[]; agents: AgentDefinition[]; dealStatus: "Agreed" | "Blocked" | "Failed"; finalSummary: Record<string, unknown>; scenarioId: string }`
    - Implement inactive toggle computation: `toggles.filter(t => !activeToggleIds.includes(t.id))`
    - Implement prompt text generation per deal status (Agreed: include offer value, Blocked: reference block, Failed: reference turns)
    - Resolve `target_agent_role` to agent `name` using the agents array
    - When all toggles active, return single baseline "all toggles off" prompt with empty `toggleIds`
    - When >3 inactive toggles, select 3 prioritizing different `target_agent_role` values
    - Cap output at max 3 prompts
    - Skip toggles whose `target_agent_role` doesn't match any agent
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 5.3, 5.4, 5.5_
- [x] 1.3 Export `buildDeepLinkUrl(scenarioId: string, toggleIds: string[]): string` in `frontend/lib/whatIfPrompts.ts`
    - Return `/arena?scenario={scenarioId}&toggles={id1},{id2}` format
    - When `toggleIds` is empty (baseline prompt), return `/arena?scenario={scenarioId}` (no toggles param)
    - _Requirements: 3.1_

## Task 2: Update OutcomeReceipt component

- [x] 2.1 Add new optional props to `OutcomeReceiptProps` in `frontend/components/glassbox/OutcomeReceipt.tsx`
    - Add `toggles?: ToggleDefinition[]`
    - Add `activeToggleIds?: string[]`
    - Add `agents?: AgentDefinition[]`
    - Import types from `@/lib/api`
    - _Requirements: 4.3_
- [x] 2.2 Add What-If prompt generation and card rendering to OutcomeReceipt
    - Call `generateWhatIfPrompts()` when `toggles`, `activeToggleIds`, and `agents` are all provided
    - When prompts are available, render each as a clickable card with: prompt text, target agent name, toggle label
    - Each card navigates to `buildDeepLinkUrl()` on click
    - Retain "Reset with Different Variables" button alongside prompt cards
    - When no prompts available (no toggles, or props missing), fall back to existing "Run Another Scenario" button
    - Cards layout: `flex flex-col sm:flex-row` for responsive stacking/side-by-side
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.4_

## Task 3: Pass scenario context to OutcomeReceipt from session page

- [x] 3.1 Update session page URL to include active toggle IDs
    - In `frontend/app/(protected)/arena/page.tsx`, append `&toggles={activeToggles.join(",")}` to the session navigation URL in `handleInitialize`
    - Only append when `activeToggles.length > 0`
    - _Requirements: 4.2_
- [x] 3.2 Pass toggle definitions, active toggle IDs, and agents to OutcomeReceipt in session page
    - In `frontend/app/(protected)/arena/session/[sessionId]/page.tsx`, extract `toggles` param from `searchParams`
    - Parse comma-separated toggle IDs into `activeToggleIds` array
    - Pass `scenarioDetail.toggles`, `activeToggleIds`, and `scenarioDetail.agents` as props to `OutcomeReceipt`
    - _Requirements: 4.1, 4.2_

## Task 4: Deep-link toggle pre-configuration in Arena Selector

- [x] 4.1 Parse `toggles` query parameter in Arena page and activate valid toggles
    - In `frontend/app/(protected)/arena/page.tsx`, after `scenarioDetail` loads, read `toggles` from `searchParams`
    - Split by comma, filter to IDs that exist in `scenarioDetail.toggles`
    - Call `setActiveToggles(validIds)` — only when `selectedScenarioId` is also present
    - Ignore `toggles` param entirely when no `scenario` param is present
    - _Requirements: 3.2, 3.3, 3.4, 3.5_

## Task 5: Write property-based tests for Prompt Generator

- [x] 5.1 Write property test: Inactive toggle computation is correct (`frontend/__tests__/properties/whatIfPrompts.property.test.ts`) [PBT]
    - **Property 1: Inactive toggle computation is correct**
    - Generate random toggle definitions (with id, label, target_agent_role) and random subsets as activeToggleIds
    - Generate matching agent definitions for each unique target_agent_role
    - Verify prompts are generated only for toggles not in activeToggleIds
    - Verify count matches inactive toggle count (capped at 3)
    - `@settings(min 100 iterations)` — use `fc.assert` with `{ numRuns: 100 }`
    - _Requirements: 1.1, 1.2_
- [x] 5.2 Write property test: Prompt text contains toggle label and resolved agent name [PBT]
    - **Property 2: Prompt text contains toggle label and resolved agent name**
    - Generate random toggles with agents, ensure at least 1 inactive toggle
    - Verify each prompt's `text` contains the toggle's `label`
    - Verify each prompt's `targetAgentName` matches the agent whose role equals the toggle's `target_agent_role`
    - _Requirements: 1.3, 5.4_
- [x] 5.3 Write property test: All-active scenario produces baseline prompt [PBT]
    - **Property 3: All-active scenario produces baseline prompt**
    - Generate random toggles, set activeToggleIds = all toggle IDs
    - Verify exactly 1 prompt returned with empty `toggleIds` array
    - _Requirements: 1.4, 5.5_
- [x] 5.4 Write property test: Output length never exceeds 3 [PBT]
    - **Property 4: Output length never exceeds 3**
    - Generate random inputs with 0–10 toggles and random active subsets
    - Verify `prompts.length <= 3` always holds
    - _Requirements: 1.5_
- [x] 5.5 Write property test: Role diversity maximization [PBT]
    - **Property 5: Role diversity maximization**
    - Generate scenarios with >3 inactive toggles targeting various roles
    - Verify selected 3 cover at least `min(3, uniqueRoleCount)` distinct target_agent_role values
    - _Requirements: 1.6_
- [x] 5.6 Write property test: Deal-status-specific prompt content [PBT]
    - **Property 6: Deal-status-specific prompt content**
    - Generate random Agreed outcomes with current_offer > 0, verify prompt text contains the offer value
    - Generate random Blocked outcomes, verify prompt text references block
    - Generate random Failed outcomes with turns_completed, verify prompt text references turn count
    - _Requirements: 5.1, 5.2, 5.3_
- [x] 5.7 Write property test: Deep-link URL round-trip [PBT]
    - **Property 7: Deep-link URL round-trip**
    - Generate random scenario IDs (alphanumeric + underscores) and random toggle ID lists
    - Build URL with `buildDeepLinkUrl`, parse it back, verify scenario and toggles match original
    - _Requirements: 3.1, 3.2_

## Task 6: Write unit tests

- [x] 6.1 Write unit tests for Prompt Generator (`frontend/__tests__/lib/whatIfPrompts.test.ts`)
    - Test specific example: Agreed deal with 2 inactive toggles → 2 prompt cards with offer value in text
    - Test specific example: Blocked deal → prompt text references block
    - Test specific example: Failed deal → prompt text references turns
    - Test edge case: 0 toggles in scenario → empty array returned
    - Test edge case: exactly 3 inactive toggles → all 3 returned, no selection needed
    - Test edge case: toggle with unresolvable target_agent_role → skipped
    - Test baseline prompt text content matches expected format
    - _Requirements: 1.1–1.6, 5.1–5.5_
- [x] 6.2 Write/update unit tests for OutcomeReceipt component (`frontend/__tests__/components/glassbox/OutcomeReceipt.test.tsx`)
    - Test: renders prompt cards when toggles + activeToggleIds + agents provided
    - Test: retains "Reset with Different Variables" button alongside cards
    - Test: falls back to "Run Another Scenario" when toggles prop not provided
    - Test: falls back when toggles array is empty
    - Test: card click navigates to correct deep-link URL
    - _Requirements: 2.1–2.5, 4.3, 4.4_

## Task 7: Add "Try This" button to advice items in OutcomeReceipt

- [x] 7.1 Create `buildAdviceDeepLinkUrl` utility function in `frontend/lib/whatIfPrompts.ts`
    - Export `buildAdviceDeepLinkUrl(scenarioId: string, agentRole: string, suggestedPrompt: string): string`
    - Encode `{ [agentRole]: suggestedPrompt }` as `btoa(JSON.stringify(map))`
    - Return `/arena?scenario={scenarioId}&customPrompts={encodeURIComponent(encoded)}`
    - _Requirements: 6.2, 6.3, 6.9_
- [x] 7.2 Add "Try This" button to each advice item in `OutcomeReceipt.tsx`
    - In the Blocked deal advice section (`data-testid="block-advice"`), add a button after each `<pre>` block
    - Button text: "Try This", `data-testid="try-this-btn-{i}"`
    - On click: call `router.push(buildAdviceDeepLinkUrl(scenarioId, item.agent_role, item.suggested_prompt))`
    - Replace the italic "Paste this into Advanced Options…" text with the button
    - Only render button when `item.suggested_prompt` is non-empty AND `scenarioId` is not null
    - Style: `rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 transition-colors`
    - _Requirements: 6.1, 6.9, 6.10_

## Task 8: Parse `customPrompts` query param in Arena page

- [x] 8.1 Add `customPrompts` query param parsing in Arena page (`frontend/app/(protected)/arena/page.tsx`)
    - After `scenarioDetail` loads, read `customPrompts` from `searchParams`
    - Decode: `JSON.parse(atob(decodeURIComponent(raw)))` → `Record<string, string>`
    - Validate: filter to only roles present in `scenarioDetail.agents`
    - Apply: call `setCustomPrompts(filtered)` with the valid entries
    - Wrap in try/catch — on any error (bad Base64, bad JSON), log warning and ignore
    - Only process when `selectedScenarioId` is also present (ignore without `scenario` param)
    - Must run AFTER the `useEffect` that resets `customPrompts` on scenario change
    - _Requirements: 6.4, 6.5, 6.6, 6.7, 6.8_

## Task 9: Write property-based tests for Apply Advice Recommendation

- [x] 9.1 Write property test: Custom prompts URL encoding round-trip (`frontend/__tests__/properties/adviceDeepLink.property.test.ts`) [PBT]
    - **Property 8: Custom prompts URL encoding round-trip**
    - Generate random `Record<string, string>` maps (role → prompt text with unicode, newlines, special chars)
    - Encode with `btoa(JSON.stringify(map))`, decode with `JSON.parse(atob(encoded))`, verify deep equality
    - Also test full URL round-trip: build URL with `buildAdviceDeepLinkUrl`, extract `customPrompts` param, decode, verify original role and prompt are preserved
    - `@settings(min 100 iterations)` — use `fc.assert` with `{ numRuns: 100 }`
    - _Requirements: 6.2, 6.3, 6.4_
- [x] 9.2 Write property test: Only valid roles are prefilled (`frontend/__tests__/properties/adviceDeepLink.property.test.ts`) [PBT]
    - **Property 9: Only valid roles are prefilled**
    - Generate random decoded maps and random agent role lists
    - Filter the map to only roles in the agent list
    - Verify the filtered result contains no roles outside the agent list
    - Verify the filtered result retains all roles that were in both the map and the agent list
    - `@settings(min 100 iterations)` — use `fc.assert` with `{ numRuns: 100 }`
    - _Requirements: 6.6_

## Task 10: Write unit tests for Apply Advice Recommendation

- [x] 10.1 Write unit tests for advice "Try This" button in OutcomeReceipt (`frontend/__tests__/components/glassbox/OutcomeReceipt.test.tsx`)
    - Test: renders "Try This" button for each advice item with non-empty `suggested_prompt`
    - Test: does not render "Try This" button when `suggested_prompt` is empty or missing
    - Test: does not render "Try This" button when `scenarioId` is null
    - Test: click navigates to URL containing `scenario` param and Base64-encoded `customPrompts` param
    - Test: decoded `customPrompts` param contains correct `agent_role` → `suggested_prompt` mapping
    - _Requirements: 6.1, 6.2, 6.3, 6.9, 6.10_
- [x] 10.2 Write unit tests for Arena page `customPrompts` param parsing (`frontend/__tests__/pages/arena-advanced-config.test.tsx`)
    - Test: parses and prefills valid custom prompts from URL after scenario loads
    - Test: ignores roles not in the scenario's agent list
    - Test: ignores malformed Base64 / invalid JSON gracefully (no crash)
    - Test: ignores `customPrompts` param when no `scenario` param is present
    - Test: agent card shows `hasCustomPrompt` indicator for prefilled agents
    - _Requirements: 6.4, 6.5, 6.6, 6.7, 6.8_
