# Implementation Plan: Hybrid Agent Memory (Phase 2)

## Overview

Extends spec 100 (Structured Agent Memory) with milestone summaries, configurable sliding window, and full history elimination. Implementation proceeds bottom-up: data models → state → milestone generator → orchestration integration → prompt builder → converters → API/router → frontend toggle → frontend API client.

## Tasks

- [x] 1. Extend NegotiationParams with sliding window and milestone configuration
  - [x] 1.1 Add `sliding_window_size` and `milestone_interval` fields to `NegotiationParams` in `backend/app/scenarios/models.py`
    - `sliding_window_size: int = Field(default=3, ge=1)`
    - `milestone_interval: int = Field(default=4, ge=2)`
    - Existing scenario JSONs must continue to parse without errors (backward compatible via defaults)
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Write property test for NegotiationParams backward compatibility
    - **Property 1: Round-trip serialization of NegotiationParams with and without new fields**
    - Generate random NegotiationParams dicts, some with `sliding_window_size`/`milestone_interval`, some without. Validate that `NegotiationParams.model_validate(data)` always succeeds and defaults are applied correctly.
    - **Validates: Requirements 1.3, 1.4, 9.6**

  - [x] 1.3 Write unit tests for NegotiationParams new fields
    - Test explicit values, defaults when omitted, validation errors for `sliding_window_size < 1` and `milestone_interval < 2`
    - Test that all existing scenario JSON files in `backend/app/scenarios/data/` parse without errors
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Extend NegotiationState and create_initial_state with milestone fields
  - [x] 2.1 Add milestone fields to `NegotiationState` TypedDict in `backend/app/orchestrator/state.py`
    - Add `milestone_summaries_enabled: bool`
    - Add `milestone_summaries: dict[str, list[dict[str, Any]]]`
    - Add `sliding_window_size: int`
    - Add `milestone_interval: int`
    - _Requirements: 2.1, 2.2, 2.7_

  - [x] 2.2 Update `create_initial_state` in `backend/app/orchestrator/state.py`
    - Accept `milestone_summaries_enabled` parameter (default `False`)
    - Read `sliding_window_size` and `milestone_interval` from `scenario_config["negotiation_params"]` with defaults 3 and 4
    - When `milestone_summaries_enabled=True`: force `structured_memory_enabled=True`, initialize `milestone_summaries` with empty list per agent role
    - When `milestone_summaries_enabled=False`: initialize `milestone_summaries` as empty dict
    - _Requirements: 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 2.3 Write property test for create_initial_state milestone initialization
    - **Property 2: milestone_summaries_enabled=True implies structured_memory_enabled=True**
    - Generate random scenario configs with varying agent counts. When `milestone_summaries_enabled=True`, assert `structured_memory_enabled` is also `True` and `milestone_summaries` has one empty list per agent role.
    - **Validates: Requirements 2.4, 2.5**

  - [x] 2.4 Write unit tests for NegotiationState milestone fields
    - Test `create_initial_state` with `milestone_summaries_enabled=True` and `False`
    - Verify `sliding_window_size` and `milestone_interval` are read from params with correct defaults
    - Verify backward compatibility when fields are absent from state dict
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 9.3, 9.4_

- [x] 3. Extend NegotiationStateModel for Firestore persistence
  - [x] 3.1 Add milestone fields to `NegotiationStateModel` in `backend/app/models/negotiation.py`
    - `milestone_summaries_enabled: bool = Field(default=False)`
    - `milestone_summaries: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)`
    - `sliding_window_size: int = Field(default=3, ge=1)`
    - `milestone_interval: int = Field(default=4, ge=2)`
    - Existing Firestore documents without these fields must load cleanly (`extra="ignore"` + defaults)
    - _Requirements: 2.8, 2.9, 9.5_

  - [x] 3.2 Write property test for milestone summary serialization round-trip
    - **Property 3: Round-trip consistency of milestone_summaries through NegotiationStateModel**
    - Generate random `milestone_summaries` dicts with valid `turn_number` (int) and `summary` (str) entries. Serialize via `model_dump()` and reconstruct via `NegotiationStateModel(**data)`. Assert equivalence.
    - **Validates: Requirements 10.1, 10.2, 10.3**

  - [x] 3.3 Write unit tests for NegotiationStateModel backward compatibility
    - Test that a dict without `milestone_summaries_enabled`, `milestone_summaries`, `sliding_window_size`, `milestone_interval` fields validates without errors and uses defaults
    - _Requirements: 2.8, 2.9, 9.5_

- [x] 4. Checkpoint — Ensure all model tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update converters to pass through milestone fields
  - [x] 5.1 Update `to_pydantic` and `from_pydantic` in `backend/app/orchestrator/converters.py`
    - `to_pydantic`: pass `milestone_summaries_enabled`, `milestone_summaries`, `sliding_window_size`, `milestone_interval` from state to model
    - `from_pydantic`: pass the same fields from model back to state, using `.get()` with defaults for backward compatibility
    - _Requirements: 2.8, 10.1, 10.3_

  - [x] 5.2 Write unit tests for converter round-trip with milestone fields
    - Test `to_pydantic` → `from_pydantic` preserves all milestone fields
    - Test conversion when milestone fields are absent (defaults applied)
    - _Requirements: 10.1, 10.3, 9.3, 9.4_

- [x] 6. Implement MilestoneGenerator module
  - [x] 6.1 Create `backend/app/orchestrator/milestone_generator.py`
    - Implement `async def generate_milestones(state: NegotiationState) -> dict[str, Any]`
    - For each agent in `scenario_config["agents"]`, make one async LLM call using `model_router.get_model(agent["model_id"])`
    - Build prompt with: full history, existing milestones, agent's private context (inner thoughts, goals, budget)
    - Instruct LLM to produce ≤300 token summary covering: key positions, major concessions, unresolved disputes, regulatory concerns, trajectory
    - Set `max_tokens=300` on the LLM call
    - Store result as `{"turn_number": int, "summary": str}` in `milestone_summaries[role]`
    - On LLM failure for one agent: log error, continue with remaining agents (non-blocking)
    - Track and return token usage delta in `total_tokens_used`
    - Return state delta dict: `{"milestone_summaries": updated_dict, "total_tokens_used": new_total}`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

  - [x] 6.2 Write unit tests for MilestoneGenerator
    - Mock `model_router.get_model` to return a fake LLM that returns canned summary text
    - Test that summaries are generated for each agent with correct prompt content
    - Test that LLM failure for one agent does not block others
    - Test that token usage is tracked correctly
    - Test that `max_tokens=300` is passed to the LLM call
    - _Requirements: 3.1, 3.2, 3.3, 3.8, 3.9, 3.10_

- [x] 7. Integrate milestone generation into dispatcher
  - [x] 7.1 Modify dispatcher in `backend/app/orchestrator/graph.py`
    - After turn advancement, check if `milestone_summaries_enabled` is True and `turn_count` is a non-zero multiple of `milestone_interval`
    - If triggered, call `generate_milestones(state)` and merge the returned delta into state
    - Add `milestone_generator` as a conditional node in the graph, or integrate the check directly in the dispatcher node (making it async)
    - Skip milestone generation entirely when `milestone_summaries_enabled` is False (zero overhead)
    - On failure for one agent, continue generating for remaining agents and proceed with negotiation
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 7.2 Write unit tests for dispatcher milestone triggering
    - Mock `generate_milestones` and verify it is called at correct turn intervals
    - Verify it is NOT called when `milestone_summaries_enabled` is False
    - Verify it is NOT called when `turn_count` is not a multiple of `milestone_interval`
    - Verify state is updated with milestone results
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 9.2_

- [x] 8. Update Agent Node prompt builder for configurable sliding window and milestone summaries
  - [x] 8.1 Modify `_build_prompt` in `backend/app/orchestrator/agent_node.py`
    - Replace hardcoded sliding window size of 3 with `state["sliding_window_size"]` (falling back to 3 if absent)
    - When `milestone_summaries_enabled` is True and milestones exist for the current agent:
      - Exclude all raw history except the last `sliding_window_size` entries
      - Include milestone summaries section between structured memory and sliding window, formatted as "Strategic summary as of turn N:" for each summary in chronological order
    - When `milestone_summaries_enabled` is True but no milestones exist yet: include full history (spec 100 behavior)
    - When `milestone_summaries_enabled` is False: behave identically to spec 100
    - Full history remains in `state["history"]` — only prompt construction is affected
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 8.1, 8.2, 8.3, 9.1_

  - [x] 8.2 Write property test for prompt token boundedness
    - **Property 4: Prompt size is bounded when milestones exist**
    - Generate states with varying history lengths (10–50 entries) but fixed milestone summaries. Assert that the user message length does not grow with history length when milestones exist (only sliding window + milestones included).
    - **Validates: Requirements 8.1, 8.2**

  - [x] 8.3 Write unit tests for prompt builder milestone integration
    - Test prompt with milestones enabled and milestones present: verify full history excluded, milestones included, sliding window included
    - Test prompt with milestones enabled but no milestones yet: verify full history included
    - Test prompt with milestones disabled: verify spec 100 behavior unchanged
    - Test configurable sliding window size (e.g., size=5 includes last 5 entries)
    - Test milestone summary formatting ("Strategic summary as of turn N:")
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.3, 9.1_

- [x] 9. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Update StartNegotiationRequest and negotiation router
  - [x] 10.1 Add `milestone_summaries_enabled` field to `StartNegotiationRequest` in `backend/app/routers/negotiation.py`
    - `milestone_summaries_enabled: bool = Field(default=False)`
    - _Requirements: 6.2, 6.5_

  - [x] 10.2 Update `start_negotiation` and `stream_negotiation` in `backend/app/routers/negotiation.py`
    - Pass `milestone_summaries_enabled` from request body to `create_initial_state`
    - When `milestone_summaries_enabled=True`, force `structured_memory_enabled=True` server-side regardless of request value
    - Ensure `NegotiationStateModel` persistence includes the new fields
    - Update `stream_negotiation` to pass `milestone_summaries_enabled` when building initial state from persisted session
    - _Requirements: 6.1, 6.3, 6.4, 6.5_

  - [x] 10.3 Write unit tests for negotiation router milestone toggle
    - Test request with `milestone_summaries_enabled=True` forces `structured_memory_enabled=True`
    - Test request without `milestone_summaries_enabled` defaults to `False`
    - Test that the field is persisted to Firestore
    - _Requirements: 6.2, 6.3, 6.4, 6.5_

- [x] 11. Add Milestone Summaries toggle to frontend
  - [x] 11.1 Create `MilestoneSummariesToggle` component in `frontend/components/arena/`
    - Add a "Milestone Summaries" toggle below the "Structured Agent Memory" toggle in the Advanced Options section
    - Include description: "Generate periodic strategic summaries to compress negotiation history and cap token usage for long negotiations"
    - Default to off (disabled)
    - Visually disabled (grayed out, non-interactive) when structured memory toggle is off, with helper text indicating the dependency
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [x] 11.2 Wire toggle state logic in `frontend/app/(protected)/arena/page.tsx`
    - Add `milestoneSummariesEnabled` state variable (default `false`)
    - When milestone summaries toggle is enabled: auto-enable structured memory if not already on
    - When structured memory toggle is disabled: auto-disable milestone summaries
    - Reset milestone summaries toggle to off on scenario change
    - _Requirements: 5.4, 5.5, 5.7_

  - [x] 11.3 Write frontend tests for MilestoneSummariesToggle
    - Test toggle renders with correct description
    - Test toggle is disabled when structured memory is off
    - Test enabling milestone summaries auto-enables structured memory
    - Test disabling structured memory auto-disables milestone summaries
    - Test scenario change resets toggle to off
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [x] 12. Update frontend API client to pass milestone toggle
  - [x] 12.1 Update `startNegotiation` in `frontend/lib/api.ts`
    - Add `milestoneSummariesEnabled` parameter to `startNegotiation` function
    - Include `milestone_summaries_enabled` in the POST request body
    - _Requirements: 6.1_

  - [x] 12.2 Update `handleInitialize` in `frontend/app/(protected)/arena/page.tsx`
    - Pass `milestoneSummariesEnabled` state to `startNegotiation` call
    - _Requirements: 6.1_

  - [x] 12.3 Write frontend tests for API client milestone parameter
    - Test that `startNegotiation` includes `milestone_summaries_enabled` in request body
    - Test that `false` is sent when toggle is off
    - _Requirements: 6.1_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - Run `cd backend && pytest --cov=app --cov-fail-under=70` for backend coverage
  - Run `cd frontend && npx vitest run --coverage` for frontend coverage

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (serialization round-trips, token boundedness)
- Unit tests validate specific examples and edge cases
- Backend uses pytest + pytest-asyncio; frontend uses Vitest + React Testing Library
- All LLM calls in tests must be mocked (Vertex AI SDK)
