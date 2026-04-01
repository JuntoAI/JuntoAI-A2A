# Requirements Document

## Introduction

This specification covers the LangGraph-based AI orchestration layer and Vertex AI integration for the JuntoAI A2A MVP. It defines the negotiation state machine that coordinates N autonomous AI agents through a config-driven, turn-based protocol. Each agent is assigned a type (`negotiator`, `regulator`, or `observer`) and routed to a distinct LLM via Google Vertex AI Model Garden, demonstrating LLM heterogeneity. The architecture is fully config-driven: agent count, turn order, personas, and termination thresholds are all read from the scenario JSON — no role names are hardcoded. The NegotiationState schema, generic agent node factory, dynamic graph construction, dispatcher-based routing, and Vertex AI model client configuration are all in scope. The FastAPI scaffold, Firestore persistence, and SSE streaming are covered in the separate `a2a-backend-core-sse` spec. The scenario JSON schema, loader, and toggle injection are covered in the `a2a-scenario-config-engine` spec. GCP infrastructure provisioning is covered in the `a2a-gcp-infrastructure` spec.

## Glossary

- **Orchestrator**: The LangGraph-based state machine module that drives the turn-based negotiation loop across all agent nodes.
- **NegotiationState**: The TypedDict (LangGraph-compatible) state object containing `session_id`, `scenario_id`, `turn_count`, `max_turns`, `current_speaker`, `deal_status`, `current_offer`, `history`, `hidden_context`, `agreement_threshold`, `turn_order`, `turn_order_index`, `agent_states`, and `scenario_config`. This is the LangGraph runtime representation. A separate Pydantic `NegotiationStateModel` (defined in the `a2a-backend-core-sse` spec) is used for API serialization and Firestore persistence. Explicit conversion functions (`to_pydantic()` / `from_pydantic()`) bridge the two representations.
- **AgentNode**: A single generic LangGraph node factory that produces a callable for any agent defined in the scenario config. The agent's `type` field (`negotiator`, `regulator`, `observer`) determines which output schema to use and how the node updates state.
- **Agent_Type**: The classification of an agent that determines its output schema and state-update behavior. Valid values: `negotiator` (proposes prices, updates `current_offer`), `regulator` (monitors compliance, tracks warnings, can block), `observer` (appends observations to history, read-only on negotiation fields).
- **Agent_State**: A per-agent state dictionary stored in `agent_states`, keyed by role name. Contains `role`, `name`, `agent_type`, `model_id`, and `last_proposed_price` (for negotiators). Enables N-agent tracking without hardcoded field names.
- **Turn**: One complete cycle through the `turn_order` array. The `turn_count` increments by 1 after the `turn_order_index` wraps back to 0. All SSE events emitted during a single cycle share the same `turn_number` value.
- **StateGraph**: The LangGraph `StateGraph` class used to define nodes and conditional routing edges for the negotiation loop.
- **Dispatcher**: A central routing node in the StateGraph that reads `current_speaker` and `deal_status` to determine which agent node executes next, or routes to END on terminal status.
- **Vertex_AI_Client**: The module that wraps the Google Vertex AI SDK to invoke LLM models from the Model Garden, handling authentication via GCP IAM.
- **Model_Router**: The configuration-driven component within the Orchestrator that maps `model_id` strings from the scenario config to initialized LangChain chat model instances.
- **Hidden_Context**: An optional dictionary injected into an agent's system prompt before the simulation starts, representing information asymmetry toggles from the investor UI. Keyed by agent role.
- **Warning_Count**: An integer tracked per regulator role in `agent_states`, representing cumulative WARNING statuses issued by that regulator. Three warnings from any single regulator trigger a BLOCKED status.

## Requirements

### Requirement 1: LangGraph and Vertex AI SDK Installation

**User Story:** As a developer, I want the LangGraph and Vertex AI SDK dependencies installed and configured, so that the orchestration layer can be built on top of them.

#### Acceptance Criteria

1. THE Orchestrator project SHALL declare `langgraph`, `langchain-google-vertexai`, and `google-cloud-aiplatform` as dependencies in the Python package configuration.
2. WHEN the dependencies are installed, THE Orchestrator SHALL be importable without errors in a Python 3.11+ environment.
3. THE Orchestrator project SHALL declare a `GOOGLE_CLOUD_PROJECT` environment variable for Vertex AI SDK initialization.
4. THE Orchestrator project SHALL declare a `VERTEX_AI_LOCATION` environment variable with a default value of `europe-west1` for Vertex AI regional endpoint configuration.

### Requirement 2: NegotiationState Schema for LangGraph

**User Story:** As a developer, I want a LangGraph-compatible NegotiationState schema with N-agent support, so that the state machine can pass validated state between any number of agent nodes.

#### Acceptance Criteria

1. THE NegotiationState SHALL be defined as a Python `TypedDict` compatible with LangGraph's `StateGraph` state specification.
2. THE NegotiationState SHALL contain a `session_id` field of type `str`.
3. THE NegotiationState SHALL contain a `scenario_id` field of type `str`, referencing the Arena_Scenario that initialized this negotiation.
4. THE NegotiationState SHALL contain a `turn_count` field of type `int` with a default value of `0`.
5. THE NegotiationState SHALL contain a `max_turns` field of type `int` with a default value of `15`.
6. THE NegotiationState SHALL contain a `current_speaker` field of type `str`, initialized to the first entry in `turn_order`.
7. THE NegotiationState SHALL contain a `deal_status` field of type `str` with a default value of `"Negotiating"`, constrained to the values `"Negotiating"`, `"Agreed"`, `"Blocked"`, or `"Failed"`.
8. THE NegotiationState SHALL contain a `current_offer` field of type `float` with a default value of `0.0`.
9. THE NegotiationState SHALL contain a `history` field of type `Annotated[list[dict[str, Any]], add]` using LangGraph's append-only reducer, with a default value of an empty list.
10. THE NegotiationState SHALL contain a `hidden_context` field of type `dict[str, Any]` with a default value of an empty dict, representing information asymmetry injected per agent role.
11. THE NegotiationState SHALL contain a `warning_count` field of type `int` with a default value of `0`, tracking the global cumulative regulator warning count for backward compatibility.
12. THE NegotiationState SHALL contain an `agreement_threshold` field of type `float` with a default value of `1000000.0`, loaded from the active Arena_Scenario's `negotiation_params.agreement_threshold` at initialization.
13. THE NegotiationState SHALL contain a `scenario_config` field of type `dict[str, Any]` with a default value of an empty dict, holding the full loaded Arena_Scenario for agent nodes to read personas, goals, and output fields dynamically.
14. THE NegotiationState SHALL contain a `turn_order` field of type `list[str]` defining the sequence of agent roles executed per cycle (e.g., `["Buyer", "Regulator", "Seller", "Regulator"]`).
15. THE NegotiationState SHALL contain a `turn_order_index` field of type `int` with a default value of `0`, tracking the current position within the `turn_order` array.
16. THE NegotiationState SHALL contain an `agent_states` field of type `dict[str, dict[str, Any]]` keyed by agent role name, where each value contains `role`, `name`, `agent_type`, `model_id`, and `last_proposed_price` fields.
17. THE NegotiationState SHALL contain an `active_toggles` field of type `list[str]` with a default value of an empty list.
18. THE Orchestrator SHALL provide a `to_pydantic(state: NegotiationState) -> NegotiationStateModel` conversion function that maps the TypedDict to the Pydantic model defined in the `a2a-backend-core-sse` spec, including `turn_order`, `turn_order_index`, and `agent_states` fields.
19. THE Orchestrator SHALL provide a `from_pydantic(model: NegotiationStateModel) -> NegotiationState` conversion function that maps the Pydantic model back to the TypedDict, including `turn_order`, `turn_order_index`, and `agent_states` fields.

### Requirement 3: Generic AgentNode Implementation

**User Story:** As a developer, I want a single generic agent node factory that can produce a callable for any agent type, so that adding new agent roles requires zero code changes.

#### Acceptance Criteria

1. THE Orchestrator SHALL provide a `create_agent_node(agent_role: str)` factory function that returns a callable compatible with LangGraph's node interface.
2. WHEN the returned callable is invoked, it SHALL look up the agent's configuration from `state["scenario_config"]["agents"]` by matching the `role` field to `agent_role`.
3. THE factory SHALL dispatch on the agent's `type` field from the scenario config to determine the output schema: `negotiator` → `NegotiatorOutput`, `regulator` → `RegulatorOutput`, `observer` → `ObserverOutput`.
4. WHEN a `negotiator` type agent completes its turn, THE node SHALL update `current_offer` to the agent's `proposed_price` and set `agent_states[role]["last_proposed_price"]` to the same value.
5. WHEN a `regulator` type agent returns a `"WARNING"` status, THE node SHALL increment `warning_count` by 1 and track `warning_count` per role in `agent_states[role]["warning_count"]`.
6. WHEN a `regulator` type agent's cumulative `warning_count` reaches 3, THE node SHALL set `deal_status` to `"Blocked"` regardless of the LLM response status.
7. WHEN a `regulator` type agent returns a `"BLOCKED"` status, THE node SHALL set `deal_status` to `"Blocked"`.
8. WHEN an `observer` type agent completes its turn, THE node SHALL append an observation entry to `history` only. THE node SHALL NOT modify `current_offer`, `deal_status`, or `warning_count`.
9. WHEN any agent node completes its turn, THE node SHALL advance `turn_order_index` by 1. WHEN `turn_order_index` reaches the length of `turn_order`, THE node SHALL wrap it to 0 and increment `turn_count` by 1.
10. WHEN any agent node completes its turn, THE node SHALL set `current_speaker` to `turn_order[new_turn_order_index]`.
11. WHEN `hidden_context` contains a key matching the agent's role, THE node SHALL inject the corresponding hidden context into the system prompt.
12. THE node SHALL construct the system prompt from the agent's `persona_prompt`, `goals`, `budget`, and any applicable hidden context from the scenario config. THE node SHALL NOT use hardcoded persona text.
13. THE node SHALL resolve its LLM client by passing the agent's `model_id` from the scenario config to the Model_Router.
14. IF the LLM response cannot be parsed into the expected output schema, THEN THE node SHALL retry the LLM call once with an explicit JSON formatting instruction appended to the prompt. If the retry also fails, THE node SHALL raise an `AgentOutputParseError`.

### Requirement 4: Dynamic Graph Construction

**User Story:** As a developer, I want the LangGraph StateGraph to be constructed dynamically from the scenario config, so that agent count and turn order are fully config-driven.

#### Acceptance Criteria

1. THE Orchestrator SHALL provide a `build_graph(scenario_config: dict)` function that constructs and compiles a StateGraph from the scenario configuration.
2. THE `build_graph` function SHALL read the `agents` array from the scenario config and create one node per unique agent role using `create_agent_node(role)`.
3. THE `build_graph` function SHALL read the `turn_order` from `scenario_config["negotiation_params"]["turn_order"]` if present, or derive it from the agents array if absent.
4. THE `build_graph` function SHALL add a `dispatcher` node that routes execution to the correct agent node based on `current_speaker`.
5. THE `build_graph` function SHALL NOT contain any hardcoded role names (e.g., no `"Buyer"`, `"Seller"`, `"Regulator"` string literals). All role names SHALL come from the scenario config.
6. THE `build_graph` function SHALL set the graph entry point to the `dispatcher` node.
7. THE `build_graph` function SHALL add edges from every agent node back to the `dispatcher` node.

### Requirement 5: Turn Order and Routing Logic

**User Story:** As a developer, I want the dispatcher to route agents in the order defined by the scenario config's turn_order field, so that execution sequence is fully configurable.

#### Acceptance Criteria

1. THE `turn_order` field in `negotiation_params` SHALL define the execution sequence of agent roles per cycle (e.g., `["Buyer", "Regulator", "Seller", "Regulator"]`).
2. THE dispatcher node SHALL read `current_speaker` from the state and route execution to the agent node matching that role.
3. WHEN `deal_status` is `"Agreed"`, `"Blocked"`, or `"Failed"`, THE dispatcher SHALL route to the `END` node, terminating graph execution.
4. WHEN `turn_count` equals `max_turns` and `deal_status` is `"Negotiating"`, THE dispatcher SHALL set `deal_status` to `"Failed"` and route to the `END` node.
5. THE dispatcher SHALL implement routing as a conditional edge that maps `current_speaker` values to agent node names, plus a terminal condition check.

### Requirement 6: Vertex AI Model Router

**User Story:** As a developer, I want a configuration-driven model router that maps model_id strings to Vertex AI model instances, so that the system demonstrates LLM heterogeneity.

#### Acceptance Criteria

1. THE Model_Router SHALL accept an agent's `model_id` string (from the scenario config's Agent_Definition) and return an initialized LangChain chat model instance configured for the corresponding Vertex AI model endpoint.
2. THE Model_Router SHALL support at minimum the following model identifiers: `gemini-2.5-flash`, `claude-3-5-sonnet-v2`, `claude-sonnet-4`, and `gemini-2.5-pro`.
3. THE Model_Router SHALL accept an optional `fallback_model_id` parameter. When the primary model endpoint is unavailable or times out, THE Model_Router SHALL attempt the fallback model before raising an error.
4. THE Model_Router SHALL authenticate all Vertex AI API calls using GCP IAM credentials from the runtime environment, requiring no separate API keys.
5. THE Model_Router SHALL pass the `GOOGLE_CLOUD_PROJECT` and `VERTEX_AI_LOCATION` configuration values to each LLM client instance.
6. THE Model_Router SHALL NOT maintain a hardcoded mapping of agent role names to model identifiers. Model assignment is defined in the scenario JSON and passed to the Model_Router at runtime by each agent node.
7. WHEN a `model_id` is not recognized or the corresponding Vertex AI endpoint is unavailable and no fallback succeeds, THE Model_Router SHALL raise a `ModelNotAvailableError` with the `model_id` and a descriptive message.
8. THE Model_Router SHALL configure a per-request timeout of 60 seconds (configurable via `VERTEX_AI_REQUEST_TIMEOUT_SECONDS` environment variable) on all LLM invocations. IF a request exceeds the timeout, THE Model_Router SHALL cancel the request and attempt the fallback model if one is configured, or raise a `ModelTimeoutError` with the `model_id` and elapsed time.
9. THE Model_Router SHALL log a warning when any LLM request exceeds 30 seconds, including the `model_id`, agent role, and elapsed time, to aid in identifying slow model endpoints before they hit the hard timeout.

### Requirement 7: Agent Output Parsing by Type

**User Story:** As a developer, I want structured output models determined by agent type, so that the orchestrator can reliably parse and validate any agent's LLM response.

#### Acceptance Criteria

1. THE Orchestrator SHALL define a `NegotiatorOutput` Pydantic model containing `inner_thought` (str), `public_message` (str), `proposed_price` (float), and an optional `extra_fields` (dict[str, Any]) for scenario-specific fields.
2. THE Orchestrator SHALL define a `RegulatorOutput` Pydantic model containing `status` (str, constrained to `"CLEAR"`, `"WARNING"`, or `"BLOCKED"`) and `reasoning` (str) fields.
3. THE Orchestrator SHALL define an `ObserverOutput` Pydantic model containing `observation` (str) and an optional `recommendation` (str) field.
4. THE agent node factory SHALL select the output model based on the agent's `type` field from the scenario config: `negotiator` → `NegotiatorOutput`, `regulator` → `RegulatorOutput`, `observer` → `ObserverOutput`.
5. WHEN an LLM response is received, THE node SHALL parse the response text as JSON and validate it against the corresponding Pydantic output model. Any fields defined in the agent's `output_fields` (from the scenario config) that are not in the base model SHALL be captured in `extra_fields` (for negotiators).
6. IF the LLM response JSON is invalid or missing required fields, THEN THE node SHALL raise an `AgentOutputParseError` with the agent name and raw response text (after the retry-once mechanism is exhausted).
7. FOR ALL valid NegotiatorOutput instances, serializing to JSON then deserializing back SHALL produce an equivalent object (round-trip property).
8. FOR ALL valid RegulatorOutput instances, serializing to JSON then deserializing back SHALL produce an equivalent object (round-trip property).

### Requirement 8: N-Agent Termination Conditions

**User Story:** As a developer, I want termination conditions that work for any number of negotiating agents, so that the simulation always reaches a definitive outcome regardless of scenario configuration.

#### Acceptance Criteria

1. WHEN ALL agents with `agent_type == "negotiator"` have a `last_proposed_price` in `agent_states` that is within `agreement_threshold` of every other negotiator's `last_proposed_price`, THE Orchestrator SHALL set `deal_status` to `"Agreed"`. THE Orchestrator SHALL NOT use a hardcoded threshold value; the threshold MUST come from the scenario configuration.
2. WHEN a scenario has only a single negotiator, THE Orchestrator SHALL skip the price convergence check (agreement requires explicit regulator approval or max_turns exhaustion).
3. WHEN `turn_count` reaches `max_turns` and `deal_status` remains `"Negotiating"`, THE Orchestrator SHALL set `deal_status` to `"Failed"`.
4. WHEN any single regulator sets `deal_status` to `"Blocked"`, THE Orchestrator SHALL terminate the negotiation loop immediately.
5. WHEN `deal_status` transitions from `"Negotiating"` to a terminal state, THE Orchestrator SHALL record the final `deal_status`, `current_offer`, `turn_count`, and `warning_count` in the NegotiationState.
6. THE Orchestrator SHALL verify that `deal_status` is one of `"Negotiating"`, `"Agreed"`, `"Blocked"`, or `"Failed"` at every state transition.
7. THE Orchestrator SHALL read the `agreement_threshold` and `max_turns` values from the loaded Arena_Scenario's `negotiation_params` at graph initialization time and inject them into the NegotiationState, so that termination conditions are fully config-driven per scenario.

### Requirement 9: Graph Compilation and Execution Entry Point

**User Story:** As a developer, I want a single entry point to compile and execute the negotiation graph, so that the FastAPI endpoint can trigger a full negotiation run.

#### Acceptance Criteria

1. THE Orchestrator SHALL provide a `build_graph(scenario_config)` function that constructs and compiles the StateGraph with all nodes and edges dynamically from the scenario config.
2. THE Orchestrator SHALL provide a `run_negotiation(initial_state: NegotiationState)` async generator function that executes the compiled graph from the initial state to completion.
3. WHEN `run_negotiation` is called, THE Orchestrator SHALL yield intermediate NegotiationState snapshots after each node execution, enabling SSE streaming.
4. WHEN the graph execution completes, THE `run_negotiation` generator SHALL yield the final NegotiationState.
5. IF an unrecoverable error occurs during graph execution, THEN THE Orchestrator SHALL set `deal_status` to `"Failed"`, log the error with the `session_id`, and yield the error state.

### Requirement 10: State Conversion Functions

**User Story:** As a developer, I want explicit conversion functions between the LangGraph TypedDict and the Pydantic model, so that state can be serialized for Firestore and API responses without data loss.

#### Acceptance Criteria

1. THE `to_pydantic()` function SHALL map all NegotiationState TypedDict fields to the corresponding Pydantic `NegotiationStateModel` fields, including `turn_order`, `turn_order_index`, and `agent_states`.
2. THE `from_pydantic()` function SHALL map all Pydantic `NegotiationStateModel` fields back to the NegotiationState TypedDict, including `turn_order`, `turn_order_index`, and `agent_states`.
3. FOR ALL valid NegotiationState instances, converting to Pydantic and back SHALL produce an equivalent NegotiationState (round-trip property).
4. THE `to_pydantic()` function SHALL handle the `agent_states` dict by converting each `AgentState` dict to a serializable format.
5. THE `from_pydantic()` function SHALL reconstruct the `agent_states` dict with proper typing from the Pydantic model's serialized format.
