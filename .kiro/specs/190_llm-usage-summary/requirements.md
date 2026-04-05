# Requirements Document

## Introduction

LLM Usage Summary for the JuntoAI A2A outcome receipt (Screen 4). After a negotiation completes, users currently see deal terms, participant summaries, and basic performance metrics (elapsed time, total AI tokens). This spec adds a dedicated "Behind the Curtain" stats card that surfaces per-persona token breakdowns, per-model usage, average latency, and efficiency metrics — giving users (and investors) transparency into how the AI agents actually consumed LLM resources during the negotiation.

This spec is a pure consumer of the `agent_calls` telemetry array produced by Spec 145 (per-model-telemetry). It adds no new data collection — only aggregation logic on the backend and a new UI section on the frontend.

## Glossary

- **Agent_Calls_Array**: The `agent_calls` field on the session document, an append-only list of `AgentCallRecord` dicts accumulated during a negotiation (produced by Spec 145). Each record contains `agent_role`, `agent_type`, `model_id`, `latency_ms`, `input_tokens`, `output_tokens`, `error`, `turn_number`, and `timestamp`.
- **Usage_Summary**: A structured JSON object computed from the Agent_Calls_Array that contains per-persona stats, per-model stats, and session-wide aggregate metrics. Included in the `final_summary` of the `NegotiationCompleteEvent`.
- **Persona**: An agent role in the negotiation (e.g. "Buyer", "Seller", "EU Regulator"). Each persona maps to exactly one `agent_role` in the telemetry data.
- **Outcome_Receipt**: Screen 4 of the core user flow — the overlay shown after a negotiation reaches a terminal state (Agreed, Blocked, or Failed). Displays deal terms, ROI metrics, and CTAs.
- **Tokens_Per_Message**: The average total tokens (input + output) consumed per non-error `AgentCallRecord` for a given persona or model.
- **Thinking_Time**: The `latency_ms` value from an `AgentCallRecord`, representing wall-clock milliseconds for a single LLM invocation.

## Requirements

### Requirement 1: Usage Summary Aggregation Service

**User Story:** As a developer, I want a pure function that computes LLM usage statistics from the agent_calls array, so that the aggregation logic is testable and reusable.

#### Acceptance Criteria

1. THE Usage_Summary_Aggregator SHALL accept a list of AgentCallRecord dicts and return a Usage_Summary dict.
2. THE Usage_Summary_Aggregator SHALL compute per-persona statistics grouped by `agent_role`: total input tokens, total output tokens, total tokens (input + output), number of LLM calls, number of error calls, average latency in milliseconds (rounded to the nearest integer), and tokens per message (total tokens divided by non-error call count, rounded to the nearest integer).
3. THE Usage_Summary_Aggregator SHALL compute per-model statistics grouped by `model_id`: total input tokens, total output tokens, total tokens, number of LLM calls, number of error calls, average latency in milliseconds (rounded to the nearest integer), and tokens per message (total tokens divided by non-error call count, rounded to the nearest integer).
4. THE Usage_Summary_Aggregator SHALL compute session-wide totals: total input tokens, total output tokens, total tokens, total LLM calls, total error calls, average latency across all calls (rounded to the nearest integer), and total negotiation duration derived from the earliest and latest `timestamp` values in the array.
5. WHEN the agent_calls array is empty, THE Usage_Summary_Aggregator SHALL return a Usage_Summary with all numeric fields set to zero and empty lists for per-persona and per-model breakdowns.
6. WHEN a persona has zero non-error calls, THE Usage_Summary_Aggregator SHALL set tokens_per_message to zero for that persona instead of dividing by zero.
7. THE Usage_Summary_Aggregator SHALL be a pure function with no side effects, located in a dedicated module `backend/app/orchestrator/usage_summary.py`.

### Requirement 2: Usage Summary Schema

**User Story:** As a developer, I want a well-defined Pydantic schema for the usage summary, so that the data contract between backend and frontend is explicit and validated.

#### Acceptance Criteria

1. THE system SHALL define a `PersonaUsageStats` Pydantic V2 model with fields: `agent_role` (str), `agent_type` (str), `model_id` (str), `total_input_tokens` (int, ge=0), `total_output_tokens` (int, ge=0), `total_tokens` (int, ge=0), `call_count` (int, ge=0), `error_count` (int, ge=0), `avg_latency_ms` (int, ge=0), and `tokens_per_message` (int, ge=0).
2. THE system SHALL define a `ModelUsageStats` Pydantic V2 model with fields: `model_id` (str), `total_input_tokens` (int, ge=0), `total_output_tokens` (int, ge=0), `total_tokens` (int, ge=0), `call_count` (int, ge=0), `error_count` (int, ge=0), `avg_latency_ms` (int, ge=0), and `tokens_per_message` (int, ge=0).
3. THE system SHALL define a `UsageSummary` Pydantic V2 model with fields: `per_persona` (list of PersonaUsageStats), `per_model` (list of ModelUsageStats), `total_input_tokens` (int, ge=0), `total_output_tokens` (int, ge=0), `total_tokens` (int, ge=0), `total_calls` (int, ge=0), `total_errors` (int, ge=0), `avg_latency_ms` (int, ge=0), and `negotiation_duration_ms` (int, ge=0).
4. FOR ALL valid UsageSummary instances, serializing to JSON via `.model_dump_json()` and deserializing back via `UsageSummary.model_validate_json()` SHALL produce an equivalent object (round-trip property).

### Requirement 3: Integration into NegotiationCompleteEvent

**User Story:** As a user, I want the LLM usage summary included in the outcome receipt data, so that I can see it immediately when the negotiation ends.

#### Acceptance Criteria

1. WHEN a negotiation reaches a terminal state (Agreed, Blocked, or Failed), THE `_snapshot_to_events` function SHALL compute the Usage_Summary from the session's `agent_calls` array and include it as a `usage_summary` key in the `final_summary` dict of the `NegotiationCompleteEvent`.
2. WHEN the session has no `agent_calls` data (pre-Spec-145 sessions or empty array), THE system SHALL include a Usage_Summary with all numeric fields set to zero.
3. THE Usage_Summary computation SHALL NOT add measurable latency to the event emission path (the aggregation operates on in-memory data only, no additional database queries or LLM calls).

### Requirement 4: Frontend Usage Summary Card

**User Story:** As a user, I want to see a "Behind the Curtain" stats card on the outcome receipt, so that I understand how each AI persona and LLM model consumed resources during the negotiation.

#### Acceptance Criteria

1. WHEN the `final_summary` contains a `usage_summary` object with non-zero `total_calls`, THE Outcome_Receipt component SHALL render a collapsible "LLM Usage" section with `data-testid="usage-summary-section"`.
2. THE usage summary section SHALL display a per-persona breakdown table showing each persona's name, model ID, total tokens, call count, average latency (formatted as milliseconds with "ms" suffix), and tokens per message.
3. THE usage summary section SHALL display a per-model breakdown table showing each model's ID, total tokens, call count, average latency, and tokens per message.
4. THE usage summary section SHALL display session-wide totals: total tokens, total LLM calls, total errors (only if greater than zero), average latency, and negotiation duration (formatted as seconds with one decimal place).
5. WHEN the `usage_summary` is absent or has `total_calls` equal to zero, THE Outcome_Receipt component SHALL NOT render the usage summary section.
6. THE usage summary section SHALL be collapsed by default and expandable via a toggle button with `data-testid="usage-summary-toggle"`, so that the primary deal outcome remains the visual focus.
7. THE usage summary section SHALL render correctly on viewports from 320px to 1920px wide, using responsive layout (stacked on mobile, side-by-side tables on desktop at 1024px and above).

### Requirement 5: Token Efficiency Insights

**User Story:** As a user, I want to see which personas are token-efficient and which are verbose, so that I can understand the relative cost of each agent.

#### Acceptance Criteria

1. THE per-persona breakdown SHALL sort personas by `total_tokens` in descending order, so the most token-heavy persona appears first.
2. THE per-persona breakdown SHALL display an input-to-output token ratio for each persona (formatted as "input:output" e.g. "3.2:1"), providing insight into how much context each persona consumed versus how much it produced.
3. WHEN there are two or more personas, THE usage summary section SHALL highlight the persona with the highest tokens_per_message with a visual indicator (a colored badge or label with `data-testid="most-verbose-badge"`).

### Requirement 6: Backward Compatibility

**User Story:** As a developer, I want the usage summary feature to degrade gracefully for sessions that predate Spec 145, so that existing sessions continue to work.

#### Acceptance Criteria

1. WHEN the session document has no `agent_calls` field, THE system SHALL treat the missing field as an empty list and produce a zero-valued Usage_Summary.
2. THE existing `ai_tokens_used` field in `final_summary` SHALL continue to be populated from `total_tokens_used` as before — the Usage_Summary is additive, not a replacement.
3. THE Outcome_Receipt component SHALL continue to render correctly when `usage_summary` is absent from `final_summary`.
