# Requirements Document

## Introduction

This specification covers the LangGraph-based AI orchestration layer and Vertex AI integration for the JuntoAI A2A MVP. It defines the negotiation state machine that coordinates three autonomous AI agents (Buyer, Seller, Regulator) through a turn-based protocol. Each agent is routed to a distinct LLM via Google Vertex AI Model Garden, demonstrating LLM heterogeneity. The NegotiationState schema, LangGraph node definitions, conditional routing edges, and Vertex AI model client configuration are all in scope. The FastAPI scaffold, Firestore persistence, and SSE streaming are covered in the separate `a2a-backend-core-sse` spec. GCP infrastructure provisioning is covered in the `a2a-gcp-infrastructure` spec.

## Glossary

- **Orchestrator**: The LangGraph-based state machine module that drives the turn-based negotiation loop across all agent nodes.
- **NegotiationState**: The TypedDict (LangGraph-compatible) state object containing `session_id`, `turn_count`, `max_turns`, `current_speaker`, `deal_status`, `current_offer`, `history`, and `hidden_context`.
- **BuyerNode**: A LangGraph node representing the Buyer agent (Titan Corp CEO) that reads the shared NegotiationState, invokes its assigned LLM, and returns an updated state with `inner_thought`, `public_message`, and `proposed_price`.
- **SellerNode**: A LangGraph node representing the Seller agent (Innovate Tech Founder) that reads the shared NegotiationState, invokes its assigned LLM, and returns an updated state with `inner_thought`, `public_message`, `proposed_price`, and `retention_clause_demanded`.
- **RegulatorNode**: A LangGraph node representing the Regulator agent (EU Compliance Bot) that reads the shared NegotiationState, invokes its assigned LLM, and returns an updated state with `status` (CLEAR, WARNING, or BLOCKED) and `reasoning`.
- **StateGraph**: The LangGraph `StateGraph` class used to define nodes and conditional routing edges for the negotiation loop.
- **Vertex_AI_Client**: The module that wraps the Google Vertex AI SDK to invoke LLM models from the Model Garden, handling authentication via GCP IAM.
- **Model_Router**: The configuration-driven component within the Orchestrator that maps each agent role to a specific Vertex AI model endpoint.
- **Hidden_Context**: An optional dictionary injected into an agent's system prompt before the simulation starts, representing information asymmetry toggles from the investor UI.
- **Turn**: A single cycle in which the current speaker agent generates a response and the Orchestrator updates the NegotiationState.
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
3. THE NegotiationState SHALL contain a `turn_count` field of type `int` with a default value of `0`.
4. THE NegotiationState SHALL contain a `max_turns` field of type `int` with a default value of `15`.
5. THE NegotiationState SHALL contain a `current_speaker` field of type `str` with a default value of `"Buyer"`.
6. THE NegotiationState SHALL contain a `deal_status` field of type `str` with a default value of `"Negotiating"`, constrained to the values `"Negotiating"`, `"Agreed"`, `"Blocked"`, or `"Failed"`.
7. THE NegotiationState SHALL contain a `current_offer` field of type `float` with a default value of `0.0`.
8. THE NegotiationState SHALL contain a `history` field of type `list[dict[str, Any]]` with a default value of an empty list.
9. THE NegotiationState SHALL contain a `hidden_context` field of type `dict[str, Any]` with a default value of an empty dict, representing information asymmetry injected per agent.
10. THE NegotiationState SHALL contain a `warning_count` field of type `int` with a default value of `0`, tracking cumulative regulator warnings.

### Requirement 3: BuyerNode Implementation

**User Story:** As a developer, I want a BuyerNode that invokes the Buyer agent's LLM and updates the negotiation state, so that the Buyer can autonomously participate in the negotiation loop.

#### Acceptance Criteria

1. THE BuyerNode SHALL be a callable function registered as a node in the StateGraph.
2. WHEN the BuyerNode is invoked, THE BuyerNode SHALL read the current NegotiationState including `history`, `current_offer`, and `hidden_context`.
3. WHEN the BuyerNode is invoked, THE BuyerNode SHALL construct a prompt containing the Buyer persona system prompt (Titan Corp CEO, max budget €50M, target price €35M) and the shared negotiation history.
4. WHEN `hidden_context` contains a key matching the Buyer agent role, THE BuyerNode SHALL inject the corresponding hidden context into the system prompt.
5. WHEN the BuyerNode receives a response from the LLM, THE BuyerNode SHALL parse the response into `inner_thought` (str), `public_message` (str), and `proposed_price` (float) fields.
6. WHEN the BuyerNode completes its turn, THE BuyerNode SHALL append a new entry to the `history` list containing `agent_name`, `inner_thought`, `public_message`, `proposed_price`, and `turn_number`.
7. WHEN the BuyerNode completes its turn, THE BuyerNode SHALL update `current_offer` to the `proposed_price` value from the LLM response.
8. WHEN the BuyerNode completes its turn, THE BuyerNode SHALL set `current_speaker` to `"Regulator"` in the returned state.
9. IF the LLM response cannot be parsed into the required output schema, THEN THE BuyerNode SHALL retry the LLM call once with an explicit formatting instruction appended to the prompt.

### Requirement 4: SellerNode Implementation

**User Story:** As a developer, I want a SellerNode that invokes the Seller agent's LLM and updates the negotiation state, so that the Seller can autonomously participate in the negotiation loop.

#### Acceptance Criteria

1. THE SellerNode SHALL be a callable function registered as a node in the StateGraph.
2. WHEN the SellerNode is invoked, THE SellerNode SHALL read the current NegotiationState including `history`, `current_offer`, and `hidden_context`.
3. WHEN the SellerNode is invoked, THE SellerNode SHALL construct a prompt containing the Seller persona system prompt (Innovate Tech Founder, floor budget €40M, 2-year retention clause required) and the shared negotiation history.
4. WHEN `hidden_context` contains a key matching the Seller agent role, THE SellerNode SHALL inject the corresponding hidden context into the system prompt.
5. WHEN the SellerNode receives a response from the LLM, THE SellerNode SHALL parse the response into `inner_thought` (str), `public_message` (str), `proposed_price` (float), and `retention_clause_demanded` (bool) fields.
6. WHEN the SellerNode completes its turn, THE SellerNode SHALL append a new entry to the `history` list containing `agent_name`, `inner_thought`, `public_message`, `proposed_price`, `retention_clause_demanded`, and `turn_number`.
7. WHEN the SellerNode completes its turn, THE SellerNode SHALL update `current_offer` to the `proposed_price` value from the LLM response.
8. WHEN the SellerNode completes its turn, THE SellerNode SHALL set `current_speaker` to `"Regulator"` in the returned state.
9. IF the LLM response cannot be parsed into the required output schema, THEN THE SellerNode SHALL retry the LLM call once with an explicit formatting instruction appended to the prompt.

### Requirement 5: RegulatorNode Implementation

**User Story:** As a developer, I want a RegulatorNode that monitors the negotiation for compliance violations and can block the deal, so that regulatory oversight is enforced autonomously.

#### Acceptance Criteria

1. THE RegulatorNode SHALL be a callable function registered as a node in the StateGraph.
2. WHEN the RegulatorNode is invoked, THE RegulatorNode SHALL read the current NegotiationState including `history`, `current_offer`, `warning_count`, and `hidden_context`.
3. WHEN the RegulatorNode is invoked, THE RegulatorNode SHALL construct a prompt containing the Regulator persona system prompt (EU Compliance Bot, monitor for data privacy and monopoly risks) and the shared negotiation history.
4. WHEN `hidden_context` contains a key matching the Regulator agent role, THE RegulatorNode SHALL inject the corresponding hidden context into the system prompt.
5. WHEN the RegulatorNode receives a response from the LLM, THE RegulatorNode SHALL parse the response into `status` (one of `"CLEAR"`, `"WARNING"`, `"BLOCKED"`) and `reasoning` (str) fields.
6. WHEN the RegulatorNode returns a `status` of `"WARNING"`, THE RegulatorNode SHALL increment the `warning_count` field by 1.
7. WHEN the `warning_count` reaches 3, THE RegulatorNode SHALL set `deal_status` to `"Blocked"` regardless of the LLM response status.
8. WHEN the RegulatorNode returns a `status` of `"BLOCKED"`, THE RegulatorNode SHALL set `deal_status` to `"Blocked"`.
9. WHEN the RegulatorNode completes its turn, THE RegulatorNode SHALL append a new entry to the `history` list containing `agent_name`, `status`, `reasoning`, and `turn_number`.
10. IF the LLM response cannot be parsed into the required output schema, THEN THE RegulatorNode SHALL retry the LLM call once with an explicit formatting instruction appended to the prompt.

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
10. THE Orchestrator SHALL increment `turn_count` by 1 after each complete Buyer-Regulator-Seller-Regulator cycle.

### Requirement 7: Vertex AI Model Router

**User Story:** As a developer, I want a configuration-driven model router that maps each agent to a specific Vertex AI model, so that the system demonstrates LLM heterogeneity.

#### Acceptance Criteria

1. THE Model_Router SHALL maintain a mapping of agent role names to Vertex AI model identifiers.
2. THE Model_Router SHALL map the `"Buyer"` role to the `gemini-2.5-flash` model endpoint via the Vertex AI SDK.
3. THE Model_Router SHALL map the `"Seller"` role to the `claude-3-5-sonnet-v2` model endpoint via the Vertex AI SDK.
4. THE Model_Router SHALL map the `"Regulator"` role to the `claude-sonnet-4` model endpoint via the Vertex AI SDK, with a fallback to `gemini-2.5-pro`.
5. THE Model_Router SHALL accept the agent role name as input and return an initialized LLM client configured for the corresponding model.
6. THE Model_Router SHALL authenticate all Vertex AI API calls using GCP IAM credentials from the runtime environment, requiring no separate API keys.
7. WHEN a model endpoint is unavailable, THE Model_Router SHALL attempt the fallback model for that role before raising an error.
8. THE Model_Router SHALL pass the `GOOGLE_CLOUD_PROJECT` and `VERTEX_AI_LOCATION` configuration values to each LLM client instance.

### Requirement 8: Agent Output Parsing and Validation

**User Story:** As a developer, I want structured output parsing for all agent LLM responses, so that the orchestration layer can reliably extract and validate agent actions.

#### Acceptance Criteria

1. THE Orchestrator SHALL define a `BuyerOutput` Pydantic model containing `inner_thought` (str), `public_message` (str), and `proposed_price` (float) fields.
2. THE Orchestrator SHALL define a `SellerOutput` Pydantic model containing `inner_thought` (str), `public_message` (str), `proposed_price` (float), and `retention_clause_demanded` (bool) fields.
3. THE Orchestrator SHALL define a `RegulatorOutput` Pydantic model containing `status` (str, constrained to `"CLEAR"`, `"WARNING"`, or `"BLOCKED"`) and `reasoning` (str) fields.
4. WHEN an LLM response is received, THE Orchestrator SHALL parse the response text as JSON and validate it against the corresponding Pydantic model.
5. IF the LLM response JSON is invalid or missing required fields, THEN THE Orchestrator SHALL raise a `AgentOutputParseError` with the agent name and raw response text.
6. FOR ALL valid BuyerOutput instances, serializing to JSON then deserializing back SHALL produce an equivalent BuyerOutput object (round-trip property).
7. FOR ALL valid SellerOutput instances, serializing to JSON then deserializing back SHALL produce an equivalent SellerOutput object (round-trip property).
8. FOR ALL valid RegulatorOutput instances, serializing to JSON then deserializing back SHALL produce an equivalent RegulatorOutput object (round-trip property).

### Requirement 9: Negotiation Termination Conditions

**User Story:** As a developer, I want clearly defined termination conditions for the negotiation loop, so that the simulation always reaches a definitive outcome.

#### Acceptance Criteria

1. WHEN both the Buyer's `proposed_price` and the Seller's `proposed_price` are within €1M of each other and the Seller's `retention_clause_demanded` is satisfied, THE Orchestrator SHALL set `deal_status` to `"Agreed"`.
2. WHEN `turn_count` reaches `max_turns` and `deal_status` remains `"Negotiating"`, THE Orchestrator SHALL set `deal_status` to `"Failed"`.
3. WHEN the RegulatorNode sets `deal_status` to `"Blocked"`, THE Orchestrator SHALL terminate the negotiation loop.
4. WHEN `deal_status` transitions from `"Negotiating"` to a terminal state, THE Orchestrator SHALL record the final `deal_status`, `current_offer`, `turn_count`, and `warning_count` in the NegotiationState.
5. THE Orchestrator SHALL verify that `deal_status` is one of `"Negotiating"`, `"Agreed"`, `"Blocked"`, or `"Failed"` at every state transition.

### Requirement 10: Graph Compilation and Execution Entry Point

**User Story:** As a developer, I want a single entry point to compile and execute the negotiation graph, so that the FastAPI endpoint can trigger a full negotiation run.

#### Acceptance Criteria

1. THE Orchestrator SHALL provide a `build_graph()` function that constructs and compiles the StateGraph with all nodes and edges.
2. THE Orchestrator SHALL provide a `run_negotiation(initial_state: NegotiationState)` async function that executes the compiled graph from the initial state to completion.
3. WHEN `run_negotiation` is called, THE Orchestrator SHALL yield intermediate NegotiationState snapshots after each node execution, enabling SSE streaming.
4. WHEN the graph execution completes, THE `run_negotiation` function SHALL return the final NegotiationState.
5. IF an unrecoverable error occurs during graph execution, THEN THE Orchestrator SHALL set `deal_status` to `"Failed"`, log the error with the `session_id`, and return the error state.
