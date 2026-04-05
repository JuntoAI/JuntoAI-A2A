# Implementation Plan: Bring Your Own Agent (BYOA)

## Overview

Implementation follows a dependency-ordered approach: backend security primitives first (SSRF guard, header stripping, response size guard), then the validation API and negotiation endpoint extensions, then frontend UI, then Docker Compose dev stack, and finally documentation. Each layer builds on the previous one so there's no orphaned code.

## Tasks

- [ ] 1. Backend security primitives
  - [ ] 1.1 Create SSRF guard module (`backend/app/services/ssrf_guard.py`)
    - Implement `check_ssrf(url: str) -> str | None` that resolves hostname via `socket.getaddrinfo` and checks resolved IPs against private/internal ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16, ::1/128, fc00::/7, fe80::/10)
    - Return error message string if blocked, `None` if safe
    - _Requirements: 7.1_

  - [ ]* 1.2 Write property test for SSRF private IP rejection
    - **Property 5: SSRF Private IP Rejection**
    - Generate random IPv4 addresses via `st.tuples(st.integers(0,255), ...)`, classify as private/public, mock DNS resolution, verify `check_ssrf` returns error for private and `None` for public
    - Test file: `backend/tests/property/test_byoa_properties.py`
    - **Validates: Requirements 7.1**

  - [ ] 1.3 Add outbound header builder to `backend/app/orchestrator/agent_node.py`
    - Add `ALLOWED_OUTBOUND_HEADERS` dict and `build_outbound_headers(session_id, schema_version)` function
    - Returns exactly `User-Agent`, `Content-Type`, `X-JuntoAI-Session-Id`, `X-JuntoAI-Schema-Version` — no other headers
    - _Requirements: 7.4_

  - [ ]* 1.4 Write property test for outbound header allowlist
    - **Property 7: Outbound Header Allowlist**
    - Generate random session IDs and schema versions via `st.text()`, call `build_outbound_headers`, verify exactly 4 keys present with correct values
    - Test file: `backend/tests/property/test_byoa_properties.py`
    - **Validates: Requirements 7.4**

  - [ ] 1.5 Add response size guard to `backend/app/orchestrator/agent_node.py`
    - Implement `_read_response_with_limit(response)` that raises `ValueError` if body exceeds 1,048,576 bytes (1 MB)
    - _Requirements: 7.3_

  - [ ]* 1.6 Write property test for response size limit enforcement
    - **Property 6: Response Size Limit Enforcement**
    - Generate random byte lengths via `st.integers(0, 2_000_000)`, create mock responses, verify raises for >1MB and succeeds for ≤1MB
    - Test file: `backend/tests/property/test_byoa_properties.py`
    - **Validates: Requirements 7.3**

  - [ ] 1.7 Add BYOA settings to `backend/app/config.py`
    - Add `BYOA_SSRF_CHECK_ENABLED: bool = True`, `BYOA_MAX_RESPONSE_SIZE_BYTES: int = 1_048_576`, `BYOA_RATE_LIMIT_INTERVAL_SECONDS: float = 2.0`
    - _Requirements: 7.1, 7.2, 7.3_

- [ ] 2. Checkpoint — Security primitives
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Backend endpoint validation API and negotiation start extension
  - [ ] 3.1 Create agents router (`backend/app/routers/agents.py`)
    - Implement `POST /agents/validate-endpoint` handler with `ValidateEndpointRequest` and `ValidateEndpointResponse` Pydantic models
    - Health check via GET with 5s timeout, contract probe via POST with synthetic `TurnPayload`, validate response against `NegotiatorOutput`/`RegulatorOutput`/`ObserverOutput`
    - Include `_build_synthetic_payload(agent_type)` helper
    - Register router in `backend/app/main.py` under the `api_router`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 3.2 Write property test for validation response completeness
    - **Property 4: Endpoint Validation Response Completeness**
    - Generate random validation outcomes (mock reachable/unreachable, valid/invalid contract), verify response always has all 4 fields with correct logical constraints (`contract_valid=true` implies `reachable=true` and empty `errors`)
    - Test file: `backend/tests/property/test_byoa_properties.py`
    - **Validates: Requirements 3.3, 3.4**

  - [ ] 3.3 Extend `StartNegotiationRequest` in `backend/app/routers/negotiation.py`
    - Add `endpoint_overrides: dict[str, str] = Field(default_factory=dict)` with `@field_validator` for URL scheme and host validation
    - _Requirements: 2.1, 2.2_

  - [ ]* 3.4 Write property test for endpoint URL validation
    - **Property 1: Endpoint URL Validation**
    - Generate random strings via `st.text()`, valid URLs via custom strategy combining `st.sampled_from(["http", "https", "ftp", "ws", ""])` with `st.text()` hosts. Verify accept/reject matches scheme+host rules
    - Test file: `backend/tests/property/test_byoa_properties.py`
    - **Validates: Requirements 1.3, 2.2**

  - [ ] 3.5 Implement endpoint override merge and validation in `start_negotiation` handler
    - Validate roles exist in scenario (return 422 for invalid roles)
    - Run SSRF check on each override URL
    - Enforce HTTPS in cloud mode (`settings.RUN_MODE == "cloud"`)
    - Merge `endpoint_overrides` into scenario `AgentDefinition` objects (set `endpoint` field)
    - Run health check for all overridden endpoints before graph construction
    - Record overrides in session document
    - _Requirements: 2.3, 2.4, 2.5, 2.6, 7.1, 7.6_

  - [ ]* 3.6 Write property test for endpoint override merge correctness
    - **Property 2: Endpoint Override Merge Correctness**
    - Use scenario strategy, generate random subsets of agent roles with random URLs, apply merge, assert overridden agents have correct endpoint and non-overridden agents have `None`, all other fields unchanged
    - Test file: `backend/tests/property/test_byoa_properties.py`
    - **Validates: Requirements 2.3**

  - [ ]* 3.7 Write property test for invalid role rejection
    - **Property 3: Invalid Role Rejection**
    - Use scenario strategy, generate random role strings not in scenario, submit as `endpoint_overrides` keys, verify 422 response
    - Test file: `backend/tests/property/test_byoa_properties.py`
    - **Validates: Requirements 2.4**

  - [ ]* 3.8 Write property test for cloud HTTPS enforcement
    - **Property 8: Cloud Mode HTTPS Enforcement**
    - Generate random URLs with `st.sampled_from(["http", "https"])` schemes, test with both `RUN_MODE` values, verify cloud rejects `http://` and local accepts both
    - Test file: `backend/tests/property/test_byoa_properties.py`
    - **Validates: Requirements 7.6**

  - [ ] 3.9 Add security audit logging for outbound BYOA requests
    - Log at INFO level: session_id, agent_role, endpoint (path only, no query params), response status, response time
    - Log SSRF blocks and response size violations
    - _Requirements: 7.5_

- [ ] 4. Checkpoint — Backend API complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Frontend — API client and URL validation utility
  - [ ] 5.1 Add `validateAgentEndpoint` function and types to `frontend/lib/api.ts`
    - Add `ValidateEndpointRequest`, `ValidateEndpointResponse` interfaces
    - Implement `validateAgentEndpoint(req)` calling `POST /api/v1/agents/validate-endpoint`
    - Extend `startNegotiation` signature with `endpointOverrides?: Record<string, string>` parameter, include in request body when present
    - _Requirements: 1.4, 1.7, 3.1_

  - [ ] 5.2 Create `validateEndpointUrl` client-side utility (`frontend/lib/byoa.ts`)
    - Implement `validateEndpointUrl(url: string): string | null` — returns error message or null
    - Check: non-empty after trim, starts with `http://` or `https://`, valid URL via `new URL()`, has hostname
    - _Requirements: 1.3_

  - [ ]* 5.3 Write unit tests for `validateEndpointUrl` utility
    - Test file: `frontend/__tests__/lib/byoa.test.ts`
    - Test valid HTTP/HTTPS URLs accepted, `ftp://`/`ws://`/empty/malformed rejected
    - _Requirements: 1.3_

- [ ] 6. Frontend — AgentCard BYOA extension and Arena page state
  - [ ] 6.1 Extend `AgentCard` component with BYOA toggle, endpoint input, and validate button
    - Add BYOA props: `byoaEndpoint`, `byoaValidated`, `byoaValidating`, `byoaError`, `onByoaToggle`, `onByoaEndpointChange`, `onByoaValidate`
    - Render "Use External Agent" toggle with `data-testid="byoa-toggle-{role}"`
    - When toggled on, show endpoint input (`data-testid="byoa-endpoint-{role}"`) and validate button (`data-testid="byoa-validate-{role}"`)
    - Show validation state: green checkmark for valid, red error for invalid, spinner while validating
    - Show active badge (`data-testid="byoa-active-badge-{role}"`) when validated
    - Use client-side `validateEndpointUrl` for instant inline validation
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ] 6.2 Add BYOA state management to Arena page (`frontend/app/(protected)/arena/page.tsx`)
    - Add state: `byoaEndpoints`, `byoaValidated`, `byoaValidating`, `byoaErrors` (all `Record<string, ...>`)
    - Wire toggle/input/validate handlers to AgentCard BYOA props
    - Call `validateAgentEndpoint` on validate click
    - Include validated `endpointOverrides` in `startNegotiation` call
    - Reset BYOA state on scenario change
    - _Requirements: 1.1, 1.2, 1.4, 1.6, 1.7_

  - [ ]* 6.3 Write component tests for AgentCard BYOA functionality
    - Test file: `frontend/__tests__/components/arena/AgentCardByoa.test.tsx`
    - Test toggle renders with correct `data-testid`, toggle reveals input/validate, invalid URL shows inline error, successful validation shows green badge, deactivate clears state
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6_

- [ ] 7. Checkpoint — Frontend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Backend integration test — full BYOA flow
  - [ ] 8.1 Create `backend/tests/integration/test_byoa_flow.py`
    - Use `respx` to mock an external agent (GET `/` returns `{"status": "ok"}`, POST `/` returns valid `NegotiatorOutput`)
    - Test validate-endpoint returns `reachable: true, contract_valid: true`
    - Test negotiation start with `endpoint_overrides` succeeds and records overrides in session
    - Test mixed negotiation: 1 local + 1 overridden agent
    - Test health check failure: mock returns 500, verify 422 response
    - Test SSRF rejection: `http://127.0.0.1:8080` returns 422
    - _Requirements: 8.4, 2.5, 2.6, 7.1_

- [ ] 9. Docker Compose BYOA dev stack
  - [ ] 9.1 Create `docker-compose.byoa.yml` override file
    - Define `custom-agent` service building from `./byoa` directory, exposed on port 8080
    - Add `CUSTOM_AGENT_ENDPOINT=http://custom-agent:8080` env var to backend service
    - Ensure it extends existing `docker-compose.yml` via `-f` flag
    - _Requirements: 4.1, 4.3, 4.4, 4.6_

  - [ ] 9.2 Create `byoa/` starter directory
    - `byoa/Dockerfile` — Python 3.11-slim, installs requirements, runs `my_agent.py`
    - `byoa/requirements.txt` — `juntoai-agent-sdk`
    - `byoa/my_agent.py` — Minimal `BaseAgent` subclass implementing `on_turn` for negotiator type
    - `byoa/README.md` — Step-by-step instructions for modifying agent logic, rebuilding container, running negotiation
    - _Requirements: 4.2, 4.5_

- [ ] 10. BYOA developer guide and testing documentation
  - [ ] 10.1 Create `docs/byoa-guide.md`
    - Sections: Prerequisites, Quick Start (5-minute path with copy-pasteable commands), Build Your Agent (SDK reference + minimal negotiator example under 30 lines), Test Locally (test harness + Docker Compose), Connect to JuntoAI (ngrok primary + Cloudflare Tunnel alternative), Run a Negotiation (Arena UI walkthrough), Testing Checklist, Common Mistakes, Troubleshooting
    - Tunneling: ngrok install + `ngrok http 8080` + copy URL workflow, Cloudflare Tunnel alternative
    - Troubleshooting: ngrok URL changes, firewall blocking, HTTPS cert errors, timeout tuning, wrong response schema, empty history on turn 1, proposed_price outside budget, response time exceeding timeout
    - Warning about temporary tunnel URLs with pointer to cloud deployment options
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 8.1, 8.2, 8.3_

- [ ] 11. Final checkpoint — All tests pass, full BYOA flow verified
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend security primitives (tasks 1.x) are implemented first because the validation API and negotiation handler depend on them
- The agents router (task 3.1) is a new file; it must be registered in `main.py` alongside existing routers
- Property tests use Hypothesis and go in `backend/tests/property/test_byoa_properties.py` (one file, 8 properties)
- Frontend tests use Vitest + React Testing Library per project conventions
- Integration test uses `respx` for mocking external HTTP calls (consistent with existing test patterns)
- Docker Compose override file avoids duplicating service definitions from the base `docker-compose.yml`
