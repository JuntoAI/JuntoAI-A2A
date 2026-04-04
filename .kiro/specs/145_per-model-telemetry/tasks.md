# Implementation Plan: Per-Model Telemetry

## Overview

Instrument the agent node to capture per-LLM-call telemetry (model_id, latency, token breakdown, error status) as `AgentCallRecord` dicts accumulated in an append-only `agent_calls` list on the session state. New Pydantic model, state field with `add` reducer, converter updates, and `_node()` instrumentation with try/except safety. Prerequisite for Spec 150 (Admin Dashboard).

## Tasks

- [ ] 1. AgentCallRecord model and state plumbing
  - [ ] 1.1 Add `AgentCallRecord` Pydantic model to `backend/app/orchestrator/outputs.py`
    - Define fields: `agent_role` (str), `agent_type` (str), `model_id` (str), `latency_ms` (int, ge=0), `input_tokens` (int, default=0, ge=0), `output_tokens` (int, default=0, ge=0), `error` (bool, default=False), `turn_number` (int, ge=0), `timestamp` (str)
    - _Requirements: 1.1_

  - [ ] 1.2 Add `agent_calls` field to `NegotiationState` TypedDict in `backend/app/orchestrator/state.py`
    - Add `agent_calls: Annotated[list[dict[str, Any]], add]` following the same append-on-merge pattern as `history`
    - _Requirements: 2.1_

  - [ ] 1.3 Initialize `agent_calls=[]` in `create_initial_state()` in `backend/app/orchestrator/state.py`
    - Add `agent_calls=[]` to the returned `NegotiationState` dict
    - _Requirements: 2.2_

  - [ ] 1.4 Add `agent_calls` field to `NegotiationStateModel` in `backend/app/models/negotiation.py`
    - Add `agent_calls: list[dict[str, Any]] = Field(default_factory=list)`
    - _Requirements: 2.3_

  - [ ] 1.5 Update converters in `backend/app/orchestrator/converters.py`
    - `to_pydantic()`: add `agent_calls=state.get("agent_calls", [])` (backward compat for sessions without the field)
    - `from_pydantic()`: add `agent_calls=model.agent_calls`
    - _Requirements: 2.4, 4.3_

  - [ ]* 1.6 Write property test: AgentCallRecord round-trip serialization (Property 1)
    - **Property 1: AgentCallRecord round-trip serialization**
    - Generate random valid `AgentCallRecord` instances via Hypothesis; serialize with `.model_dump_json()` and deserialize with `AgentCallRecord.model_validate_json()`; assert equality
    - File: `backend/tests/property/test_telemetry_properties.py`
    - **Validates: Requirements 1.2**

  - [ ]* 1.7 Write property test: Converter round-trip preserves agent_calls (Property 2)
    - **Property 2: Converter round-trip preserves agent_calls**
    - Generate random lists of valid `AgentCallRecord` dicts; place in a `NegotiationState`; round-trip through `to_pydantic()` then `from_pydantic()`; assert `agent_calls` is equal
    - File: `backend/tests/property/test_telemetry_properties.py`
    - **Validates: Requirements 2.4**

  - [ ]* 1.8 Write unit tests for AgentCallRecord and state plumbing
    - Test `AgentCallRecord` rejects negative `latency_ms`, negative `input_tokens`, negative `output_tokens`
    - Test `NegotiationStateModel` defaults `agent_calls` to `[]`
    - Test `create_initial_state()` includes `agent_calls=[]`
    - Test converters map `agent_calls` correctly; missing field defaults to `[]`
    - File: `backend/tests/unit/orchestrator/test_telemetry.py`
    - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4, 4.3_

- [ ] 2. Checkpoint — State plumbing
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Agent node instrumentation
  - [ ] 3.1 Add `_extract_tokens()` helper to `backend/app/orchestrator/agent_node.py`
    - Extract `(input_tokens, output_tokens)` from `response.usage_metadata` handling dict, object, and `None` cases
    - Replace the existing inline token extraction in `_node()` with calls to this helper
    - _Requirements: 3.2_

  - [ ] 3.2 Instrument the first `model.invoke()` call in `_node()` with telemetry
    - Wrap with `time.perf_counter()` to capture `latency_ms`
    - Extract tokens via `_extract_tokens()`
    - Build `AgentCallRecord` dict with `agent_role`, `agent_type`, `effective_model_id`, `latency_ms`, `input_tokens`, `output_tokens`, `error=False`, `turn_number`, and UTC ISO 8601 `timestamp`
    - Append to `call_records` list
    - Wrap all telemetry code in try/except, log WARNING on failure
    - _Requirements: 3.1, 3.2, 3.5, 3.6, 3.7, 5.1, 5.3_

  - [ ] 3.3 Instrument the retry `model.invoke()` call in `_node()` with telemetry
    - Same timing/token/record pattern as 3.2 for the retry call
    - Set `error=True` when retry parse also fails and fallback is used
    - Record a separate `AgentCallRecord` for the retry (not merged with first call)
    - Wrap in try/except independently from the first call's telemetry
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 5.1_

  - [ ] 3.4 Include `agent_calls` in the state delta returned by `_node()`
    - Add `merged["agent_calls"] = call_records` so LangGraph appends via the `add` reducer
    - Ensure no existing state fields are modified by telemetry code
    - _Requirements: 3.5, 4.1, 4.2, 5.2_

  - [ ]* 3.5 Write property test: Token extraction correctness (Property 3)
    - **Property 3: Token extraction correctness**
    - Generate random non-negative `(input_tokens, output_tokens)` pairs; mock `usage_metadata` as dict, as object with attributes, and as `None`; assert `_extract_tokens()` returns the correct pair or `(0, 0)`
    - File: `backend/tests/property/test_telemetry_properties.py`
    - **Validates: Requirements 3.2**

  - [ ]* 3.6 Write unit tests for agent node telemetry instrumentation
    - Test successful LLM call produces exactly 1 `AgentCallRecord` in state delta with correct fields
    - Test retry produces 2 `AgentCallRecords` (first with `error=False`, retry with its own latency/tokens)
    - Test fallback sets `error=True` on the retry record
    - Test `timestamp` is valid UTC ISO 8601 string
    - Test `model_id` reflects `model_overrides` when present
    - Test telemetry failure (e.g., `AgentCallRecord` validation error) does not break `_node()` — state delta still returned with history, turn_count, etc. intact
    - Test non-telemetry state fields (`history`, `turn_count`, `deal_status`, `current_offer`, `agent_states`) are unchanged by telemetry
    - File: `backend/tests/unit/orchestrator/test_agent_node_telemetry.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 5.2, 5.3_

- [ ] 4. Final checkpoint — All telemetry complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 3 correctness properties defined in the design (Hypothesis, min 100 examples)
- This spec is a prerequisite for Spec 150 (Admin Dashboard) which reads `agent_calls` for per-model metrics
- All telemetry code must be wrapped in try/except — failures must never break negotiation logic
