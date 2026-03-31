# Requirements Document

## Introduction

This specification covers the LangGraph-based AI orchestration layer and Vertex AI integration for the JuntoAI A2A MVP. It defines the negotiation state machine that coordinates three autonomous AI agents (Buyer, Seller, Regulator) through a turn-based protocol. Each agent is routed to a distinct LLM via Google Vertex AI Model Garden, demonstrating LLM heterogeneity. The NegotiationState schema, LangGraph node definitions, conditional routing edges, and Vertex AI model client configuration are all in scope. The FastAPI scaffold, Firestore persistence, and SSE streaming are covered in the separate `a2a-backend-core-sse` spec. GCP infrastructure provisioning is covered in the `a2a-gcp-infrastructure` spec.

## Glossary

- **Orchestrator**: The LangGraph-based state machine module that drives the turn-based negotiation loop across all agent nodes.
- **NegotiationState**: The TypedDict (LangGraph-compatible) state object containing `session_id`, `scenario_id`, `turn_count`, `max_turns`, `current_speaker`, `deal_status`, `current_offer`, `history`, `hidden_context`, and `agreement_threshold`. This is the LangGraph runtime representation. A separate Pydantic `NegotiationStateModel` (defined in the `a2a-backend-core-sse` spec) is used for API serialization and Firestore persistence. Explicit conversion functions (`to_pydantic()` / `from_pydantic()`) bridge the two representations.
- **BuyerNode**: A LangGraph node representing the first negotiating agent (e.g., Buyer/Recruiter). It reads its persona, goals, and budget from the `scenario_config` field of the NegotiationState, invokes its assigned LLM via the Model_Router, and returns an updated state with `inner_thought`, `public_message`, and `proposed_price`. Agent identity is fully config-driven — no hardcoded personas.
- **SellerNode**: A LangGraph node representing the second negotiating agent (e.g., Seller/Candidate). It reads its persona, goals, and budget from the `scenario_config` field of the NegotiationState, invokes its assigned LLM via the Model_Router, and returns an updated state with `inner_thought`, `public_message`, `proposed_price`, and optional scenario-specific fields.
- **RegulatorNode**: A LangGraph node representing the compliance agent. It reads its persona and monitoring criteria from the `scenario_config` field of the NegotiationState, invokes its assigned LLM via the Model_Router, and returns an updated state with `status` (CLEAR, WARNING, or BLOCKED) and `reasoning`.
- **StateGraph**: The LangGraph `StateGraph` class used to define nodes and conditional routing edges for the negotiation loop.
- **Vertex_AI_Client**: The module that wraps the Google Vertex AI SDK to invoke LLM models from the Model Garden, handling authentication via GCP IAM.
- **Model_Router**: The configuration-driven component within the Orchestrator that maps each agent role to a specific Vertex AI model endpoint.
- **Hidden_Context**: An optional dictionary injected into an agent's system prompt before the simulation starts, representing information asymmetry toggles from the investor UI.
- **Turn**: One complete negotiation round consisting of a Buyer node execution, a Regulator check, a Seller node execution, and a second Regulator check (4 node executions total). The `turn_count` increments by 1 after this full cycle completes. The `turn_number` emitted in SSE events equals the current `turn_count` value at the time the node executes, so all 4 node executions within the same cycle share the same `turn_number`.
- **Warning_Count**: An integer field tracked by the RegulatorNode representing the cumulative number of WARNING statuses issued; three warnings trigger a BLOCKED status.

## Requirements

### Requirement 1: LangGraph and Vertex AI SDK Installation

**User Story:** As a developer, I want the LangGraph and Vertex AI SDK dependencies installed and configured, so that the orchestration layer can be built on top of them.

#### Acceptance Criteria

1. THE Orchestrator project SHALL declare `langgraph`, `langchain-google-vertexai`, and `google-cloud-aiplatform` as dependencies in the Python package configuration.
2. WHEN the dependencies are installed, THE Orchestrator SHALL be importable without errors in a Python 3.11+ environment.
3. THE Orchestrator project SHALL declare a `GOOGLE_CLOUD_PROJECT` environment variable for Vertex AI SDK initialization.
4. THE Orchestrator project SHALL declare a `VERTEX_AI_LOCATION` environment variable with a default value of `europe-west1` for Vertex AI regional endpoint configuration.

### Requirement 2: NegotiationState Schema for LangGraph

**User Story:** As a developer, I want a LangGraph-compatible NegotiationState schema, so that the state machine can pass validated state between nodes.

#### Acceptance Criteria

1. THE NegotiationState SHALL be defined as a Python `TypedDict` compatible with LangGraph's `StateGraph` state specification.
2. THE NegotiationState SHALL contain a `session_id` field of type `str`.
3. THE NegotiationState SHALL contain a `scenario_id` field of type `str`, referencing the Arena_Scenario that initialized this negotiation.
4. THE NegotiationState SHALL contain a `turn_count` field of type `int` with a default value of `0`.
5. THE NegotiationState SHALL contain a `max_turns` field of type `int` with a default value of `15`.
6. THE NegotiationState SHALL contain a `current_speaker` field of type `str` with a default value of `"Buyer"`.
7. THE NegotiationState SHALL contain a `deal_status` field of type `str` with a default value of `"Negotiating"`, constrained to the values `"Negotiating"`, `"Agreed"`, `"Blocked"`, or `"Failed"`.
8. THE NegotiationState SHALL contain a `current_offer` field of type `float` with a default value of `0.0`.
9. THE NegotiationState SHALL contain a `history` field of type `list[dict[str, Any]]` with a default value of an empty list.
10. THE NegotiationState SHALL contain a `hidden_context` field of type `dict[str, Any]` with a default value of an empty dict, representing information asymmetry injected per agent.
11. THE NegotiationState SHALL contain a `warning_count` field of type `int` with a default value of `0`, tracking cumulative regulator warnings.
12. THE NegotiationState SHALL contain an `agreement_threshold` field of type `float` with a default value of `1000000.0`, loaded from the active Arena_Scenario's `negotiation_params.agreement_threshold` at initialization.
13. THE NegotiationState SHALL contain a `scenario_config` field of type `dict[str, Any]` with a default value of an empty dict, holding the full loaded Arena_Scenario for agent nodes to read personas, goals, and output fields dynamically.
14. THE Orchestrator SHALL provide a `negotiation_state_to_pydantic(state: NegotiationState) -> NegotiationStateModel` conversion function that maps the TypedDict to the Pydantic model defined in the `a2a-backend-core-sse` spec.
15. THE Orchestrator SHALL provide a `pydantic_to_negotiation_state(model: NegotiationStateModel) -> NegotiationState` conversion function that maps the Pydantic model back to the TypedDict.

### Requirement 3: BuyerNode Implementation

**User Story:** As a developer, I want a BuyerNode that invokes the Buyer agent's LLM and updates the negotiation state, so that the Buyer can autonomously participate in the negotiation loop.

#### Acceptance Criteria

1. THE BuyerNode SHALL be a callable function registered as a node in the StateGraph.
2. WHEN the BuyerNode is invoked, THE BuyerNode SHALL read the current NegotiationState including `history`, `current_offer`, `hidden_context`, and `scenario_config`.
3. WHEN the BuyerNode is invoked, THE BuyerNode SHALL look up the first agent in `scenario_config.agents` whose `role` matches the Buyer/first-negotiator role, and construct a prompt using that agent's `persona_prompt`, `goals`, and `budget` fields from the scenario config. THE BuyerNode SHALL NOT use hardcoded persona text.
4. WHEN `hidden_context` contains a key matching the Buyer agent role, THE BuyerNode SHALL inject the corresponding hidden context into the system prompt.
5. WHEN the BuyerNode receives a response from the LLM, THE BuyerNode SHALL parse the response into the fields defined by the agent's `output_fields` in the scenario config (typically `inner_thought`, `public_message`, and `proposed_price`).
6. WHEN the BuyerNode completes its turn, THE BuyerNode SHALL append a new entry to the `history` list containing `agent_name`, the parsed output fields, and `turn_number`.
7. WHEN the BuyerNode completes its turn, THE BuyerNode SHALL update `current_offer` to the `proposed_price` value from the LLM response.
8. WHEN the BuyerNode completes its turn, THE BuyerNode SHALL set `current_speaker` to `"Regulator"` in the returned state.
9. IF the LLM response cannot be parsed into the required output schema, THEN THE BuyerNode SHALL retry the LLM call once with an explicit formatting instruction appended to the prompt.
10. THE BuyerNode SHALL resolve its LLM client by passing the agent's `model_id` from the scenario config to the Model_Router, not by using a hardcoded model identifier.

### Requirement 4: SellerNode Implementation

**User Story:** As a developer, I want a SellerNode that invokes the Seller agent's LLM and updates the negotiation state, so that the Seller can autonomously participate in the negotiation loop.

#### Acceptance Criteria

1. THE SellerNode SHALL be a callable function registered as a node in the StateGraph.
2. WHEN the SellerNode is invoked, THE SellerNode SHALL read the current NegotiationState including `history`, `current_offer`, `hidden_context`, and `scenario_config`.
3. WHEN the SellerNode is invoked, THE SellerNode SHALL look up the second agent in `scenario_config.agents` whose `role` matches the Seller/second-negotiator role, and construct a prompt using that agent's `persona_prompt`, `goals`, and `budget` fields from the scenario config. THE SellerNode SHALL NOT use hardcoded persona text.
4. WHEN `hidden_context` contains a key matching the Seller agent role, THE SellerNode SHALL inject the corresponding hidden context into the system prompt.
5. WHEN the SellerNode receives a response from the LLM, THE SellerNode SHALL parse the response into the fields defined by the agent's `output_fields` in the scenario config (typically `inner_thought`, `public_message`, `proposed_price`, and optional scenario-specific fields like `retention_clause_demanded`).
6. WHEN the SellerNode completes its turn, THE SellerNode SHALL append a new entry to the `history` list containing `agent_name`, the parsed output fields, and `turn_number`.
7. WHEN the SellerNode completes its turn, THE SellerNode SHALL update `current_offer` to the `proposed_price` value from the LLM response.
8. WHEN the SellerNode completes its turn, THE SellerNode SHALL set `current_speaker` to `"Regulator"` in the returned state.
9. IF the LLM response cannot be parsed into the required output schema, THEN THE SellerNode SHALL retry the LLM call once with an explicit formatting instruction appended to the prompt.
10. THE SellerNode SHALL resolve its LLM client by passing the agent's `model_id` from the scenario config to the Model_Router, not by using a hardcoded model identifier.

### Requirement 5: RegulatorNode Implementation

**User Story:** As a developer, I want a RegulatorNode that monitors the negotiation for compliance violations and can block the deal, so that regulatory oversight is enforced autonomously.

#### Acceptance Criteria

1. THE RegulatorNode SHALL be a callable function registered as a node in the StateGraph.
2. WHEN the RegulatorNode is invoked, THE RegulatorNode SHALL read the current NegotiationState including `history`, `current_offer`, `warning_count`, `hidden_context`, and `scenario_config`.
3. WHEN the RegulatorNode is invoked, THE RegulatorNode SHALL look up the agent in `scenario_config.agents` whose `role` matches the Regulator role, and construct a prompt using that agent's `persona_prompt` and `goals` fields from the scenario config. THE RegulatorNode SHALL NOT use hardcoded persona text.
4. WHEN `hidden_context` contains a key matching the Regulator agent role, THE RegulatorNode SHALL inject the corresponding hidden context into the system prompt.
5. WHEN the RegulatorNode receives a response from the LLM, THE RegulatorNode SHALL parse the response into `status` (one of `"CLEAR"`, `"WARNING"`, `"BLOCKED"`) and `reasoning` (str) fields.
6. WHEN the RegulatorNode returns a `status` of `"WARNING"`, THE RegulatorNode SHALL increment the `warning_count` field by 1.
7. WHEN the `warning_count` reaches 3, THE RegulatorNode SHALL set `deal_status` to `"Blocked"` regardless of the LLM response status.
8. WHEN the RegulatorNode returns a `status` of `"BLOCKED"`, THE RegulatorNode SHALL set `deal_status` to `"Blocked"`.
9. WHEN the RegulatorNode completes its turn, THE RegulatorNode SHALL append a new entry to the `history` list containing `agent_name`, `status`, `reasoning`, and `turn_number`.
10. IF the LLM response cannot be parsed into the required output schema, THEN THE RegulatorNode SHALL retry the LLM call once with an explicit formatting instruction appended to the prompt.
11. THE RegulatorNode SHALL resolve its LLM client by passing the agent's `model_id` from the scenario config to the Model_Router, not by using a hardcoded model identifier.

### Requirement 6: LangGraph Routing Logic

**User Story:** As a developer, I want deterministic routing logic between agent nodes, so that the negotiation follows the correct turn order (Buyer → Regulator → Seller → Regulator → Buyer → ...).

#### Acceptance Criteria

1. THE Orchestrator SHALL define a StateGraph with three nodes: `buyer`, `seller`, and `regulator`.
2. THE Orchestrator SHALL set the graph entry point to the `buyer` node.
3. WHEN the `buyer` node completes, THE Orchestrator SHALL route to the `regulator` node.
4. WHEN the `regulator` node completes after the Buyer's turn, THE Orchestrator SHALL route to the `seller` node.
5. WHEN the `seller` node completes, THE Orchestrator SHALL route to the `regulator` node.
6. WHEN the `regulator` node completes after the Seller's turn, THE Orchestrator SHALL route to the `buyer` node.
7. THE Orchestrator SHALL implement routing from the `regulator` node as a conditional edge that inspects `current_speaker` to determine the next node.
8. WHEN `deal_status` is `"Agreed"`, `"Blocked"`, or `"Failed"`, THE Orchestrator SHALL route to the `END` node, terminating the graph execution.
9. WHEN `turn_count` equals `max_turns` and `deal_status` is `"Negotiating"`, THE Orchestrator SHALL set `deal_status` to `"Failed"` and route to the `END` node.
10. THE Orchestrator SHALL increment `turn_count` by 1 after each complete Buyer-Regulator-Seller-Regulator cycle (4 node executions). All SSE events emitted during a single cycle SHALL carry the same `turn_number` value equal to the `turn_count` at cycle start, so the UI's Turn Counter advances once per full negotiation round, not per node execution.

### Requirement 7: Vertex AI Model Router

**User Story:** As a developer, I want a configuration-driven model router that maps each agent to a specific Vertex AI model, so that the system demonstrates LLM heterogeneity.

#### Acceptance Criteria

1. THE Model_Router SHALL accept an agent's `model_id` string (from the scenario config's Agent_Definition) and return an initialized LLM client configured for the corresponding Vertex AI model endpoint.
2. THE Model_Router SHALL support at minimum the following model identifiers: `gemini-2.5-flash`, `claude-3-5-sonnet-v2`, `claude-sonnet-4`, and `gemini-2.5-pro`.
3. THE Model_Router SHALL accept an optional `fallback_model_id` parameter. When the primary model endpoint is unavailable or times out, THE Model_Router SHALL attempt the fallback model before raising an error.
4. THE Model_Router SHALL authenticate all Vertex AI API calls using GCP IAM credentials from the runtime environment, requiring no separate API keys.
5. THE Model_Router SHALL pass the `GOOGLE_CLOUD_PROJECT` and `VERTEX_AI_LOCATION` configuration values to each LLM client instance.
6. THE Model_Router SHALL NOT maintain a hardcoded mapping of agent role names to model identifiers. Model assignment is defined in the scenario JSON and passed to the Model_Router at runtime by each agent node.
7. WHEN a `model_id` is not recognized or the corresponding Vertex AI endpoint is unavailable and no fallback succeeds, THE Model_Router SHALL raise a `ModelNotAvailableError` with the `model_id` and a descriptive message.
8. THE Model_Router SHALL configure a per-request timeout of 60 seconds (configurable via `VERTEX_AI_REQUEST_TIMEOUT_SECONDS` environment variable) on all LLM invocations. IF a request exceeds the timeout, THE Model_Router SHALL cancel the request and attempt the fallback model if one is configured, or raise a `ModelTimeoutError` with the `model_id` and elapsed time.
9. THE Model_Router SHALL log a warning when any LLM request exceeds 30 seconds, including the `model_id`, agent role, and elapsed time, to aid in identifying slow model endpoints before they hit the hard timeout.

### Requirement 8: Agent Output Parsing and Validation

**User Story:** As a developer, I want structured output parsing for all agent LLM responses, so that the orchestration layer can reliably extract and validate agent actions.

#### Acceptance Criteria

1. THE Orchestrator SHALL define a `BaseAgentOutput` Pydantic model containing `inner_thought` (str) and `public_message` (str) fields as the minimum required output for all negotiating agents.
2. THE Orchestrator SHALL define a `NegotiatingAgentOutput` Pydantic model extending `BaseAgentOutput` with `proposed_price` (float) and an optional `extra_fields` (dict) for scenario-specific fields (e.g., `retention_clause_demanded`).
3. THE Orchestrator SHALL define a `RegulatorOutput` Pydantic model containing `status` (str, constrained to `"CLEAR"`, `"WARNING"`, or `"BLOCKED"`) and `reasoning` (str) fields.
4. WHEN an LLM response is received, THE Orchestrator SHALL parse the response text as JSON and validate it against the corresponding Pydantic model. Any fields defined in the agent's `output_fields` (from the scenario config) that are not in the base model SHALL be captured in the `extra_fields` dict.
5. IF the LLM response JSON is invalid or missing required fields, THEN THE Orchestrator SHALL raise a `AgentOutputParseError` with the agent name and raw response text.
6. FOR ALL valid NegotiatingAgentOutput instances, serializing to JSON then deserializing back SHALL produce an equivalent object (round-trip property).
7. FOR ALL valid RegulatorOutput instances, serializing to JSON then deserializing back SHALL produce an equivalent RegulatorOutput object (round-trip property).

### Requirement 9: Negotiation Termination Conditions

**User Story:** As a developer, I want clearly defined termination conditions for the negotiation loop, so that the simulation always reaches a definitive outcome.

#### Acceptance Criteria

1. WHEN both the Buyer's `proposed_price` and the Seller's `proposed_price` are within the `agreement_threshold` value loaded from the active Arena_Scenario's `negotiation_params.agreement_threshold` field, AND any scenario-specific acceptance conditions are met (e.g., `retention_clause_demanded` satisfied), THE Orchestrator SHALL set `deal_status` to `"Agreed"`. THE Orchestrator SHALL NOT use a hardcoded threshold value; the threshold MUST come from the scenario configuration.
2. WHEN `turn_count` reaches `max_turns` and `deal_status` remains `"Negotiating"`, THE Orchestrator SHALL set `deal_status` to `"Failed"`.
3. WHEN the RegulatorNode sets `deal_status` to `"Blocked"`, THE Orchestrator SHALL terminate the negotiation loop.
4. WHEN `deal_status` transitions from `"Negotiating"` to a terminal state, THE Orchestrator SHALL record the final `deal_status`, `current_offer`, `turn_count`, and `warning_count` in the NegotiationState.
5. THE Orchestrator SHALL verify that `deal_status` is one of `"Negotiating"`, `"Agreed"`, `"Blocked"`, or `"Failed"` at every state transition.
6. THE Orchestrator SHALL read the `agreement_threshold` and `max_turns` values from the loaded Arena_Scenario's `negotiation_params` at graph initialization time and inject them into the NegotiationState, so that termination conditions are fully config-driven per scenario.

### Requirement 10: Graph Compilation and Execution Entry Point

**User Story:** As a developer, I want a single entry point to compile and execute the negotiation graph, so that the FastAPI endpoint can trigger a full negotiation run.

#### Acceptance Criteria

1. THE Orchestrator SHALL provide a `build_graph()` function that constructs and compiles the StateGraph with all nodes and edges.
2. THE Orchestrator SHALL provide a `run_negotiation(initial_state: NegotiationState)` async function that executes the compiled graph from the initial state to completion.
3. WHEN `run_negotiation` is called, THE Orchestrator SHALL yield intermediate NegotiationState snapshots after each node execution, enabling SSE streaming.
4. WHEN the graph execution completes, THE `run_negotiation` function SHALL return the final NegotiationState.
5. IF an unrecoverable error occurs during graph execution, THEN THE Orchestrator SHALL set `deal_status` to `"Failed"`, log the error with the `session_id`, and return the error state.
