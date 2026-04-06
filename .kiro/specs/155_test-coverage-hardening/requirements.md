# Requirements Document: Test Coverage Hardening

## Introduction

The JuntoAI A2A test suite has broad coverage across property tests, unit tests, and orchestrator integration tests, but critical "glue" layers — routers, SSE event formatting, database clients, middleware, and frontend API clients — are severely undertested. The full backend coverage sits around 26% when measured against the complete `app/` module. Multiple source files with complex business logic show 0% or sub-20% coverage. This spec closes those gaps, restructures test configuration for speed and clarity, and enforces the 70% coverage target in CI.

## Scope

Backend (`backend/tests/`) and frontend (`frontend/__tests__/`) test suites. No production code changes — this spec only adds tests, test fixtures, and test configuration. The only non-test file changes are `pytest.ini` (markers/config) and `vitest.config.ts` (thresholds already updated).

## Dependencies

All existing specs that produced the source code being tested:
- Spec 030 (LangGraph Orchestration) — orchestrator modules
- Spec 050 (Frontend Gate Waitlist) — auth, waitlist, token flows
- Spec 060 (Glass Box UI) — SSE streaming, event formatting
- Spec 080 (Local Battle Arena) — SQLite client, model mapping
- Spec 140 (User Profile Token Upgrade) — profile client, auth service
- Spec 145 (Per-Model Telemetry) — telemetry in agent_node
- Spec 150 (Admin Dashboard) — admin router (in progress)

## Requirements

### Requirement 1: Backend Coverage Gate

**User Story:** As a developer, I want the test suite to reliably pass the 70% coverage threshold in CI, so that PRs cannot merge with insufficient test coverage.

#### Acceptance Criteria

1. WHEN `pytest --cov=app --cov-fail-under=70` is run from `backend/`, the test suite SHALL pass the 70% coverage threshold.
2. THE test suite SHALL complete in under 120 seconds on a standard CI runner (GitHub Actions `ubuntu-latest`), excluding Hypothesis database warm-up.
3. THE `pytest.ini` SHALL define markers `unit`, `integration`, `property`, and `slow` so tests can be run selectively via `pytest -m unit`.
4. ALL new test files SHALL use the appropriate marker decorator at the module or class level.

### Requirement 2: SSE Event Formatting Tests

**User Story:** As a developer, I want the `_snapshot_to_events()` function fully tested, so that changes to the SSE contract are caught before they break the frontend.

#### Acceptance Criteria

1. THERE SHALL be unit tests for `_snapshot_to_events()` in `backend/app/routers/negotiation.py` covering: negotiator snapshot → `agent_thought` + `agent_message` events, regulator snapshot → regulator events with status, observer snapshot → observer events, dispatcher agreement snapshot → `negotiation_complete` event, dispatcher failure snapshot → `negotiation_complete` event with failed status.
2. EACH generated SSE event SHALL be validated for `data: <valid JSON>\n\n` format compliance.
3. THERE SHALL be tests verifying that inner thoughts stream BEFORE public messages for negotiator events (product rule).
4. THERE SHALL be tests for `_build_participant_summaries()` covering multi-agent scenarios with negotiators, regulators, and observers.
5. THERE SHALL be tests for `_build_block_advice()` covering regulator block scenarios.
6. THERE SHALL be tests for `_format_outcome_value()` covering currency and percentage value formats.

### Requirement 3: Negotiation Router Integration Tests

**User Story:** As a developer, I want the `POST /api/v1/negotiation/start` endpoint tested end-to-end with mocked dependencies, so that the session creation flow is validated.

#### Acceptance Criteria

1. THERE SHALL be an integration test for `POST /api/v1/negotiation/start` that verifies: successful session creation returns 200 with `session_id` and `tokens_remaining`, invalid scenario_id returns 404, missing email returns 422.
2. THERE SHALL be an integration test verifying that `created_at` is set on the session document after `start_negotiation()`.
3. THERE SHALL be an integration test for the SSE stream endpoint verifying event replay via `Last-Event-ID` header (event buffer middleware).

### Requirement 4: Model Mapping Tests

**User Story:** As a developer, I want `resolve_model_id()` fully tested, so that LLM routing in local mode works correctly for all providers.

#### Acceptance Criteria

1. THERE SHALL be unit tests for `resolve_model_id()` covering all 4 resolution paths: global override, MODEL_MAP JSON override, default mapping, and provider default fallback.
2. THERE SHALL be tests for each provider (`openai`, `anthropic`, `ollama`) with known model_id values.
3. THERE SHALL be tests for edge cases: invalid JSON in `model_map_json`, unknown provider, unknown model_id, `ollama_model` override.

### Requirement 5: Database Client Tests

**User Story:** As a developer, I want the SQLite and Firestore session clients tested against their interface contract, so that local and cloud modes behave identically.

#### Acceptance Criteria

1. THERE SHALL be unit tests for `SQLiteSessionClient` covering: `create_session`, `get_session`, `get_session_doc`, `update_session`, and session-not-found error.
2. THE SQLite tests SHALL use an in-memory database (`:memory:`) for speed and isolation.
3. THERE SHALL be unit tests for `FirestoreSessionClient` with mocked Firestore SDK covering: `create_session`, `get_session`, `get_session_doc`, and document-not-found error.
4. THERE SHALL be unit tests for `ProfileClient` with mocked Firestore SDK covering: `get_or_create_profile`, `get_profile`, `update_profile`.

### Requirement 6: Middleware Tests

**User Story:** As a developer, I want the SSE middleware (event buffer and connection limiter) tested, so that reconnection replay and rate limiting work correctly.

#### Acceptance Criteria

1. THERE SHALL be unit tests for `SSEEventBuffer` covering: `append` returns incrementing event IDs, `replay_after` returns only events after the given ID, terminal events are stored, concurrent session isolation.
2. THERE SHALL be unit tests for `SSEConnectionTracker` covering: `acquire` returns True under limit, `acquire` returns False at limit, `release` decrements count, `total_active_connections` reflects current state.

### Requirement 7: Auth Service Tests

**User Story:** As a developer, I want the auth service functions tested, so that password hashing and Google token validation are verified.

#### Acceptance Criteria

1. THERE SHALL be unit tests for `hash_password` and `verify_password` covering: round-trip (hash then verify succeeds), wrong password fails, bcrypt 72-byte truncation edge case.
2. THERE SHALL be unit tests for `validate_google_token` with mocked HTTP responses covering: valid token returns claims, invalid token raises ValueError, missing `sub` claim raises ValueError.
3. THERE SHALL be unit tests for `check_google_oauth_id_unique` with mocked profile client covering: no existing profile → True, same email → True, different email → False.

### Requirement 8: Frontend API Client Tests

**User Story:** As a developer, I want the frontend API client modules (`lib/auth.ts`, `lib/profile.ts`) tested with mocked fetch, so that error handling for each endpoint is verified.

#### Acceptance Criteria

1. THERE SHALL be tests for `lib/auth.ts` covering all exported functions: `checkEmail`, `loginWithPassword`, `loginWithGoogle`, `setPassword`, `changePassword`, `linkGoogle`, `unlinkGoogle`.
2. EACH function test SHALL verify: successful response parsing, specific error status handling (401, 404, 409 as applicable), generic error handling for unexpected status codes.
3. THERE SHALL be tests for `lib/profile.ts` covering: `getProfile`, `updateProfile`, `requestEmailVerification`.
4. EACH function test SHALL verify successful response parsing and error handling for non-ok responses.

### Requirement 9: Frontend Component Tests

**User Story:** As a developer, I want the untested frontend components covered, so that the waitlist gate and token display work correctly.

#### Acceptance Criteria

1. THERE SHALL be tests for `components/WaitlistForm.tsx` covering: form renders, email validation, successful submission, error display.
2. THERE SHALL be tests for `components/TokenDisplay.tsx` covering: renders token count, handles zero tokens, handles undefined/null state.
3. THERE SHALL be tests for `components/StartNegotiationButton.tsx` covering: renders enabled when tokens available, renders disabled when no tokens, click triggers negotiation start.

### Requirement 10: Evaluator and Evaluator Prompts Tests

**User Story:** As a developer, I want the negotiation evaluator and its prompt builder tested, so that post-negotiation analysis works correctly.

#### Acceptance Criteria

1. THERE SHALL be unit tests for `app/orchestrator/evaluator.py` covering the main evaluation logic with mocked LLM responses.
2. THERE SHALL be unit tests for `app/orchestrator/evaluator_prompts.py` covering prompt construction for different scenario types and agent configurations.

### Requirement 11: Scenario Module Tests

**User Story:** As a developer, I want the scenario loader, registry, and toggle injector fully tested, so that config-driven scenario loading is reliable.

#### Acceptance Criteria

1. THERE SHALL be unit tests for `app/scenarios/toggle_injector.py` covering: toggle injection adds hidden context to correct agent, multiple toggles, toggle for non-existent agent is ignored.
2. THERE SHALL be unit tests for `app/scenarios/pretty_printer.py` covering scenario formatting output.
3. THE existing `test_scenario_loader.py` and `test_scenario_registry.py` SHALL be verified to cover error paths (missing file, invalid JSON, duplicate IDs).
