# Implementation Plan: Agent Gateway API & Remote Agent Node

## Overview

Extend the JuntoAI orchestrator to support external AI agents via HTTP. The implementation adds an `endpoint` field to `AgentDefinition`, creates `TurnPayload`/`TurnResponse` contract models, branches `create_agent_node` to route between local LLM and remote HTTP paths, adds pre-negotiation health checks, and wires in configurable timeouts with robust error handling. Ordered by dependency — schema first, then contract models, then node logic, then integration points.

## Tasks

- [ ] 1. Extend AgentDefinition schema and Settings
  - [ ] 1.1 Add `endpoint` field to `AgentDefinition` in `backend/app/scenarios/models.py`
    - Add `endpoint: str | None = Field(default=None, ...)` with `@field_validator` for HTTP/HTTPS URL validation
    - Reject empty strings, non-HTTP(S) schemes, malformed URLs at Pydantic validation time
    - `None` always accepted (backward compatible)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2_

  - [ ] 1.2 Add remote agent timeout settings to `backend/app/config.py`
    - Add `REMOTE_AGENT_TIMEOUT_SECONDS: float = 30.0`
    - Add `REMOTE_AGENT_HEALTH_CHECK_TIMEOUT_SECONDS: float = 5.0`
    - Both configurable via environment variables (inherited from `BaseSettings`)
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 1.3 Write property test for endpoint URL validation (Property 1)
    - **Property 1: Endpoint URL Validation**
    - Generate random strings via `st.text()`, valid HTTP/HTTPS URLs via custom strategy
    - Verify accept/reject behavior matches requirements: HTTP(S) accepted, non-HTTP(S)/empty/malformed rejected, `None` always accepted
    - File: `backend/tests/property/test_remote_agent_properties.py`
    - **Validates: Requirements 1.1, 7.1, 7.2**

  - [ ]* 1.4 Write unit tests for backward compatibility
    - Verify all existing scenario JSON files load without modification
    - Verify `AgentDefinition` without `endpoint` defaults to `None`
    - Verify Settings defaults for timeout fields
    - File: `backend/tests/unit/test_remote_agent.py`
    - _Requirements: 1.5, 9.1, 9.2_

- [ ] 2. Create TurnPayload and contract models
  - [ ] 2.1 Create `backend/app/orchestrator/remote_agent.py` with TurnPayload model
    - Define `TurnPayload` Pydantic model with all required fields: `schema_version`, `agent_role`, `agent_type`, `agent_name`, `turn_number`, `max_turns`, `current_offer`, `history`, `agent_config`, `negotiation_params`
    - Implement `build_turn_payload(agent_role, agent_config, state) -> TurnPayload` that constructs the payload from `NegotiationState`
    - Hidden context for the target agent injected into `agent_config`; other agents' hidden context excluded
    - `schema_version` hardcoded to `"1.0"`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 2.2 Write property test for TurnPayload completeness (Property 2)
    - **Property 2: TurnPayload Contains All Required Fields**
    - Generate random valid `NegotiationState` dicts, build payload, assert all required fields present and non-None
    - File: `backend/tests/property/test_remote_agent_properties.py`
    - **Validates: Requirements 2.2, 2.4**

  - [ ]* 2.3 Write property test for hidden context isolation (Property 3)
    - **Property 3: Hidden Context Isolation**
    - Generate states with multi-agent hidden context, build payloads per agent, assert no leakage of other agents' hidden context
    - File: `backend/tests/property/test_remote_agent_properties.py`
    - **Validates: Requirements 2.3**

  - [ ]* 2.4 Write property test for output serialization round-trip (Property 4)
    - **Property 4: Agent Output Serialization Round-Trip**
    - Generate random `NegotiatorOutput`, `RegulatorOutput`, `ObserverOutput` instances
    - Serialize via `model_dump_json()`, parse back via `model_validate_json()`, assert equality
    - File: `backend/tests/property/test_remote_agent_properties.py`
    - **Validates: Requirements 3.2, 3.3, 3.4**

- [ ] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement remote agent HTTP call in agent_node
  - [ ] 4.1 Add `_remote_agent_turn` async function to `backend/app/orchestrator/agent_node.py`
    - Use `httpx.AsyncClient` to POST `TurnPayload` JSON to the agent's endpoint
    - Include `User-Agent: JuntoAI-A2A/1.0` and `X-JuntoAI-Session-Id` headers
    - Enforce configurable timeout from `settings.REMOTE_AGENT_TIMEOUT_SECONDS`
    - Parse response into `NegotiatorOutput`, `RegulatorOutput`, or `ObserverOutput` based on `agent_type`
    - Report `tokens_used = 0` for remote agent turns
    - _Requirements: 4.2, 4.3, 4.5, 4.6, 4.7_

  - [ ] 4.2 Add retry and error handling logic to `_remote_agent_turn`
    - Retry once on timeout or 5xx, never on 4xx
    - On connection refused, DNS failure, non-JSON response, or Pydantic validation failure: log at WARNING + use `_fallback_output`
    - Log response body truncated to 500 chars
    - Include `[{agent_name} encountered a communication error]` in history entry content on fallback
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 3.5, 3.6_

  - [ ] 4.3 Branch `create_agent_node` to route local vs remote
    - In `_node`, check `agent_config.get("endpoint")`
    - If endpoint present: call `_remote_agent_turn` (async)
    - If endpoint absent: use existing local LLM path (unchanged)
    - Make `_node` async to support `await _remote_agent_turn`
    - Shared `_update_state` and `_advance_turn_order` for both paths — state deltas identical
    - _Requirements: 4.1, 4.4, 5.1, 5.2, 5.3_

  - [ ]* 4.4 Write property test for state delta equivalence (Property 5)
    - **Property 5: State Delta Equivalence for Local and Remote Agents**
    - Generate random parsed outputs + states, run through `_update_state`, compare deltas are identical regardless of origin
    - File: `backend/tests/property/test_remote_agent_properties.py`
    - **Validates: Requirements 4.4, 5.2, 5.3**

  - [ ]* 4.5 Write property test for zero token tracking (Property 6)
    - **Property 6: Zero Token Tracking for Remote Agents**
    - Generate random remote agent turns, assert `total_tokens_used` delta is 0
    - File: `backend/tests/property/test_remote_agent_properties.py`
    - **Validates: Requirements 4.5**

  - [ ]* 4.6 Write property test for invalid response fallback (Property 7)
    - **Property 7: Invalid Remote Response Triggers Fallback**
    - Generate random invalid responses (bad JSON, wrong schema, missing fields, non-200 status)
    - Verify `_fallback_output` produces valid state delta with well-formed history entry
    - File: `backend/tests/property/test_remote_agent_properties.py`
    - **Validates: Requirements 3.5, 3.6, 6.1, 6.2, 6.3**

  - [ ]* 4.7 Write unit tests for remote agent node
    - Test routing: `endpoint=None` → local path, `endpoint` set → remote path
    - Test headers: `User-Agent: JuntoAI-A2A/1.0` and `X-JuntoAI-Session-Id` present
    - Test retry logic: 5xx → retry → success; 5xx → retry → 5xx → fallback; 4xx → no retry → fallback; timeout → retry → success
    - Test fallback content includes `[{agent_name} encountered a communication error]`
    - Mock httpx calls with `unittest.mock.patch` or `respx`
    - File: `backend/tests/unit/test_remote_agent.py`
    - _Requirements: 4.1, 4.7, 6.1, 6.2, 6.4_

- [ ] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Add pre-negotiation health check and response extension
  - [ ] 6.1 Add health check function and response models to `backend/app/routers/negotiation.py`
    - Create `AgentHealthStatus` model with `role`, `status`, `endpoint` fields
    - Extend `StartNegotiationResponse` with optional `agent_health: list[AgentHealthStatus] | None = None`
    - Implement `_check_remote_agent_health(agents, timeout)` that GETs each remote endpoint with `User-Agent: JuntoAI-A2A/1.0`
    - 200 = healthy, non-200 = unhealthy, exception = unreachable
    - Enforce `REMOTE_AGENT_HEALTH_CHECK_TIMEOUT_SECONDS` per endpoint
    - _Requirements: 8.1, 8.2, 8.4, 8.5_

  - [ ] 6.2 Integrate health check into `start_negotiation` endpoint
    - Before creating session state, check if any agents have `endpoint` set
    - If remote agents exist, run `_check_remote_agent_health`
    - If any agent is unhealthy, return 422 with `{"detail": "Remote agent health check failed", "unhealthy_agents": [...]}`
    - If all healthy, include `agent_health` in `StartNegotiationResponse`
    - _Requirements: 8.1, 8.3, 8.5_

  - [ ]* 6.3 Write unit tests for health check
    - Test GET request sent to each remote endpoint
    - Test 200 = healthy, non-200 = unhealthy, timeout = unreachable
    - Test any unhealthy agent → 422 response, negotiation not started
    - Test scenarios with no remote agents skip health check entirely
    - Mock httpx calls
    - File: `backend/tests/unit/test_remote_agent.py`
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 7. Wire SSE event parity for remote agents
  - [ ] 7.1 Verify SSE event generation works for remote agent state deltas
    - Confirm `_snapshot_to_events` in `negotiation.py` produces identical `AgentThoughtEvent` and `AgentMessageEvent` for remote agent history entries
    - No code changes expected if state deltas are correctly structured — this task validates the integration
    - _Requirements: 5.4_

  - [ ]* 7.2 Write integration test for mixed local/remote negotiation
    - Scenario with 1 local + 1 remote negotiator + 1 local regulator
    - Mock remote endpoint to return valid `NegotiatorOutput` JSON
    - Run 2-3 turns through the graph, verify state consistency
    - Verify SSE events from remote turns are structurally identical to local turns
    - File: `backend/tests/integration/test_remote_agent_integration.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- All external HTTP calls are mocked in tests — no real network calls
- `create_agent_node` becomes async to support `httpx.AsyncClient` — verify LangGraph supports async node callables (it does via `astream`)
