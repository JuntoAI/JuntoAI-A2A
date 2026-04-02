# Implementation Plan: Structured Agent Memory

## Overview

Incremental implementation of per-agent structured memory with sliding window prompts, opt-in via frontend toggle. Backend changes flow bottom-up: model → state → converters → prompt builder → memory extractor → stall detector. Frontend adds the Advanced Options UI section last. Each step builds on the previous and wires into existing code.

## Tasks

- [ ] 1. Add AgentMemory model and update state infrastructure
  - [ ] 1.1 Create `AgentMemory` Pydantic V2 model in `backend/app/orchestrator/outputs.py`
    - Add `AgentMemory(BaseModel)` with fields: `my_offers: list[float]`, `their_offers: list[float]`, `concessions_made: list[str]`, `concessions_received: list[str]`, `open_items: list[str]`, `tactics_used: list[str]`, `red_lines_stated: list[str]`, `compliance_status: dict[str, str]`, `turn_count: int = 0`
    - All list fields default to `Field(default_factory=list)`, `compliance_status` to `Field(default_factory=dict)`
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ]* 1.2 Write property test for AgentMemory serialization round-trip
    - **Property 1: AgentMemory serialization round-trip**
    - Use `hypothesis` to generate arbitrary `AgentMemory` instances, verify `AgentMemory(**inst.model_dump()) == inst`
    - Place in `backend/tests/property/test_agent_memory_properties.py`
    - **Validates: Requirements 1.4, 9.1**

  - [ ]* 1.3 Write property test for AgentMemory JSON serializability
    - **Property 10: AgentMemory produces JSON-serializable output**
    - Use `hypothesis` to generate arbitrary `AgentMemory` instances, verify `json.dumps(inst.model_dump())` succeeds
    - Place in `backend/tests/property/test_agent_memory_properties.py`
    - **Validates: Requirements 9.3**

  - [ ] 1.4 Add `structured_memory_enabled` and `agent_memories` to `NegotiationState` TypedDict in `backend/app/orchestrator/state.py`
    - Add `structured_memory_enabled: bool` and `agent_memories: dict[str, dict[str, Any]]` fields
    - Update `create_initial_state` to accept `structured_memory_enabled: bool = False` parameter
    - When `True`: populate `agent_memories` with `AgentMemory().model_dump()` per agent role
    - When `False`: set `agent_memories` to `{}`
    - Include both fields in the returned `NegotiationState` dict
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 1.5 Write property test for `create_initial_state` memory initialization
    - **Property 2: create_initial_state memory initialization**
    - Use `hypothesis` to generate scenario configs with N agents and boolean `structured_memory_enabled`
    - Verify correct key count and default memory values when enabled, empty dict when disabled
    - Place in `backend/tests/property/test_agent_memory_properties.py`
    - **Validates: Requirements 2.3, 2.4, 2.5**

  - [ ] 1.6 Add `structured_memory_enabled` and `agent_memories` to `NegotiationStateModel` in `backend/app/models/negotiation.py`
    - `structured_memory_enabled: bool = Field(default=False)`
    - `agent_memories: dict[str, dict[str, Any]] = Field(default_factory=dict)`
    - Defaults ensure backward compatibility with existing Firestore documents
    - _Requirements: 2.6, 8.4, 8.5_

- [ ] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Update converters and API layer
  - [ ] 3.1 Update `to_pydantic` and `from_pydantic` in `backend/app/orchestrator/converters.py`
    - Map `structured_memory_enabled` and `agent_memories` between `NegotiationState` and `NegotiationStateModel`
    - Use `.get()` with defaults for backward compatibility in `to_pydantic`
    - _Requirements: 9.2, 8.4_

  - [ ]* 3.2 Write property test for full state round-trip with memory
    - **Property 9: Full state round-trip with memory**
    - Use `hypothesis` to generate `NegotiationState` dicts with populated `agent_memories`
    - Verify `from_pydantic(to_pydantic(state))` preserves `agent_memories` and `structured_memory_enabled`
    - Place in `backend/tests/unit/orchestrator/test_converters.py` or `backend/tests/property/test_agent_memory_properties.py`
    - **Validates: Requirements 9.2**

  - [ ] 3.3 Add `structured_memory_enabled` to `StartNegotiationRequest` in `backend/app/routers/negotiation.py`
    - Add `structured_memory_enabled: bool = Field(default=False)` to the request model
    - Pass `body.structured_memory_enabled` through to `NegotiationStateModel` construction in `start_negotiation`
    - _Requirements: 4.2, 4.3, 4.4_

- [ ] 4. Implement memory-aware prompt building in `_build_prompt`
  - [ ] 4.1 Modify `_build_prompt` in `backend/app/orchestrator/agent_node.py` for structured memory mode
    - When `state.get("structured_memory_enabled", False)` is `True`:
      - Serialize `AgentMemory` fields with labeled sections (e.g., "Your previous offers:", "Concessions you made:")
      - Append `history[-3:]` as sliding window in the same format as current history entries
    - When `False`: no change to current behavior (full history in prompt)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 4.2 Write property test for memory-enabled prompt format
    - **Property 3: Memory-enabled prompt contains labeled memory and sliding window**
    - Verify prompt contains labeled sections for non-empty memory fields, does NOT contain full history, and contains exactly `min(3, len(history))` sliding window entries
    - Place in `backend/tests/unit/orchestrator/test_agent_node_properties.py`
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

  - [ ]* 4.3 Write property test for disabled memory prompt identity
    - **Property 4: Disabled memory produces identical prompts**
    - Verify `_build_prompt` output is identical to current implementation when `structured_memory_enabled=False`
    - Place in `backend/tests/unit/orchestrator/test_agent_node_properties.py`
    - **Validates: Requirements 5.5, 8.1**

- [ ] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement memory extraction in `_update_state`
  - [ ] 6.1 Add memory extraction logic to `_update_state` in `backend/app/orchestrator/agent_node.py`
    - When `structured_memory_enabled` is `True` and agent type is `negotiator`:
      - Load current `AgentMemory` from `state.get("agent_memories", {}).get(role, AgentMemory().model_dump())`
      - Append `proposed_price` to `my_offers`
      - Find last opposing negotiator's `proposed_price` from history, append to `their_offers`
      - Increment `turn_count` by 1
      - Store updated `AgentMemory.model_dump()` back into `agent_memories[role]` in the state delta
    - When `False`: skip all memory logic, produce identical delta to current implementation
    - Handle missing role in `agent_memories` by initializing fresh `AgentMemory`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 6.2 Write property test for memory extractor updates
    - **Property 5: Memory extractor correctly updates agent memory**
    - Verify `my_offers` ends with new `proposed_price`, `turn_count` incremented by 1, result is valid `AgentMemory` dict
    - Place in `backend/tests/unit/orchestrator/test_agent_node_properties.py`
    - **Validates: Requirements 6.1, 6.3, 6.4**

  - [ ]* 6.3 Write property test for opposing offer capture
    - **Property 6: Memory extractor captures opposing offers**
    - Verify `their_offers` ends with most recent opposing negotiator's `proposed_price` when history contains one
    - Place in `backend/tests/unit/orchestrator/test_agent_node_properties.py`
    - **Validates: Requirements 6.2**

  - [ ]* 6.4 Write property test for memory extraction skipped when disabled
    - **Property 7: Memory extraction skipped when disabled**
    - Verify `_update_state` produces identical delta when `structured_memory_enabled=False`
    - Place in `backend/tests/unit/orchestrator/test_agent_node_properties.py`
    - **Validates: Requirements 6.5, 8.2**

- [ ] 7. Update stall detector for structured memory
  - [ ] 7.1 Modify `_get_prices_by_role` in `backend/app/orchestrator/stall_detector.py`
    - When `structured_memory_enabled` is `True`: read `my_offers` directly from `agent_memories[role]`
    - When `False`: use existing history-parsing logic unchanged
    - Update `detect_stall` to pass `state` to `_get_prices_by_role` (or extract the flag internally)
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ]* 7.2 Write property test for stall detector equivalence
    - **Property 8: Stall detector equivalence**
    - For states where `agent_memories` is consistent with `history`, verify `detect_stall` produces identical results regardless of `structured_memory_enabled` value
    - Place in `backend/tests/unit/orchestrator/test_stall_detector.py` or `backend/tests/property/test_agent_memory_properties.py`
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 8.3**

- [ ] 8. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Frontend: Advanced Options UI and API wiring
  - [ ] 9.1 Add `structuredMemoryEnabled` parameter to `startNegotiation` in `frontend/lib/api.ts`
    - Add optional `structuredMemoryEnabled?: boolean` parameter
    - Include `structured_memory_enabled: structuredMemoryEnabled ?? false` in the request body
    - _Requirements: 4.1_

  - [ ] 9.2 Add collapsible "Advanced Options" section to `frontend/app/(protected)/arena/page.tsx`
    - Add state: `structuredMemoryEnabled` (boolean, default `false`), `advancedOptionsOpen` (boolean, default `false`)
    - Render collapsible section below Hidden Variables with chevron icon (use Lucide `ChevronDown`/`ChevronUp`)
    - Inside: toggle switch for "Structured Agent Memory" with description text
    - Reset `structuredMemoryEnabled` to `false` when scenario changes (in `handleScenarioSelect`)
    - Pass `structuredMemoryEnabled` to `startNegotiation` call in `handleInitialize`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1_

  - [ ]* 9.3 Write frontend tests for Advanced Options section
    - Vitest + React Testing Library tests verifying:
      - Section renders collapsed by default
      - Toggle defaults to off
      - Toggle resets on scenario change
      - `startNegotiation` called with `structured_memory_enabled` in payload
    - Place in `frontend/__tests__/components/AdvancedOptions.test.tsx`
    - _Requirements: 3.2, 3.4, 3.5, 4.1_

- [ ] 10. Final checkpoint — Ensure all tests pass
  - Ensure all backend and frontend tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` with minimum 100 examples per test
- Backend is Python (FastAPI + Pydantic V2), frontend is TypeScript (Next.js + Tailwind)
- All `.get()` calls with defaults ensure backward compatibility with pre-feature sessions
