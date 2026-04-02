# Implementation Plan: Agent Advanced Configuration

## Overview

Add per-agent advanced configuration (custom prompts + model overrides) to the Arena Selector. Implementation flows bottom-up: backend state/models → API endpoints → orchestrator logic → frontend components → tests. Python (backend) and TypeScript (frontend).

## Tasks

- [x] 1. Extend backend state and data models
  - [x] 1.1 Add `custom_prompts` and `model_overrides` fields to `NegotiationState` TypedDict in `backend/app/orchestrator/state.py`
    - Add `custom_prompts: dict[str, str]` and `model_overrides: dict[str, str]` to the TypedDict
    - Update `create_initial_state` to accept optional `custom_prompts` and `model_overrides` parameters, defaulting to `{}` when not provided
    - Store both in the returned `NegotiationState` dict
    - _Requirements: 13.2, 13.3_

  - [x] 1.2 Add `custom_prompts` and `model_overrides` fields to `NegotiationStateModel` in `backend/app/models/negotiation.py`
    - Add `custom_prompts: dict[str, str] = Field(default_factory=dict)` and `model_overrides: dict[str, str] = Field(default_factory=dict)`
    - _Requirements: 6.4, 13.1, 13.4_

  - [x] 1.3 Update `StartNegotiationRequest` in `backend/app/routers/negotiation.py`
    - Add `custom_prompts: dict[str, str] = Field(default_factory=dict)` and `model_overrides: dict[str, str] = Field(default_factory=dict)`
    - Add a `model_validator(mode="after")` that rejects any `custom_prompts` value exceeding 500 characters with a descriptive `ValueError`
    - _Requirements: 6.1, 6.2, 11.1_

  - [x] 1.4 Write property tests for `StartNegotiationRequest` round-trip serialization (P1) and custom prompt length validation (P2)
    - **Property 1: StartNegotiationRequest round-trip serialization** — generate random valid requests with `custom_prompts` (≤500 chars) and `model_overrides`, serialize to JSON, deserialize, assert equality
    - **Validates: Requirements 6.1, 11.1, 13.1**
    - **Property 2: Custom prompt length validation rejects oversized prompts** — generate strings >500 chars, assert `ValidationError` raised
    - **Validates: Requirements 6.2**
    - Test file: `backend/tests/unit/test_negotiation_models.py`

  - [x] 1.5 Write property test for state persistence round-trip (P10)
    - **Property 10: State persistence round-trip** — generate random `custom_prompts` and `model_overrides`, round-trip through `NegotiationStateModel` serialization and `create_initial_state`, assert equivalence
    - **Validates: Requirements 6.4, 11.4, 13.2, 13.4**
    - Test file: `backend/tests/unit/test_negotiation_models.py`

- [x] 2. Create GET /api/v1/models endpoint
  - [x] 2.1 Create `backend/app/routers/models.py` with a `GET /models` endpoint
    - Inject `ScenarioRegistry` via `Depends(get_scenario_registry)`
    - Iterate all scenarios, collect all `model_id` and `fallback_model_id` from every agent
    - Deduplicate, filter by `model_router.MODEL_FAMILIES` keys (prefix before first `-`)
    - Return `list[dict[str, str]]` with `model_id` and `family` fields
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 2.2 Register the models router in `backend/app/main.py`
    - Import and include `models_router` in the `api_router` with `api_router.include_router(models_router)`
    - _Requirements: 9.1_

  - [x] 2.3 Write property test for available models endpoint (P7)
    - **Property 7: Available models endpoint returns correct filtered union** — generate random scenario configs with various model_ids, mock registry, assert endpoint returns correct deduplicated filtered union with `model_id` and `family` fields
    - **Validates: Requirements 9.2, 9.3, 9.4**
    - Test file: `backend/tests/integration/test_models_router.py`

- [x] 3. Update negotiation router to handle custom_prompts and model_overrides
  - [x] 3.1 Update `start_negotiation` endpoint in `backend/app/routers/negotiation.py`
    - Validate `model_overrides` values against available models (derived from registry, same logic as `/models` endpoint) — return HTTP 422 for invalid model_ids
    - Filter `custom_prompts` and `model_overrides` keys to only include keys matching agent roles in the selected scenario (silently drop unknown keys)
    - Store validated `custom_prompts` and `model_overrides` in `NegotiationStateModel` and persist to Firestore
    - Pass both to `create_initial_state`
    - _Requirements: 6.2, 6.3, 11.2, 11.3, 6.4, 11.4_

  - [x] 3.2 Update `stream_negotiation` endpoint in `backend/app/routers/negotiation.py`
    - Pass `custom_prompts` and `model_overrides` from the loaded `NegotiationStateModel` state to `create_initial_state`
    - _Requirements: 13.2, 13.4_

  - [x] 3.3 Write property tests for invalid model rejection (P3) and unknown role key filtering (P4)
    - **Property 3: Invalid model override rejection** — generate random non-existent model_ids, POST to `/negotiation/start`, assert HTTP 422
    - **Validates: Requirements 11.2**
    - **Property 4: Unknown agent role keys are silently ignored** — generate random role strings not in scenario, assert they're filtered from stored state
    - **Validates: Requirements 6.3, 11.3**
    - Test file: `backend/tests/integration/test_negotiation_router.py`

- [x] 4. Checkpoint — Backend models and API
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update orchestrator agent_node for custom prompt injection and model override routing
  - [x] 5.1 Update `_build_prompt` in `backend/app/orchestrator/agent_node.py` for custom prompt injection
    - After the hidden context block and before the output schema block, read `custom_prompts` from state
    - If a custom prompt exists for the agent's role, append `"\nAdditional user instructions:\n{custom_prompt}"` to `parts`
    - When no custom prompt exists, behavior is identical to current (no change)
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 5.2 Update `create_agent_node._node` in `backend/app/orchestrator/agent_node.py` for model override routing
    - Read `model_overrides` from state
    - Use `model_overrides.get(agent_role, agent_config["model_id"])` as the effective model_id passed to `model_router.get_model()`
    - Preserve the original `fallback_model_id` from `agent_config`
    - When no override exists, behavior is identical to current (no change)
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [x] 5.3 Write property test for custom prompt injection (P5)
    - **Property 5: Custom prompt injection into system message** — generate random custom prompts, call `_build_prompt` with state containing `custom_prompts`, assert the delimiter `"\nAdditional user instructions:\n"` + prompt appears after persona/goals/hidden_context and before output schema JSON. When no custom prompt, assert system message is unchanged.
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    - Test file: `backend/tests/unit/test_agent_node.py`

  - [x] 5.4 Write property test for model override routing (P6)
    - **Property 6: Model override routing** — generate random model overrides, mock `model_router.get_model`, call `_node`, assert `get_model` called with overridden model_id and original fallback_model_id. When no override, assert default model_id used.
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
    - Test file: `backend/tests/unit/test_agent_node.py`

- [x] 6. Checkpoint — Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Add frontend API client functions
  - [x] 7.1 Add `fetchAvailableModels` function and `ModelInfo` interface to `frontend/lib/api.ts`
    - Add `ModelInfo` interface with `model_id: string` and `family: string`
    - Add `fetchAvailableModels(): Promise<ModelInfo[]>` that calls `GET ${API_BASE}/models`
    - _Requirements: 10.1_

  - [x] 7.2 Update `startNegotiation` function signature in `frontend/lib/api.ts`
    - Add optional `customPrompts?: Record<string, string>` and `modelOverrides?: Record<string, string>` parameters
    - Include both in the request body JSON (only when non-empty)
    - _Requirements: 5.1, 5.2, 5.5, 5.6_

  - [x] 7.3 Write property test for request payload filtering (P9)
    - **Property 9: Request payload includes only non-empty overrides** — generate random agent configs with mixed empty/non-empty prompts and overrides, assert payload contains only non-empty entries
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.5, 5.6, 5.7**
    - Test file: `frontend/__tests__/properties/startNegotiationPayload.property.test.ts`

- [x] 8. Create AdvancedConfigModal component
  - [x] 8.1 Create `frontend/components/arena/AdvancedConfigModal.tsx`
    - Implement `AdvancedConfigModalProps` interface (isOpen, agentName, agentRole, defaultModelId, availableModels, initialCustomPrompt, initialModelOverride, onSave, onCancel)
    - Textarea for custom prompt with 500-char `maxLength`, live character counter (`{length} / 500`)
    - Truncate pasted text exceeding 500 chars
    - Model selector dropdown: default model first with "(default)" suffix, all models show family label
    - Save/Cancel buttons, Escape key closes modal
    - Backdrop overlay, focus trap for accessibility
    - Responsive: full-width on `<1024px`, centered 480px modal on `≥1024px`
    - Textarea min-height: 120px
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 3.1, 3.2, 3.3, 3.4, 8.1, 8.2, 8.3_

  - [x] 8.2 Write property test for custom prompt character limit enforcement (P8)
    - **Property 8: Custom prompt character limit enforcement in textarea** — generate random strings of varying lengths, assert textarea never exceeds 500 chars and counter matches length
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    - Test file: `frontend/__tests__/properties/customPromptCharLimit.property.test.ts`

  - [x] 8.3 Write property test for model selector default ordering and labeling (P12)
    - **Property 12: Model selector default ordering and labeling** — generate random model lists and default model_id, render dropdown, assert default is first option with "(default)" suffix and all models show family label
    - **Validates: Requirements 2.5, 10.2, 10.3, 10.4**
    - Test file: `frontend/__tests__/properties/modelSelector.property.test.tsx`

  - [x] 8.4 Write property test for config save-and-reload round-trip (P13)
    - **Property 13: Config save-and-reload round-trip** — generate random prompts (≤500 chars) and model selections, simulate save then re-open, assert pre-populated values match saved values
    - **Validates: Requirements 4.3, 4.4, 4.6, 4.7**
    - Test file: `frontend/__tests__/properties/configRoundTrip.property.test.tsx`

- [x] 9. Update AgentCard with Advanced Config button and indicators
  - [x] 9.1 Update `AgentCard` component in `frontend/components/arena/AgentCard.tsx`
    - Extend `AgentCardProps` with `hasCustomPrompt: boolean`, `modelOverride: string | null`, `onAdvancedConfig: () => void`
    - Add "Advanced Config" button with Lucide `SlidersHorizontal` icon + text label below model info
    - Show visual indicator dot when `hasCustomPrompt` is true
    - Display overridden model name when `modelOverride` is non-null
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 9.2 Write property test for agent card visual indicators (P11)
    - **Property 11: Agent card visual indicators reflect configuration state** — generate random `hasCustomPrompt`/`modelOverride` combinations, render AgentCard, assert indicator presence matches props
    - **Validates: Requirements 1.4, 1.5**
    - Test file: `frontend/__tests__/properties/agentCardConfig.property.test.tsx`

- [x] 10. Update Arena page state management and wiring
  - [x] 10.1 Update `ArenaPageContent` in `frontend/app/(protected)/arena/page.tsx`
    - Add `customPrompts`, `modelOverrides`, and `availableModels` state maps
    - Fetch `availableModels` on mount via `fetchAvailableModels()` (graceful fallback on error: empty array)
    - Clear `customPrompts` and `modelOverrides` when `selectedScenarioId` changes
    - Add state for tracking which agent's modal is open (`advancedConfigAgent`)
    - Wire `AgentCard.onAdvancedConfig` to open `AdvancedConfigModal` for that agent
    - Wire `AdvancedConfigModal.onSave` to update `customPrompts` and `modelOverrides` state maps
    - Pass `customPrompts` and `modelOverrides` to `startNegotiation` call (filtering out empty values)
    - Handle model list fetch failure: Model_Selector shows only default model, dropdown disabled with tooltip
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 10.1, 10.5_

- [x] 11. Checkpoint — Full integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Unit tests for edge cases
  - [x] 12.1 Write unit tests for AdvancedConfigModal interactions
    - Test modal opens/closes on button click, Escape key, Cancel button
    - Test focus trap within modal
    - Test backdrop overlay prevents background interaction
    - Test placeholder text is displayed
    - _Requirements: 2.6, 2.7, 2.8, 2.9, 2.10_

  - [x] 12.2 Write unit tests for Arena page state management
    - Test scenario change clears all custom prompts and model overrides
    - Test API error fallback for model list fetch failure
    - Test empty `custom_prompts`/`model_overrides` produce identical behavior to no feature
    - _Requirements: 4.5, 10.5_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend tasks (1-6) are independent of frontend tasks (7-12) and can be parallelized
