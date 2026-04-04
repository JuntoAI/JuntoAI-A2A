# Requirements Document

## Introduction

Per-agent-call telemetry collection for the JuntoAI A2A negotiation engine. Currently, the orchestrator tracks only aggregate `total_tokens_used` across all agents in a session. This spec adds per-call telemetry — recording the model_id, latency, token breakdown (input/output), and error status for every LLM invocation during a negotiation. The telemetry data is stored as an `agent_calls` array on the session document, enabling the admin dashboard (Spec 150) to compute per-model performance metrics (average latency, average token usage, error rates) without additional data sources.

This is a lightweight instrumentation spec — it modifies the agent node to capture timing and token data that already flows through the system but is currently discarded after aggregation.

## Glossary

- **Agent_Call_Record**: A structured telemetry record captured for each LLM invocation during a negotiation. Contains `agent_role` (str), `agent_type` (str), `model_id` (str), `latency_ms` (int — wall-clock milliseconds for the LLM call), `input_tokens` (int), `output_tokens` (int), `error` (bool — true if the call required fallback), `turn_number` (int), and `timestamp` (str — UTC ISO 8601).
- **Agent_Calls_Array**: The `agent_calls` field on the NegotiationState TypedDict and session documents, an append-only list of Agent_Call_Record dicts accumulated across all agent nodes during a negotiation.
- **Retry_Call**: When an agent's first LLM response fails to parse and a retry is attempted, both the original call and the retry call are recorded as separate Agent_Call_Records. The retry call has the same `turn_number` and `agent_role` but its own latency and token counts.

## Requirements

### Requirement 1: Agent Call Record Schema

**User Story:** As a developer, I want a well-defined schema for per-call telemetry, so that the data is consistent and queryable.

#### Acceptance Criteria

1. THE orchestrator SHALL define an `AgentCallRecord` Pydantic V2 model in `backend/app/orchestrator/outputs.py` with fields: `agent_role` (str), `agent_type` (str, one of "negotiator", "regulator", "observer"), `model_id` (str), `latency_ms` (int, ge=0), `input_tokens` (int, ge=0), `output_tokens` (int, ge=0), `error` (bool, default False), `turn_number` (int, ge=0), and `timestamp` (str).
2. FOR ALL valid `AgentCallRecord` instances, serializing to JSON and deserializing back SHALL produce an equivalent object (round-trip property).

### Requirement 2: NegotiationState Extension

**User Story:** As a developer, I want the negotiation state to accumulate per-call telemetry, so that it is available when the session completes.

#### Acceptance Criteria

1. THE `NegotiationState` TypedDict in `backend/app/orchestrator/state.py` SHALL include an `agent_calls` field of type `Annotated[list[dict[str, Any]], add]` (append-on-merge, same pattern as `history`).
2. THE `create_initial_state()` function SHALL initialize `agent_calls` to an empty list.
3. THE `NegotiationStateModel` Pydantic model in `backend/app/models/negotiation.py` SHALL include an `agent_calls` field of type `list[dict[str, Any]]` with `default_factory=list`.
4. THE converters in `backend/app/orchestrator/converters.py` SHALL map `agent_calls` in both `to_pydantic()` and `from_pydantic()`.

### Requirement 3: Telemetry Capture in Agent Node

**User Story:** As a developer, I want each LLM call in the agent node to be instrumented with timing and token data, so that per-model metrics can be computed.

#### Acceptance Criteria

1. WHEN the agent node invokes the LLM via `model.invoke(messages)`, THE agent node SHALL record the wall-clock time of the call in milliseconds as `latency_ms`.
2. WHEN the LLM response includes `usage_metadata`, THE agent node SHALL extract `input_tokens` and `output_tokens` from the metadata. If `usage_metadata` is absent, both SHALL default to 0.
3. WHEN the first LLM parse fails and a retry is attempted, THE agent node SHALL record a separate `AgentCallRecord` for the retry call with its own `latency_ms`, `input_tokens`, and `output_tokens`.
4. WHEN the agent node uses a fallback output (both first call and retry failed), THE agent node SHALL set `error=True` on the retry call's `AgentCallRecord`.
5. THE agent node SHALL include all `AgentCallRecord` dicts in the state delta as `{"agent_calls": [record1, record2, ...]}` so LangGraph appends them to the accumulated list.
6. THE agent node SHALL set `timestamp` to the UTC ISO 8601 string at the time of the LLM call.
7. THE agent node SHALL set `model_id` to the effective model ID used for the call (after applying `model_overrides`).

### Requirement 4: Telemetry Persistence

**User Story:** As a developer, I want the telemetry data to be persisted with the session document, so that it survives beyond the in-memory graph execution.

#### Acceptance Criteria

1. WHEN the negotiation session completes and the session document is updated, THE `agent_calls` array SHALL be included in the persisted session data.
2. THE `agent_calls` array SHALL be available in the raw session document returned by `get_session_doc()`.
3. FOR sessions that predate this spec (no `agent_calls` field), THE system SHALL treat the missing field as an empty list for backward compatibility.

### Requirement 5: Telemetry Does Not Affect Negotiation Logic

**User Story:** As a developer, I want telemetry collection to be purely observational, so that it cannot break or alter negotiation behavior.

#### Acceptance Criteria

1. THE agent node SHALL capture telemetry in a try/except block — any failure in telemetry recording SHALL be logged at WARNING level and SHALL NOT prevent the agent node from returning its state delta.
2. THE telemetry capture SHALL NOT modify any existing state fields (`history`, `turn_count`, `deal_status`, `current_offer`, `agent_states`, etc.).
3. THE telemetry capture SHALL NOT add latency beyond the wall-clock measurement overhead (no additional LLM calls, no network requests).
