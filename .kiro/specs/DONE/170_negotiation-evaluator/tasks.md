# Implementation Plan: Negotiation Evaluator

## Overview

Adds a deal closure protocol (confirmation round) and a post-negotiation evaluator agent to the JuntoAI negotiation engine. The confirmation round is a LangGraph node that does NOT increment `turn_count`. The evaluator runs OUTSIDE the graph as a standalone async generator, called from the streaming endpoint AFTER `run_negotiation()` completes and BEFORE the `negotiation_complete` SSE event.

## Tasks

- [x] 1. Extend state, models, and output schemas
  - [x] 1.1 Add `ConfirmationOutput`, `EvaluationInterview`, and `EvaluationReport` to `backend/app/orchestrator/outputs.py`
    - `ConfirmationOutput`: `accept` (bool), `final_statement` (str, min_length=1), `conditions` (list[str], default empty)
    - `EvaluationInterview`: `feels_served` (bool), `felt_respected` (bool), `is_win_win` (bool), `criticism` (str), `satisfaction_rating` (int, ge=1, le=10)
    - `EvaluationReport`: `participant_interviews` (list[dict[str, Any]]), `dimensions` (dict[str, int]), `overall_score` (int, ge=1, le=10), `verdict` (str), `deal_status` (str)
    - _Requirements: 1.5, 3.1, 6.2, 7.1, 7.4_

  - [x] 1.2 Add `closure_status` and `confirmation_pending` to `NegotiationState` TypedDict in `backend/app/orchestrator/state.py`
    - `closure_status: str` (default `""`)
    - `confirmation_pending: list[str]` (default `[]`)
    - Update `create_initial_state()` to initialize both fields
    - _Requirements: 4.1, 4.2_

  - [x] 1.3 Extend `NegotiationStateModel` in `backend/app/models/negotiation.py`
    - Add `"Confirming"` to the `deal_status` Literal type
    - Add `closure_status: str = Field(default="")` and `confirmation_pending: list[str] = Field(default_factory=list)`
    - _Requirements: 4.3, 4.4_

  - [x] 1.4 Add `EvaluatorConfig` model and `evaluator_config` field to `ArenaScenario` in `backend/app/scenarios/models.py`
    - `EvaluatorConfig`: `model_id` (str, min_length=1), `fallback_model_id` (str | None), `enabled` (bool, default True)
    - `ArenaScenario.evaluator_config: EvaluatorConfig | None = Field(default=None)`
    - _Requirements: 9.1_

  - [x] 1.5 Add `EvaluationInterviewEvent` and `EvaluationCompleteEvent` to `backend/app/models/events.py`
    - `EvaluationInterviewEvent`: `event_type` Literal `"evaluation_interview"`, `agent_name`, `turn_number`, `status` Literal `"interviewing" | "complete"`, optional `satisfaction_rating`, `felt_respected`, `is_win_win`
    - `EvaluationCompleteEvent`: `event_type` Literal `"evaluation_complete"`, `dimensions` (dict[str, int]), `overall_score` (int), `verdict` (str), `participant_interviews` (list[dict[str, Any]]), `deal_status` (str)
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 1.6 Update converters in `backend/app/orchestrator/converters.py`
    - Map `closure_status` and `confirmation_pending` in both `to_pydantic()` and `from_pydantic()`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x]* 1.7 Write property test for model round-trip serialization (Property 5)
    - **Property 5: Output model serialization round-trip**
    - Test `ConfirmationOutput`, `EvaluationInterview`, `EvaluationReport`, `NegotiationStateModel` (with new fields), `ArenaScenario` (with `evaluator_config`)
    - File: `backend/tests/property/test_evaluator_model_properties.py`
    - **Validates: Requirements 1.5, 3.1, 4.3, 6.2, 7.1, 7.4, 9.1**

- [x] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement confirmation node and dispatcher modifications
  - [x] 3.1 Create `backend/app/orchestrator/confirmation_node.py`
    - Implement `confirmation_node(state: NegotiationState) -> dict[str, Any]`
    - Pop first role from `confirmation_pending`, build confirmation prompt with converged terms (`current_offer`, `turn_count`, recent `public_message` entries)
    - Call LLM via `model_router`, parse response as `ConfirmationOutput` with retry + fallback (retry once, then treat as rejection)
    - Append history entry with `agent_type = "confirmation"` and `turn_number` equal to current `turn_count` (NO increment)
    - Return `{"history": [entry], "confirmation_pending": remaining}`
    - _Requirements: 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 12.4_

  - [x] 3.2 Modify `_dispatcher()` in `backend/app/orchestrator/graph.py`
    - When `deal_status == "Confirming"` and `confirmation_pending` is empty, call `_resolve_confirmation(state)` to determine outcome
    - When `_check_agreement()` returns True and `deal_status == "Negotiating"`, set `deal_status = "Confirming"` and populate `confirmation_pending` with all negotiator roles — do NOT set `"Agreed"` directly
    - Implement `_resolve_confirmation()`: all accept + no conditions → Agreed/Confirmed; any reject → Negotiating/Rejected; all accept + conditions → Negotiating/Conditional
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.3 Modify `_route_dispatcher()` in `backend/app/orchestrator/graph.py`
    - When `deal_status == "Confirming"`, return `"confirmation"` node name
    - _Requirements: 1.1, 4.4_

  - [x] 3.4 Modify `build_graph()` in `backend/app/orchestrator/graph.py`
    - Add `confirmation` node to the `StateGraph`
    - Add `confirmation → dispatcher` edge
    - Add `"confirmation"` to the `route_map` for conditional edges
    - _Requirements: 1.1_

  - [x]* 3.5 Write property test: convergence triggers Confirming, never Agreed directly (Property 1)
    - **Property 1: Convergence triggers Confirming, never Agreed directly**
    - Generate states with converged negotiator prices within threshold, verify dispatcher returns `deal_status = "Confirming"` not `"Agreed"`
    - File: `backend/tests/property/test_confirmation_properties.py`
    - **Validates: Requirements 1.1, 1.2**

  - [x]* 3.6 Write property test: confirmation_pending contains exactly negotiator roles (Property 2)
    - **Property 2: Confirmation pending contains exactly negotiator roles**
    - Generate scenario configs with mixed agent types (2-5 agents), verify `confirmation_pending` contains only negotiator roles
    - File: `backend/tests/property/test_confirmation_properties.py`
    - **Validates: Requirements 1.3, 12.1**

  - [x]* 3.7 Write property test: confirmation resolution is deterministic and correct (Property 3)
    - **Property 3: Confirmation resolution is deterministic and correct**
    - Generate all combinations of accept/reject and conditions, verify the three exhaustive/mutually-exclusive outcomes
    - File: `backend/tests/property/test_confirmation_properties.py`
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x]* 3.8 Write property test: confirmation node appends correct history entries (Property 4)
    - **Property 4: Confirmation node appends correct history entries**
    - Verify history entry has `agent_type == "confirmation"`, correct `role`, and `turn_number` equal to current `turn_count`
    - File: `backend/tests/property/test_confirmation_properties.py`
    - **Validates: Requirements 2.4, 3.3**

  - [x]* 3.9 Write property test: confirmation prompt contains converged terms (Property 9)
    - **Property 9: Confirmation prompt contains converged terms**
    - Verify the confirmation prompt includes `current_offer`, `turn_count`, and at least one `public_message` from history
    - File: `backend/tests/property/test_confirmation_properties.py`
    - **Validates: Requirements 1.4**

  - [x]* 3.10 Write unit tests for confirmation node
    - Test parse retry + fallback (invalid JSON → retry → fallback rejection)
    - Test confirmation history entry shape and `agent_type = "confirmation"`
    - Test `_snapshot_to_events` emits `AgentMessageEvent` for confirmation `final_statement` entries
    - File: `backend/tests/unit/orchestrator/test_confirmation_node.py`
    - _Requirements: 2.6, 3.2, 3.3_

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement evaluator agent (standalone, outside graph)
  - [x] 5.1 Create `backend/app/orchestrator/evaluator_prompts.py`
    - `build_interview_system_prompt(agent_config)` — instructs participant LLM to answer honestly: "If you are unhappy, say so. If you feel you lost, say so."
    - `build_interview_user_prompt(agent_config, history, terminal_state)` — provides full history, persona, goals, final terms, and the 5 interview questions from Req 6.1
    - `build_scoring_system_prompt()` — anti-rubber-stamp prompt: default 5, cap at 6 if dissatisfaction, penalize simple splits by 2 points, reserve 9-10 for genuine enthusiasm + novel value
    - `build_scoring_user_prompt(interviews, history, terminal_state, scenario_config)` — all interviews + history + deal metrics + per-agent budget data for cross-referencing
    - _Requirements: 5.4, 5.5, 6.1, 7.2, 7.3, 11.1, 11.2, 11.3_

  - [x] 5.2 Create `backend/app/orchestrator/evaluator.py`
    - Implement `run_evaluation(terminal_state, scenario_config)` as an async generator
    - `_resolve_evaluator_model(scenario_config)` — use `evaluator_config.model_id` if present, else first negotiator's `model_id`
    - `_get_negotiator_configs(scenario_config)` — return agent configs where `type == "negotiator"`
    - `_interview_participant(model, agent_config, history, terminal_state)` — single LLM call, parse as `EvaluationInterview` with retry + fallback (satisfaction_rating=5)
    - `_score_negotiation(model, interviews, history, terminal_state, scenario_config)` — separate LLM call, parse as `EvaluationReport` with retry + fallback (all 5s)
    - Yield `EvaluationInterviewEvent` (interviewing) → interview → `EvaluationInterviewEvent` (complete) per negotiator, then `EvaluationCompleteEvent`
    - When `evaluator_config.enabled == False`, return immediately (yield nothing)
    - The evaluator does NOT modify NegotiationState, does NOT increment turn_count, is NOT a LangGraph node
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.2, 6.3, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 9.2, 9.3, 9.4, 11.1, 11.2, 11.3, 12.2, 12.3, 12.4_

  - [x]* 5.3 Write property test: evaluator interviews exactly N negotiators (Property 6)
    - **Property 6: Evaluator interviews exactly N negotiators**
    - Mock LLM, generate scenario configs with 2-5 negotiators, verify exactly N interview pairs + 1 complete event
    - File: `backend/tests/property/test_evaluator_properties.py`
    - **Validates: Requirements 5.2, 12.2**

  - [x]* 5.4 Write property test: interview isolation — no cross-contamination (Property 7)
    - **Property 7: Interview isolation — no cross-contamination**
    - Generate interview results for multiple participants, verify each interview prompt contains no other participant's response fields
    - File: `backend/tests/property/test_evaluator_properties.py`
    - **Validates: Requirements 5.3**

  - [x]* 5.5 Write property test: interview prompt contains required context (Property 8)
    - **Property 8: Interview prompt contains required context**
    - Generate terminal states with varying history lengths, verify prompt contains public_message, persona_prompt, goals, current_offer
    - File: `backend/tests/property/test_evaluator_properties.py`
    - **Validates: Requirements 5.5**

  - [x]* 5.6 Write property test: default evaluator model resolution (Property 10)
    - **Property 10: Default evaluator model resolution**
    - Generate scenario configs with and without `evaluator_config`, verify fallback to first negotiator's `model_id`
    - File: `backend/tests/property/test_evaluator_properties.py`
    - **Validates: Requirements 9.2**

  - [x]* 5.7 Write property test: scoring prompt includes objective deal metrics (Property 11)
    - **Property 11: Scoring prompt includes objective deal metrics**
    - Generate interviews and terminal states with known budgets, verify scoring prompt contains satisfaction_rating values and price-vs-budget data
    - File: `backend/tests/property/test_evaluator_properties.py`
    - **Validates: Requirements 11.3**

  - [x]* 5.8 Write unit tests for evaluator and evaluator prompts
    - Test interview parse retry + fallback (invalid JSON → retry → neutral fallback with satisfaction_rating=5)
    - Test scoring parse retry + fallback (invalid JSON → retry → all 5s report)
    - Test evaluator disabled (`enabled=False`) yields no events
    - Test prompt content: anti-rubber-stamp instructions, honest-answer instructions, multi-party fairness mention for 3+ negotiators
    - Files: `backend/tests/unit/orchestrator/test_evaluator.py`, `backend/tests/unit/orchestrator/test_evaluator_prompts.py`
    - _Requirements: 5.4, 6.3, 7.3, 9.3, 11.1, 11.2, 12.3_

- [x] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Modify streaming endpoint and snapshot-to-events
  - [x] 7.1 Update `_snapshot_to_events()` in `backend/app/routers/negotiation.py`
    - Handle `deal_status == "Confirming"` — do NOT emit `NegotiationCompleteEvent` for Confirming state
    - Handle confirmation history entries (`agent_type == "confirmation"`) — emit `AgentMessageEvent` with the `final_statement` as `public_message`
    - _Requirements: 2.6_

  - [x] 7.2 Update `event_stream()` generator in `backend/app/routers/negotiation.py`
    - After `run_negotiation()` loop completes, hold back the `NegotiationCompleteEvent` instead of yielding it immediately
    - Resolve evaluator config: check `scenario_config` for `evaluator_config`, determine if evaluation is enabled
    - Call `run_evaluation(terminal_state, scenario_config)` wrapped in try/except — any failure logs and skips evaluation, `negotiation_complete` is always emitted
    - Stream `EvaluationInterviewEvent` and `EvaluationCompleteEvent` via event buffer
    - Attach evaluation report to `final_summary["evaluation"]` on the held-back `NegotiationCompleteEvent`
    - Emit the `NegotiationCompleteEvent` AFTER evaluation events
    - Import new event types and `run_evaluation`
    - _Requirements: 5.1, 8.1, 8.2, 8.3, 8.4, 9.3_

  - [x]* 7.3 Write unit tests for SSE event models
    - Test `EvaluationInterviewEvent` shape for both `"interviewing"` and `"complete"` statuses
    - Test `EvaluationCompleteEvent` shape with dimensions, overall_score, verdict
    - File: `backend/tests/unit/models/test_evaluation_events.py`
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Frontend: OutcomeReceipt evaluation display
  - [x] 9.1 Extend `OutcomeReceipt` component in `frontend/components/glassbox/OutcomeReceipt.tsx`
    - Display overall `Evaluation_Score` as prominent "X / 10" with color coding: 1-3 `text-red-500`, 4-6 `text-amber-500`, 7-8 `text-green-500`, 9-10 `text-emerald-400`
    - Display four `Score_Dimensions` (fairness, mutual_respect, value_creation, satisfaction) as progress bars or numeric indicators
    - Display `verdict` string as 2-3 sentence summary below dimensions
    - Display each participant's `satisfaction_rating` and one-line interview summary in participant summaries section
    - When no evaluation data is present (evaluator disabled or failed), render existing layout without evaluation section
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x]* 9.2 Write frontend tests for OutcomeReceipt evaluation display
    - Test render with evaluation data: score display, color coding, dimensions, verdict
    - Test render without evaluation data: graceful fallback to existing layout
    - Test score color mapping: 1-3=red, 4-6=amber, 7-8=green, 9-10=bright green
    - File: `frontend/__tests__/components/OutcomeReceiptEvaluation.test.tsx`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 10. Integration tests
  - [x]* 10.1 Write integration test: full confirmation flow
    - Run `build_graph()` with mocked LLM that converges, verify Confirming → confirmation node → Agreed/Confirmed flow
    - Verify confirmation rejection resumes negotiation (deal_status back to Negotiating)
    - File: `backend/tests/integration/orchestrator/test_confirmation_integration.py`
    - _Requirements: 1.1, 2.1, 2.2_

  - [x]* 10.2 Write integration test: evaluation event ordering and graceful degradation
    - Full stream test verifying `evaluation_interview` → `evaluation_complete` → `negotiation_complete` ordering
    - Mock evaluator to raise exception, verify `negotiation_complete` is still emitted
    - File: `backend/tests/integration/orchestrator/test_evaluator_integration.py`
    - _Requirements: 8.4_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (11 properties total)
- The evaluator is NOT a LangGraph node — it runs as a standalone async generator called from the streaming endpoint
- The confirmation round does NOT increment `turn_count`
