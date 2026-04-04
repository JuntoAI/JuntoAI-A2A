# Requirements Document: Agent Gateway API & Remote Agent Node

## Introduction

An HTTP-based Agent Gateway that allows external AI agents — built on any framework (CrewAI, AutoGen, OpenClaw, custom Python/Node/Go) — to participate in JuntoAI negotiations alongside local LLM-powered agents. The gateway defines a simple `POST /agent/turn` contract that external agents implement. Internally, the LangGraph orchestrator gains a `RemoteAgentNode` that calls external endpoints instead of invoking a local LLM. The scenario JSON `AgentDefinition` gains an optional `endpoint` field: when present, the agent is remote; when absent, the agent is local (existing behavior). This is the foundational spec that makes JuntoAI an open platform rather than a closed LLM orchestrator.

## Glossary

- **Remote_Agent**: An AI agent hosted externally that implements the Agent Gateway HTTP contract and participates in negotiations via HTTP calls
- **Local_Agent**: The existing LLM-powered agent that runs inside the LangGraph process via `create_agent_node` (current behavior, unchanged)
- **Agent_Gateway_Contract**: The HTTP request/response schema that external agents must implement to participate in negotiations
- **RemoteAgentNode**: A new LangGraph node type that calls an external HTTP endpoint instead of invoking a local LLM
- **Turn_Payload**: The JSON request body sent to a remote agent containing conversation history, current state, agent config, and turn metadata
- **Turn_Response**: The JSON response body returned by a remote agent containing the agent's output (inner_thought, public_message, proposed_price for negotiators; status, reasoning for regulators; observation, recommendation for observers)
- **Agent_Execution_Mode**: Either `local` (LLM call inside process) or `remote` (HTTP call to external endpoint), determined by presence of `endpoint` field in AgentDefinition

## Requirements

### Requirement 1: AgentDefinition Schema Extension

**User Story:** As a scenario author, I want to specify an external endpoint URL for an agent, so that the orchestrator calls a remote service instead of a local LLM.

#### Acceptance Criteria

1. THE `AgentDefinition` Pydantic model SHALL gain an optional field `endpoint: str | None = None` that accepts a valid HTTP or HTTPS URL
2. WHEN `endpoint` is `None` (default), THE orchestrator SHALL use the existing local LLM execution path via `model_router.get_model` (backward compatible — no behavior change for existing scenarios)
3. WHEN `endpoint` is a non-empty string, THE orchestrator SHALL treat the agent as remote and use the `RemoteAgentNode` execution path
4. WHEN `endpoint` is present, THE `model_id` field SHALL still be required in the schema but SHALL be ignored during execution (it serves as documentation of what model the remote agent uses)
5. ALL existing scenario JSON files SHALL continue to validate and function identically without modification (zero breaking changes)

### Requirement 2: Agent Gateway HTTP Contract — Request

**User Story:** As an external developer, I want a clear, documented request format, so that I know exactly what data my agent will receive each turn.

#### Acceptance Criteria

1. THE Turn_Payload SHALL be a JSON object sent as the body of a `POST` request to the remote agent's endpoint URL
2. THE Turn_Payload SHALL include the following fields:
   - `agent_role`: string — the agent's role in this negotiation
   - `agent_type`: string — one of "negotiator", "regulator", "observer"
   - `agent_name`: string — the agent's display name
   - `turn_number`: integer — the current turn count
   - `max_turns`: integer — the maximum number of turns
   - `current_offer`: float — the current price/value on the table
   - `history`: array of objects — the conversation history, each entry containing `role` (string) and `content` (object with `public_message` or `reasoning` or `observation`)
   - `agent_config`: object — the full agent configuration from the scenario (persona_prompt, goals, budget, tone)
   - `negotiation_params`: object — the scenario's negotiation parameters (agreement_threshold, value_label, value_format)
3. THE Turn_Payload SHALL NOT include `hidden_context` for agents other than the target agent (hidden context is injected into the agent_config for the target agent only, same as local agents)
4. THE Turn_Payload SHALL include a `schema_version` field set to `"1.0"` to support future contract evolution

### Requirement 3: Agent Gateway HTTP Contract — Response

**User Story:** As an external developer, I want a clear response format, so that I know exactly what my agent must return.

#### Acceptance Criteria

1. THE Turn_Response SHALL be a JSON object returned in the HTTP response body with status 200
2. FOR agents with `agent_type` "negotiator", THE Turn_Response SHALL include: `inner_thought` (string), `public_message` (string), `proposed_price` (float), and optionally `extra_fields` (object)
3. FOR agents with `agent_type` "regulator", THE Turn_Response SHALL include: `status` (string, one of "CLEAR", "WARNING", "BLOCKED") and `reasoning` (string)
4. FOR agents with `agent_type` "observer", THE Turn_Response SHALL include: `observation` (string) and optionally `recommendation` (string)
5. IF the remote agent returns a non-200 HTTP status, THE RemoteAgentNode SHALL treat it as a failure and use the existing `_fallback_output` mechanism
6. IF the remote agent returns a 200 status but the response body fails Pydantic validation against the expected output model, THE RemoteAgentNode SHALL log the error and use `_fallback_output`

### Requirement 4: RemoteAgentNode Implementation

**User Story:** As the orchestrator, I want to seamlessly call remote agents within the existing LangGraph flow, so that remote and local agents can coexist in the same negotiation.

#### Acceptance Criteria

1. THE `create_agent_node` function SHALL detect whether an agent has an `endpoint` field and route to either the existing local LLM path or the new remote HTTP path
2. THE RemoteAgentNode SHALL construct the Turn_Payload from the current `NegotiationState`, send it as a `POST` request to the agent's endpoint, and parse the Turn_Response
3. THE RemoteAgentNode SHALL enforce a configurable timeout (default 30 seconds) on the HTTP call. If the timeout is exceeded, THE RemoteAgentNode SHALL use `_fallback_output`
4. THE RemoteAgentNode SHALL update `NegotiationState` identically to a local agent: append to history, update agent_states, advance turn order, update current_offer for negotiators
5. THE RemoteAgentNode SHALL NOT track `tokens_used` for remote agents (token tracking is the remote agent's responsibility). It SHALL report 0 tokens for remote agent turns
6. THE RemoteAgentNode SHALL use `httpx.AsyncClient` for HTTP calls with connection pooling
7. THE RemoteAgentNode SHALL include a `User-Agent: JuntoAI-A2A/1.0` header and a `X-JuntoAI-Session-Id` header containing the session_id on all outbound requests

### Requirement 5: Mixed Local/Remote Negotiation Support

**User Story:** As a scenario author, I want to mix local LLM agents and remote agents in the same scenario, so that I can gradually migrate agents or test external agents against local ones.

#### Acceptance Criteria

1. THE orchestrator SHALL support scenarios where some agents have `endpoint` set (remote) and others do not (local), executing each agent via its appropriate path
2. THE turn order, agreement detection, stall detection, and all other orchestration logic SHALL function identically regardless of whether agents are local or remote
3. THE `NegotiationState.history` entries from remote agents SHALL be indistinguishable from local agent entries (same structure, same fields)
4. THE SSE events streamed to the frontend SHALL be identical for remote and local agents — the frontend SHALL NOT need to know whether an agent is local or remote

### Requirement 6: Remote Agent Error Handling

**User Story:** As the orchestrator, I want robust error handling for remote agent failures, so that a single broken external agent doesn't crash the entire negotiation.

#### Acceptance Criteria

1. IF a remote agent's endpoint is unreachable (connection refused, DNS failure), THE RemoteAgentNode SHALL log the error and use `_fallback_output` for that turn
2. IF a remote agent returns an HTTP error status (4xx, 5xx), THE RemoteAgentNode SHALL log the status code and response body (truncated to 500 chars) and use `_fallback_output`
3. IF a remote agent's response is not valid JSON, THE RemoteAgentNode SHALL log the raw response (truncated to 500 chars) and use `_fallback_output`
4. THE RemoteAgentNode SHALL retry once on timeout or 5xx errors before falling back. It SHALL NOT retry on 4xx errors (client errors indicate a bug in the remote agent)
5. THE RemoteAgentNode SHALL include the error details in the history entry's content as `[{agent_name} encountered a communication error]` so the conversation flow remains coherent
6. ALL remote agent errors SHALL be logged at WARNING level with the agent role, endpoint URL, error type, and truncated response

### Requirement 7: Endpoint Validation at Scenario Load Time

**User Story:** As a scenario author, I want the system to validate remote agent endpoints when a scenario is loaded, so that I get early feedback about misconfigured agents.

#### Acceptance Criteria

1. WHEN a scenario with remote agents is loaded, THE system SHALL validate that each `endpoint` field is a well-formed HTTP or HTTPS URL
2. THE URL validation SHALL reject non-HTTP(S) schemes, empty strings, and malformed URLs at Pydantic validation time
3. THE system SHALL NOT perform a live connectivity check at scenario load time (the endpoint may not be running yet). Live checks happen only at negotiation start time (Requirement 8)

### Requirement 8: Pre-Negotiation Endpoint Health Check

**User Story:** As a user, I want to know before a negotiation starts whether all remote agents are reachable, so that I don't waste tokens on a negotiation that will fail.

#### Acceptance Criteria

1. WHEN a negotiation is initialized with a scenario containing remote agents, THE Scenario_Builder_API SHALL perform a health check on each remote agent endpoint before starting the LangGraph execution
2. THE health check SHALL send a `GET` request to the remote agent's endpoint URL. A 200 response indicates the agent is ready
3. IF any remote agent endpoint fails the health check, THE API SHALL return an error response listing the unreachable endpoints and SHALL NOT start the negotiation
4. THE health check SHALL enforce a 5-second timeout per endpoint
5. THE health check results SHALL be included in the `StartNegotiationResponse` as a new optional field `agent_health: list[{role: str, status: str, endpoint: str}]`

### Requirement 9: Configuration for Remote Agent Timeouts

**User Story:** As a platform operator, I want to configure timeout values for remote agent calls, so that I can tune performance for different deployment environments.

#### Acceptance Criteria

1. THE `Settings` class SHALL gain a `REMOTE_AGENT_TIMEOUT_SECONDS: float = 30.0` field for the per-turn HTTP call timeout
2. THE `Settings` class SHALL gain a `REMOTE_AGENT_HEALTH_CHECK_TIMEOUT_SECONDS: float = 5.0` field for the pre-negotiation health check timeout
3. BOTH timeout values SHALL be configurable via environment variables
