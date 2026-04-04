# Requirements Document: Developer Agent SDK & Documentation

## Dependency

This spec depends on **Spec 200 (Agent Gateway API & Remote Agent Node)** being fully implemented. The SDK wraps the Agent Gateway HTTP contract defined in Spec 200. It also depends on **Spec 210 (Agent Registration & Validation)** for the registration flow documentation, though the SDK itself can be built in parallel with Spec 210.

## Introduction

A lightweight Python SDK and comprehensive documentation package that enables external developers to build, test, and deploy AI agents compatible with the JuntoAI Agent Gateway. The SDK provides base classes, type definitions, a local test harness, and a "hello world" template agent. The documentation includes an OpenAPI spec for the Agent Gateway contract, a quickstart guide, and architecture diagrams. The goal is to reduce the barrier to building a compatible agent from "read the source code" to "pip install, subclass, deploy" in under 30 minutes.

## Glossary

- **Agent_SDK**: The Python package (`juntoai-agent-sdk`) that provides base classes, types, and utilities for building JuntoAI-compatible remote agents
- **BaseAgent**: The abstract base class in the SDK that developers subclass to implement their agent logic
- **Test_Harness**: A local testing tool included in the SDK that simulates the JuntoAI orchestrator sending Turn_Payloads to a developer's agent and validating Turn_Responses
- **Template_Agent**: A complete, runnable example agent included in the SDK that demonstrates all three agent types (negotiator, regulator, observer)
- **OpenAPI_Spec**: The OpenAPI 3.1 specification document describing the Agent Gateway HTTP contract
- **Agent_Server**: A lightweight HTTP server wrapper (FastAPI-based) included in the SDK that handles the HTTP plumbing so developers only write agent logic

## Requirements

### Requirement 1: SDK Package Structure

**User Story:** As an external developer, I want to install a single Python package that gives me everything I need to build a JuntoAI agent.

#### Acceptance Criteria

1. THE SDK SHALL be a Python package named `juntoai-agent-sdk` installable via `pip install juntoai-agent-sdk`
2. THE SDK SHALL be hosted in a `sdk/` directory at the root of the JuntoAI monorepo with its own `pyproject.toml`, `README.md`, and `src/juntoai_agent_sdk/` source directory
3. THE SDK SHALL have minimal dependencies: `pydantic>=2.0`, `fastapi>=0.100`, `uvicorn>=0.20`, `httpx>=0.24` — no LangChain, no LangGraph, no GCP dependencies
4. THE SDK SHALL support Python 3.10+
5. THE SDK SHALL include type stubs and be fully typed (passing `mypy --strict`)

### Requirement 2: Type Definitions

**User Story:** As an external developer, I want typed request/response models, so that my IDE gives me autocomplete and my code catches type errors before deployment.

#### Acceptance Criteria

1. THE SDK SHALL export Pydantic models for the Turn_Payload: `TurnPayload` with fields matching Spec 200 Requirement 2 (agent_role, agent_type, agent_name, turn_number, max_turns, current_offer, history, agent_config, negotiation_params, schema_version)
2. THE SDK SHALL export Pydantic models for each Turn_Response type: `NegotiatorResponse` (inner_thought, public_message, proposed_price, extra_fields), `RegulatorResponse` (status, reasoning), `ObserverResponse` (observation, recommendation)
3. THE SDK SHALL export supporting types: `AgentConfig` (persona_prompt, goals, budget, tone), `Budget` (min, max, target), `HistoryEntry` (role, content), `NegotiationParams` (agreement_threshold, value_label, value_format, max_turns)
4. ALL exported types SHALL be importable from `juntoai_agent_sdk.types`
5. THE SDK types SHALL be kept in sync with the backend Pydantic models. The SDK `NegotiatorResponse` fields SHALL exactly match `NegotiatorOutput` from `backend/app/orchestrator/outputs.py`

### Requirement 3: BaseAgent Abstract Class

**User Story:** As an external developer, I want a simple base class to subclass, so that I only write the agent logic and the SDK handles HTTP plumbing.

#### Acceptance Criteria

1. THE SDK SHALL provide a `BaseAgent` abstract class importable from `juntoai_agent_sdk`
2. `BaseAgent` SHALL require subclasses to implement a single method: `async def on_turn(self, payload: TurnPayload) -> NegotiatorResponse | RegulatorResponse | ObserverResponse`
3. `BaseAgent` SHALL accept a `name: str` and `supported_types: list[str]` in its constructor
4. `BaseAgent` SHALL provide a `run(host: str = "0.0.0.0", port: int = 8080)` method that starts a FastAPI server exposing the agent at `POST /` and a health check at `GET /`
5. THE `GET /` health check endpoint SHALL return `{"status": "ok", "name": "<agent_name>", "supported_types": [...]}` with HTTP 200
6. THE `POST /` endpoint SHALL deserialize the request body as `TurnPayload`, call `on_turn`, serialize the response, and return HTTP 200. On any exception in `on_turn`, it SHALL return HTTP 500 with `{"error": "<message>"}`

### Requirement 4: Agent Server Wrapper

**User Story:** As an external developer, I want the HTTP server to be production-ready out of the box, so that I can deploy my agent without writing server code.

#### Acceptance Criteria

1. THE Agent_Server SHALL use FastAPI with uvicorn as the ASGI server
2. THE Agent_Server SHALL include CORS middleware allowing all origins (agents are called server-to-server by the orchestrator)
3. THE Agent_Server SHALL include request logging middleware that logs: timestamp, method, path, status code, and response time
4. THE Agent_Server SHALL include a `/health` endpoint that returns `{"status": "ok"}` (alias for `GET /`)
5. THE Agent_Server SHALL be configurable via environment variables: `AGENT_HOST` (default "0.0.0.0"), `AGENT_PORT` (default 8080), `AGENT_LOG_LEVEL` (default "info")
6. THE Agent_Server SHALL include a `Dockerfile` template in the SDK examples directory for containerized deployment

### Requirement 5: Local Test Harness

**User Story:** As an external developer, I want to test my agent locally without connecting to JuntoAI, so that I can iterate quickly during development.

#### Acceptance Criteria

1. THE SDK SHALL include a `TestHarness` class importable from `juntoai_agent_sdk.testing`
2. THE `TestHarness` SHALL accept a `BaseAgent` instance and simulate a multi-turn negotiation by sending synthetic Turn_Payloads and collecting Turn_Responses
3. THE `TestHarness` SHALL validate each Turn_Response against the appropriate Pydantic model and report validation errors
4. THE `TestHarness` SHALL support configurable scenarios: number of turns, agent type to test, initial offer, history seed
5. THE `TestHarness` SHALL produce a summary report: number of turns executed, all responses collected, any validation failures, and whether the agent's proposed_prices showed movement (not stuck at the same value)
6. THE `TestHarness` SHALL be runnable as a CLI command: `juntoai-test --agent my_agent:MyAgent --type negotiator --turns 5`

### Requirement 6: Template Agent Examples

**User Story:** As an external developer, I want working example agents, so that I can copy-paste and modify rather than starting from scratch.

#### Acceptance Criteria

1. THE SDK SHALL include a `examples/` directory with at least 3 template agents:
   - `simple_negotiator.py` — a negotiator that makes incremental concessions toward a target price
   - `simple_regulator.py` — a regulator that issues warnings when offers exceed a threshold
   - `simple_observer.py` — an observer that summarizes the negotiation state
2. EACH template agent SHALL be a complete, runnable Python file (under 100 lines) that subclasses `BaseAgent` and implements `on_turn`
3. EACH template agent SHALL include inline comments explaining the key decisions and how to customize the logic
4. THE SDK SHALL include a `examples/llm_negotiator.py` that demonstrates wrapping an LLM call (OpenAI or Anthropic) inside a `BaseAgent` — showing how to use the SDK with any LLM provider
5. ALL example agents SHALL pass the `TestHarness` validation when run with default settings

### Requirement 7: OpenAPI Specification

**User Story:** As an external developer using any language (not just Python), I want a machine-readable API spec, so that I can generate client/server code in my preferred language.

#### Acceptance Criteria

1. THE SDK SHALL include an `openapi.yaml` file in the repository root describing the Agent Gateway HTTP contract
2. THE OpenAPI spec SHALL define the `POST /` endpoint with the `TurnPayload` request body schema and all three response schemas (negotiator, regulator, observer) using `oneOf` discriminated by `agent_type` in the request
3. THE OpenAPI spec SHALL define the `GET /` health check endpoint
4. THE OpenAPI spec SHALL include example request/response pairs for each agent type
5. THE OpenAPI spec SHALL use OpenAPI 3.1 format and be valid per the OpenAPI specification

### Requirement 8: Quickstart Documentation

**User Story:** As an external developer, I want a step-by-step guide to go from zero to a working agent in under 30 minutes.

#### Acceptance Criteria

1. THE SDK SHALL include a `docs/quickstart.md` that walks through: install the SDK, create a negotiator agent, test it locally with the TestHarness, deploy it (Docker), register it with JuntoAI (Spec 210), and run a negotiation with it
2. THE quickstart SHALL include copy-pasteable code blocks for each step
3. THE quickstart SHALL include a "What happens under the hood" section explaining the Turn_Payload → on_turn → Turn_Response flow with a sequence diagram
4. THE SDK `README.md` SHALL include a condensed version of the quickstart (install + 10-line example + run)

### Requirement 9: Architecture Documentation

**User Story:** As an external developer, I want to understand how my agent fits into the JuntoAI system, so that I can make informed design decisions.

#### Acceptance Criteria

1. THE SDK SHALL include a `docs/architecture.md` that explains: the JuntoAI orchestrator (LangGraph), how remote agents are called (RemoteAgentNode from Spec 200), the Turn_Payload/Turn_Response contract, error handling and fallback behavior, and how mixed local/remote negotiations work
2. THE architecture doc SHALL include a sequence diagram showing: orchestrator → RemoteAgentNode → HTTP POST → remote agent → HTTP response → state update → next turn
3. THE architecture doc SHALL include a section on "Designing Good Agents" with guidance on: response time targets (under 10 seconds recommended), stateless vs stateful agents, handling conversation history, and price movement strategies to avoid stall detection
