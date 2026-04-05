# Implementation Plan: Agent Registration & Validation

## Overview

Implement the agent registration, validation, and discovery system following the existing codebase patterns: Pydantic V2 models, Protocol-based dual storage (Firestore + SQLite), factory function in `db/__init__.py`, validation service using `httpx`, and a FastAPI router under `/api/v1/agents`. Property-based tests use Hypothesis following the pattern in `backend/tests/property/`.

## Tasks

- [ ] 1. Create Pydantic models and agent registry protocol
  - [ ] 1.1 Create `backend/app/models/agent.py` with all Pydantic models
    - `AgentRegistrationRequest` with field validators for endpoint URL, name/description length, supported_types uniqueness
    - `AgentUpdateRequest` with optional fields and same validators
    - `TypeValidationResult`, `AgentRegistration`, `AgentCard`
    - Follow the pattern in `backend/app/models/negotiation.py` and `backend/app/scenarios/models.py`
    - _Requirements: 1.1, 3.1, 4.4_

  - [ ]* 1.2 Write property test: Registration model round-trip serialization
    - **Property 1: Registration model round-trip serialization**
    - Create `backend/tests/property/test_agent_registration_properties.py`
    - Generate random valid `AgentRegistration` instances, verify `model_dump()` → reconstruct round-trip
    - Follow the Hypothesis strategy pattern in `backend/tests/property/test_agent_memory_properties.py`
    - **Validates: Requirements 1.1, 3.1, 3.2**

  - [ ]* 1.3 Write property test: Registration input validation rejects invalid inputs
    - **Property 2: Registration input validation rejects invalid inputs**
    - Generate random strings with invalid lengths/formats for name, description, endpoint, supported_types
    - Verify `ValidationError` is raised for each invalid case
    - **Validates: Requirements 1.1**

  - [ ]* 1.4 Write unit tests for Pydantic agent models
    - Create `backend/tests/unit/test_agent_models.py`
    - Test specific valid/invalid examples for `AgentRegistrationRequest`, `AgentUpdateRequest`
    - Test endpoint URL validation (http, https, invalid schemes)
    - Test name/description length boundaries
    - Test supported_types deduplication and allowed values
    - _Requirements: 1.1_

- [ ] 2. Implement Agent Registry storage layer
  - [ ] 2.1 Create `backend/app/db/agent_registry.py` with Protocol and dual implementations
    - Define `AgentRegistryStore` Protocol following `backend/app/db/base.py` pattern
    - Implement `FirestoreAgentRegistry` following `backend/app/db/firestore_client.py` pattern
    - Implement `SQLiteAgentRegistry` following `backend/app/db/sqlite_client.py` and `backend/app/db/profile_client.py` patterns
    - SQLite: create table with indexes on `owner_email`, `status`, `endpoint`
    - Methods: `create_agent`, `get_agent`, `get_agent_by_endpoint`, `list_agents`, `list_agents_by_owner`, `count_agents_by_owner`, `update_agent`, `delete_agent`
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ] 2.2 Add `get_agent_registry()` factory function to `backend/app/db/__init__.py`
    - Follow the exact pattern of `get_profile_client()` and `get_session_store()`
    - Singleton with lazy initialization, RUN_MODE-based selection
    - _Requirements: 3.3_

  - [ ]* 2.3 Write property test: Type filter returns only matching agents
    - **Property 6: Type filter returns only matching agents**
    - Generate random agent sets with varying `supported_types` and `status`
    - Verify `list_agents(type=X)` returns only active agents containing that type
    - Use SQLiteAgentRegistry with in-memory or temp DB for fast property testing
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 2.4 Write property test: Owner filter returns only owner's agents
    - **Property 7: Owner filter returns only owner's agents**
    - Generate random agent sets with varying `owner_email` values
    - Verify `list_agents_by_owner(email)` returns exactly matching agents
    - **Validates: Requirements 5.5**

- [ ] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement Validation Service
  - [ ] 4.1 Create `backend/app/services/agent_validator.py`
    - `AgentValidator` class with `validate_endpoint()`, `validate_all_types()`, `build_synthetic_payload()`
    - Use `httpx.AsyncClient` with 10-second timeout
    - Map agent types to Pydantic output models: `NegotiatorOutput`, `RegulatorOutput`, `ObserverOutput`
    - Build realistic synthetic `Turn_Payload` per type (2-agent scenario, 3 history entries, turn_number=4, max_turns=12, current_offer=100000.0)
    - Handle timeout, connection error, invalid JSON, non-200 status, Pydantic validation failure
    - Add `derive_status()` helper: "active" if all passed, "validation_failed" otherwise
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.4_

  - [ ]* 4.2 Write property test: Validation produces one result per declared type
    - **Property 3: Validation produces one result per declared type**
    - Generate random non-empty subsets of `["negotiator", "regulator", "observer"]`
    - Mock httpx to return 200 with valid JSON
    - Verify result list has exactly one entry per type, no duplicates
    - **Validates: Requirements 1.3, 2.1, 2.6**

  - [ ]* 4.3 Write property test: Valid/invalid responses produce correct pass/fail
    - **Property 4: Valid responses produce passed results, invalid responses produce failed results**
    - Generate random valid response bodies per type → verify `passed=True`
    - Generate random non-200 status codes or invalid bodies → verify `passed=False` with non-empty error
    - **Validates: Requirements 2.3, 2.4, 2.5**

  - [ ]* 4.4 Write property test: Status derivation from validation results
    - **Property 5: Status derivation from validation results**
    - Generate random lists of `TypeValidationResult` with varying pass/fail
    - Verify status is "active" iff all passed, "validation_failed" otherwise
    - **Validates: Requirements 3.4**

  - [ ]* 4.5 Write unit tests for AgentValidator
    - Create `backend/tests/unit/test_agent_validator.py`
    - Test `build_synthetic_payload()` structure per type
    - Test `validate_endpoint()` with mocked httpx: 200 valid, 200 invalid JSON, 500, timeout, connection error
    - Test `derive_status()` with specific examples
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement staleness check utility
  - [ ] 6.1 Add `is_stale()` and `check_and_revalidate_stale_agents()` functions
    - Add to `backend/app/services/agent_validator.py` or a new utility module
    - `is_stale(validated_at, now)` → True if difference > 24 hours
    - `check_and_revalidate_stale_agents(agent_endpoints, registry, validator)` → revalidates stale agents, raises error on failure
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 6.2 Write property test: Staleness detection
    - **Property 8: Staleness detection**
    - Generate random `validated_at` timestamps and current times
    - Verify `is_stale()` returns True iff difference > 24 hours
    - **Validates: Requirements 6.2, 6.4**

- [ ] 7. Implement agents router and wire into app
  - [ ] 7.1 Create `backend/app/routers/agents.py` with all endpoints
    - `POST /agents/register` — validate profile exists, check duplicate endpoint, check agent limit (10), run contract validation, store registration
    - `GET /agents` — list active agents, optional `?type=` filter (public, no auth)
    - `GET /agents/mine?email=` — list owner's agents
    - `GET /agents/{agent_id}` — get single agent card (public)
    - `PUT /agents/{agent_id}` — update + revalidate (owner only via email in body)
    - `DELETE /agents/{agent_id}?email=` — delete (owner only)
    - `POST /agents/{agent_id}/revalidate?email=` — revalidate (owner only)
    - Follow error handling patterns from design: 403, 404, 409, 422, 503
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 7.2 Register agents router in `backend/app/main.py`
    - Import and include `agents_router` in `api_router`
    - _Requirements: 1.1, 4.1_

  - [ ]* 7.3 Write integration tests for agent registration endpoints
    - Create `backend/tests/integration/test_agent_registration_router.py`
    - Follow the pattern in `backend/tests/integration/test_profile_endpoints.py`
    - Test full registration flow: valid request → 201
    - Test registration with no profile → 403
    - Test duplicate endpoint → 409
    - Test agent limit exceeded → 422
    - Test validation failure → 422 with failure details
    - Test discovery: GET /agents returns only active agents
    - Test discovery: GET /agents?type=negotiator filters correctly
    - Test discovery: GET /agents/{id} returns correct agent
    - Test management: PUT updates and revalidates
    - Test management: DELETE removes agent
    - Test management: non-owner gets 403
    - Test revalidation: POST revalidate updates timestamps
    - Test mine endpoint: returns only owner's agents
    - _Requirements: 1.1-1.7, 4.1-4.5, 5.1-5.5_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Requirement 7 (Scenario Builder integration) is explicitly excluded — it's a future enhancement
- Property tests use Hypothesis with `@settings(max_examples=100)` following existing patterns
- All storage implementations follow the existing Protocol + factory pattern in `backend/app/db/`
- The staleness check is a utility function, not wired into the orchestrator yet — that integration happens when Spec 200 is complete
