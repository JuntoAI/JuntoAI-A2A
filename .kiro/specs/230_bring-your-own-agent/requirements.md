# Requirements Document: Bring Your Own Agent (BYOA)

## Dependencies

This spec depends on:
- **Spec 200 (Agent Gateway API)**: The HTTP contract (`TurnPayload`/`TurnResponse`), `endpoint` field on `AgentDefinition`, health checks, retry/fallback. BYOA is the end-user workflow that exercises this plumbing.
- **Spec 220 (Developer Agent SDK)**: The `juntoai-agent-sdk` Python package with `BaseAgent`, types, test harness, and template agents. BYOA documentation references the SDK as the primary tool for building agents.

Optional dependency:
- **Spec 210 (Agent Registration & Validation)**: The agent registry API. BYOA can work without registration (paste endpoint URL directly), but registered agents get a smoother UX.

## Introduction

The end-to-end workflow and tooling that enables an external developer to build a custom AI agent, run it locally or in the cloud, connect it to the JuntoAI platform, and participate in live negotiations alongside JuntoAI's built-in agents. This spec covers the "last mile" that Specs 200 and 220 don't: the Arena UI for assigning external agents to scenario roles, the Docker Compose setup for local development, tunneling guides for connecting local agents to the cloud platform, endpoint validation UX, and security guardrails for external agent endpoints. Without this spec, a developer has the SDK and the gateway contract but no way to actually wire their agent into a negotiation through the UI.

## Glossary

- **BYOA_Flow**: The end-to-end user journey from building an agent locally to running it in a live JuntoAI negotiation
- **Endpoint_Input**: A UI component in the Arena Selector that allows a user to paste a remote agent's HTTP(S) URL and assign it to a specific agent role in a scenario
- **Tunnel**: A tool (ngrok, Cloudflare Tunnel, or similar) that exposes a locally running agent on a public URL so the JuntoAI cloud orchestrator can reach it
- **Agent_Compose_Stack**: A Docker Compose configuration that runs one or more custom agents alongside the JuntoAI local stack for development and testing
- **Endpoint_Validation_Check**: A real-time health + contract probe triggered from the Arena UI when a user submits an endpoint URL, verifying the agent is reachable and returns a valid Turn_Response before the negotiation starts
- **BYOA_Guide**: The comprehensive developer documentation covering the full BYOA workflow from agent creation to live negotiation
- **Role_Override**: The act of replacing a scenario's default local agent with an external agent for a specific role (e.g., replacing the built-in "Candidate" with a custom agent at `https://my-agent.ngrok.io`)

## Requirements

### Requirement 1: Arena UI — External Agent Endpoint Input

**User Story:** As a developer, I want to paste my agent's endpoint URL into the Arena Selector and assign it to a scenario role, so that my custom agent participates in the negotiation instead of the built-in one.

#### Acceptance Criteria

1. WHEN a scenario is loaded in the Arena Selector, EACH AgentCard SHALL display a "Use External Agent" toggle button with `data-testid="byoa-toggle-{role}"`
2. WHEN the user activates the "Use External Agent" toggle for an agent role, THE AgentCard SHALL reveal a text input field for the endpoint URL with `data-testid="byoa-endpoint-{role}"` and a "Validate" button with `data-testid="byoa-validate-{role}"`
3. THE Endpoint_Input field SHALL accept only valid HTTP or HTTPS URLs. WHEN the user enters an invalid URL, THE system SHALL display an inline validation error below the input field
4. WHEN the user clicks "Validate", THE system SHALL send a health check request to the endpoint (via the backend) and display the result: a green checkmark icon for healthy, a red error icon with a message for unhealthy or unreachable
5. WHEN an external agent endpoint is validated successfully for a role, THE AgentCard SHALL visually indicate the role is overridden (distinct border color or badge with `data-testid="byoa-active-badge-{role}"`)
6. THE user SHALL be able to deactivate the "Use External Agent" toggle to revert to the built-in agent for that role at any time before starting the negotiation
7. WHEN the "Initialize A2A Protocol" button is clicked with one or more external agent overrides, THE `startNegotiation` API call SHALL include the endpoint URLs in the request payload mapped to their respective agent roles

### Requirement 2: Backend — Endpoint Override in Negotiation Start

**User Story:** As the platform, I want to accept endpoint overrides at negotiation start time, so that the orchestrator uses external agents for the specified roles.

#### Acceptance Criteria

1. THE `POST /api/v1/negotiate` endpoint SHALL accept an optional `endpoint_overrides` field: a dict mapping agent role strings to endpoint URL strings
2. WHEN `endpoint_overrides` is provided, THE system SHALL validate each URL using the same Pydantic validator as `AgentDefinition.endpoint` (HTTP/HTTPS scheme, valid host)
3. WHEN `endpoint_overrides` is provided, THE system SHALL merge the overrides into the scenario's `AgentDefinition` objects before constructing the LangGraph graph — setting the `endpoint` field on the matching agent roles
4. IF an `endpoint_overrides` key does not match any agent role in the scenario, THE system SHALL return HTTP 422 with a message identifying the invalid role
5. THE pre-negotiation health check (Spec 200, Requirement 8) SHALL run for all overridden endpoints before starting the negotiation
6. WHEN a negotiation starts with endpoint overrides, THE session document SHALL record which roles were overridden and their endpoint URLs for audit and debugging

### Requirement 3: Endpoint Validation API

**User Story:** As a developer, I want to validate my agent endpoint from the Arena UI before starting a negotiation, so that I get immediate feedback on connectivity and contract compliance.

#### Acceptance Criteria

1. THE system SHALL expose a `POST /api/v1/agents/validate-endpoint` endpoint that accepts `endpoint` (string, required) and `agent_type` (string, required, one of "negotiator", "regulator", "observer")
2. WHEN a validation request is received, THE system SHALL first perform a health check (GET request with 5-second timeout) to verify the endpoint is reachable
3. WHEN the health check succeeds, THE system SHALL send a synthetic Turn_Payload (matching the contract from Spec 200) to the endpoint and validate the Turn_Response against the appropriate Pydantic output model for the declared agent_type
4. THE validation response SHALL include: `reachable` (boolean), `contract_valid` (boolean), `response_time_ms` (integer), and `errors` (array of strings describing any failures)
5. IF the endpoint is unreachable, THE system SHALL return `reachable: false` with the connection error in the `errors` array
6. IF the endpoint is reachable but the Turn_Response fails Pydantic validation, THE system SHALL return `contract_valid: false` with specific field-level validation errors in the `errors` array

### Requirement 4: Docker Compose — Agent Development Stack

**User Story:** As a developer, I want a Docker Compose setup that runs my custom agent alongside the JuntoAI local stack, so that I can develop and test end-to-end without any cloud dependency.

#### Acceptance Criteria

1. THE project SHALL include a `docker-compose.byoa.yml` override file that extends the existing `docker-compose.yml` with a `custom-agent` service definition
2. THE `custom-agent` service SHALL build from a `byoa/` directory at the monorepo root containing a `Dockerfile`, `requirements.txt`, and a `my_agent.py` starter file that subclasses `BaseAgent` from the SDK
3. THE `custom-agent` service SHALL be accessible to the `backend` service via Docker networking at `http://custom-agent:8080`
4. THE `docker-compose.byoa.yml` SHALL include environment variable `CUSTOM_AGENT_ENDPOINT=http://custom-agent:8080` that can be referenced when configuring scenarios
5. THE `byoa/` directory SHALL include a `README.md` with step-by-step instructions for: modifying the agent logic, rebuilding the container, and running a negotiation with the custom agent
6. WHEN a developer runs `docker compose -f docker-compose.yml -f docker-compose.byoa.yml up`, THE full stack (Ollama, backend, frontend, custom-agent) SHALL start and the custom agent SHALL be reachable from the backend

### Requirement 5: Tunneling Guide for Cloud Connection

**User Story:** As a developer, I want clear instructions for exposing my local agent to the JuntoAI cloud platform, so that I can test my agent against the production orchestrator without deploying to a server.

#### Acceptance Criteria

1. THE BYOA_Guide SHALL include a "Connect to Cloud" section with step-by-step instructions for exposing a local agent using ngrok (primary) and Cloudflare Tunnel (alternative)
2. THE ngrok instructions SHALL cover: installing ngrok, running `ngrok http 8080`, copying the generated public URL, and pasting it into the Arena Selector Endpoint_Input
3. THE Cloudflare Tunnel instructions SHALL cover: installing cloudflared, creating a tunnel, and mapping it to the local agent port
4. THE guide SHALL include a troubleshooting section covering common issues: ngrok free tier URL changes on restart, firewall blocking, HTTPS certificate errors, and timeout tuning for high-latency tunnels
5. THE guide SHALL include a warning that tunnel URLs are temporary and should not be used for production deployments — with a pointer to cloud deployment options (Cloud Run, Railway, Fly.io)

### Requirement 6: BYOA Developer Guide

**User Story:** As a developer, I want a single comprehensive guide that walks me through the entire BYOA workflow from zero to a live negotiation, so that I don't have to piece together information from multiple specs.

#### Acceptance Criteria

1. THE project SHALL include a `docs/byoa-guide.md` document covering the complete BYOA workflow
2. THE guide SHALL include these sections in order: Prerequisites, Quick Start (5-minute path), Build Your Agent (SDK usage), Test Locally (test harness + Docker Compose), Connect to JuntoAI (tunneling or deployment), Run a Negotiation (Arena UI walkthrough), and Troubleshooting
3. THE Quick Start section SHALL provide a copy-pasteable sequence of commands that gets a developer from zero to a running negotiation in under 5 minutes using the template agent and Docker Compose
4. THE Build Your Agent section SHALL reference the SDK documentation (Spec 220) and include a minimal negotiator example (under 30 lines) that demonstrates the `on_turn` method
5. THE Run a Negotiation section SHALL include annotated screenshots or step descriptions of the Arena UI flow: select scenario, toggle "Use External Agent", paste endpoint, validate, and initialize
6. THE Troubleshooting section SHALL cover: agent not reachable (firewall, wrong port), contract validation failures (wrong response schema), timeout errors (agent too slow), and fallback behavior (what happens when the agent fails mid-negotiation)

### Requirement 7: Security — External Endpoint Guardrails

**User Story:** As the platform, I want to enforce security guardrails on external agent endpoints, so that malicious or misconfigured endpoints cannot harm the platform or other users.

#### Acceptance Criteria

1. THE system SHALL reject endpoint URLs that resolve to private/internal IP ranges (10.x.x.x, 172.16-31.x.x, 192.168.x.x, 127.x.x.x, ::1, fc00::/7) to prevent Server-Side Request Forgery (SSRF). This validation SHALL occur at negotiation start time after DNS resolution
2. THE system SHALL enforce a per-session rate limit on outbound calls to any single external endpoint: a maximum of 1 request per 2 seconds per endpoint to prevent the orchestrator from being used as a DDoS amplifier
3. THE system SHALL enforce a maximum response body size of 1 MB for Turn_Responses from external agents. Responses exceeding this limit SHALL be treated as errors and trigger fallback
4. THE system SHALL strip any cookies or authentication headers from outbound requests to external agents — only `User-Agent`, `Content-Type`, `X-JuntoAI-Session-Id`, and `X-JuntoAI-Schema-Version` headers SHALL be sent
5. THE system SHALL log all outbound requests to external endpoints at INFO level with: session_id, agent_role, endpoint (with path only, no query params), response status, and response time — for security audit purposes
6. WHEN running in cloud mode, THE system SHALL reject `http://` (non-TLS) endpoints and require `https://` for all external agent URLs. WHEN running in local mode, THE system SHALL allow both `http://` and `https://`

### Requirement 8: End-to-End Testing Documentation

**User Story:** As a developer, I want a testing checklist that verifies my agent works correctly in all scenarios, so that I can ship with confidence.

#### Acceptance Criteria

1. THE BYOA_Guide SHALL include a "Testing Checklist" section with verification steps for each stage of the BYOA workflow
2. THE checklist SHALL include: health check passes (GET returns 200), contract validation passes for each supported agent type, agent responds within 30 seconds, agent produces valid price movement (for negotiators), agent handles edge cases (turn 1 with empty history, max_turns reached)
3. THE BYOA_Guide SHALL include a "Common Mistakes" section documenting the top failure modes: returning wrong response schema for agent type, not handling empty history on turn 1, proposed_price outside budget range causing stall detection, and response time exceeding timeout
4. THE project SHALL include an integration test in `backend/tests/integration/test_byoa_flow.py` that exercises the full BYOA flow: create a mock external agent (using respx), start a negotiation with an endpoint override, run 3 turns, and verify the external agent's responses appear in the session history

