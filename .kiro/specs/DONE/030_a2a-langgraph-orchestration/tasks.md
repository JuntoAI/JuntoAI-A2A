# Tasks

## Task 1: Module Skeleton + Exceptions + Output Models

Set up the orchestrator package structure, exception classes, and Pydantic output models.

- [x] 1.1 Create `backend/app/orchestrator/__init__.py` with empty re-exports placeholder
- [x] 1.2 Create `backend/app/orchestrator/exceptions.py` with `ModelNotAvailableError(model_id, message)`, `ModelTimeoutError(model_id, elapsed_seconds)`, `AgentOutputParseError(agent_name, raw_response)`
- [x] 1.3 Create `backend/app/orchestrator/outputs.py` with `NegotiatorOutput`, `RegulatorOutput`, `ObserverOutput` Pydantic V2 models per design
- [x] 1.4 Write unit tests for output models: construction, field validation, JSON serialization
- [x] 1.5 *Property test P1: Output Model Round-Trip* — hypothesis test that for all valid NegotiatorOutput, RegulatorOutput, ObserverOutput instances, `Model.model_validate_json(instance.model_dump_json())` produces an equivalent object
- [x] 1.6 *Property test P13: Output Parsing by Type* — hypothesis test that `_parse_output()` with agent_type="negotiator" validates against NegotiatorOutput, "regulator" against RegulatorOutput, "observer" against ObserverOutput, and mismatched types raise AgentOutputParseError

## Task 2: NegotiationState TypedDict + State Converters

Implement the LangGraph-compatible state schema and Pydantic conversion functions.

- [x] 2.1 Create `backend/app/orchestrator/state.py` with `NegotiationState` TypedDict including all fields: session_id, scenario_id, turn_count, max_turns, current_speaker, deal_status, current_offer, history (Annotated[list, add]), hidden_context, warning_count, agreement_threshold, scenario_config, turn_order, turn_order_index, agent_states, active_toggles
- [x] 2.2 Implement `create_initial_state(session_id, scenario_config, active_toggles, hidden_context)` factory function that builds turn_order from config or derives it, populates agent_states from agents array
- [x] 2.3 Create `backend/app/orchestrator/converters.py` with `to_pydantic(state)` and `from_pydantic(model)` functions mapping all fields including turn_order, turn_order_index, agent_states
- [x] 2.4 Write unit tests for `create_initial_state()` with various scenario configs (2-agent, 3-agent, 4-agent, with/without explicit turn_order)
- [x] 2.5 Write unit tests for `to_pydantic()` and `from_pydantic()` with edge cases (empty agent_states, empty history, missing optional fields)
- [x] 2.6 *Property test P2: State Conversion Round-Trip* — hypothesis test that for all valid NegotiationState dicts, `from_pydantic(to_pydantic(state))` produces an equivalent state. turn_order, turn_order_index, and agent_states must survive.

## Task 3: Checkpoint — Verify State Layer

Run all tests from Tasks 1-2 and verify green.

- [x] 3.1 Run `pytest backend/tests/unit/orchestrator/` and confirm all tests pass
- [x] 3.2 Verify output models and state TypedDict are importable from `backend.app.orchestrator`

## Task 4: Model Router

Implement the configuration-driven Vertex AI model router.

- [x] 4.1 Create `backend/app/orchestrator/model_router.py` with `get_model(model_id, fallback_model_id, project, location)` function
- [x] 4.2 Implement model family detection: prefix before first `-` maps to ChatVertexAI (gemini) or ChatAnthropicVertex (claude)
- [x] 4.3 Implement fallback logic: on primary failure, attempt fallback_model_id before raising
- [x] 4.4 Implement timeout configuration from `VERTEX_AI_REQUEST_TIMEOUT_SECONDS` env var (default 60s) and 30s slow-request warning logging
- [x] 4.5 Write unit tests for model router with mocked LangChain classes: valid model_ids, unknown model_id raises ModelNotAvailableError, fallback behavior, timeout behavior
- [x] 4.6 *Property test P14: Model Router Returns or Raises* — hypothesis test that get_model(model_id) either returns a BaseChatModel instance or raises ModelNotAvailableError, never returns None

## Task 5: Agent Node Factory

Implement the generic agent node factory with prompt construction, output parsing, state update, and turn advancement.

- [x] 5.1 Create `backend/app/orchestrator/agent_node.py` with `create_agent_node(agent_role)` factory function
- [x] 5.2 Implement `_build_prompt(agent_config, state)` — constructs system message from persona_prompt, goals, budget, hidden_context[role], and output schema for agent type
- [x] 5.3 Implement `_parse_output(response_text, agent_type)` — parses JSON into NegotiatorOutput/RegulatorOutput/ObserverOutput based on type, retry-once on failure
- [x] 5.4 Implement `_update_state(parsed_output, agent_type, role, state)` — produces state delta: negotiator updates current_offer + agent_states[role], regulator updates warning_count + agent_states[role], observer appends history only
- [x] 5.5 Implement `_advance_turn_order(state)` — increments turn_order_index, wraps to 0 + increments turn_count, sets current_speaker
- [x] 5.6 Write unit tests for `_build_prompt()` with hidden context present/absent, various agent types
- [x] 5.7 Write unit tests for `_parse_output()` with valid JSON, invalid JSON, retry behavior
- [x] 5.8 Write unit tests for `_update_state()` for each agent type (negotiator, regulator, observer)
- [x] 5.9 Write unit tests for `_advance_turn_order()` with various turn_order lengths and wrap-around
- [x] 5.10 Write integration test for full agent node execution with mocked LLM client
- [x] 5.11 *Property test P3: Turn Order Advancement* — hypothesis test that after any agent node executes, turn_order_index increments by 1, wraps correctly, and current_speaker == turn_order[turn_order_index]
- [x] 5.12 *Property test P4: Negotiator State Update* — hypothesis test that after a negotiator node, current_offer == proposed_price AND agent_states[role]["last_proposed_price"] == proposed_price
- [x] 5.13 *Property test P5: Regulator State Update* — hypothesis test that after regulator returns WARNING, warning_count increments; after 3 cumulative warnings, deal_status == "Blocked"
- [x] 5.14 *Property test P6: Observer Read-Only* — hypothesis test that after observer executes, current_offer, deal_status, warning_count are unchanged
- [x] 5.15 *Property test P7: Hidden Context Injection* — hypothesis test that when hidden_context[role] exists, system prompt contains it; when absent, prompt does not contain hidden context
- [x] 5.16 *Property test P15: Turn Number Consistency* — hypothesis test that all history entries in the same cycle share the same turn_number, and turn_count only increments on wrap

## Task 6: Checkpoint — Verify Agent Layer

Run all tests from Tasks 1-5 and verify green.

- [x] 6.1 Run `pytest backend/tests/unit/orchestrator/` and confirm all tests pass
- [x] 6.2 Verify agent node factory produces callable nodes for negotiator, regulator, and observer types

## Task 7: Graph Construction + Dispatcher + Agreement Detection

Implement dynamic graph building, the dispatcher routing node, agreement detection, and the async execution generator.

- [x] 7.1 Implement `build_graph(scenario_config)` in `backend/app/orchestrator/graph.py` — reads agents array, creates nodes via create_agent_node(), adds dispatcher, sets entry point, adds edges
- [x] 7.2 Implement `_dispatcher(state)` — checks terminal status, max_turns, agreement, routes to current_speaker or END
- [x] 7.3 Implement `_check_agreement(state)` — collects negotiator prices from agent_states, checks convergence within threshold, skips for single negotiator
- [x] 7.4 Implement `run_negotiation(initial_state, scenario_config)` async generator — builds graph, streams state snapshots via graph.astream()
- [x] 7.5 Write unit tests for `_check_agreement()` with 2 negotiators converged, 2 diverged, single negotiator, zero prices
- [x] 7.6 Write unit tests for `_dispatcher()` routing: terminal statuses route to END, max_turns triggers Failed, normal routing to current_speaker
- [x] 7.7 Write unit tests for `build_graph()` verifying correct node count (unique roles + dispatcher), no hardcoded role names
- [x] 7.8 Write integration test for `run_negotiation()` with mocked LLM: verify full cycle execution, state snapshots yielded, terminal state reached
- [x] 7.9 *Property test P8: Agreement Detection* — hypothesis test that convergence within threshold returns True, divergence returns False, single negotiator returns False
- [x] 7.10 *Property test P9: Dispatcher Terminal Routing* — hypothesis test that terminal deal_status routes to END, Negotiating routes to current_speaker
- [x] 7.11 *Property test P10: deal_status Invariant* — hypothesis test that deal_status is always in valid set, and once terminal never changes
- [x] 7.12 *Property test P11: Dynamic Graph Node Count* — hypothesis test that build_graph creates len(unique_roles) + 1 nodes
- [x] 7.13 *Property test P12: Dispatcher Routes to current_speaker* — hypothesis test that dispatcher conditional edge maps to current_speaker node name

## Task 8: Wire Up __init__.py + Integration Test

Finalize the package exports and run a full end-to-end integration test.

- [x] 8.1 Update `backend/app/orchestrator/__init__.py` to re-export: `build_graph`, `run_negotiation`, `NegotiationState`, `create_initial_state`, `to_pydantic`, `from_pydantic`
- [x] 8.2 Write end-to-end integration test: load a test scenario config, create initial state, run_negotiation with mocked LLMs, verify state snapshots are yielded and terminal state is reached
- [x] 8.3 Write integration test with 4-agent scenario (2 negotiators + 1 regulator + 1 observer) to verify N-agent support

## Task 9: Final Checkpoint

Run full test suite and verify all tests pass.

- [x] 9.1 Run `pytest backend/tests/ --cov=app.orchestrator --cov-fail-under=70` and confirm coverage target met
- [x] 9.2 Verify all 15 property tests pass (P1-P15)
- [x] 9.3 Verify orchestrator module is fully importable and functional
