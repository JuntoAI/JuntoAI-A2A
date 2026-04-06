# Implementation Plan: Test Coverage Hardening

## Overview

Close all critical test coverage gaps in backend and frontend. No production code changes. Target: pass 70% backend coverage gate, ensure all critical business logic paths are exercised, and add pytest markers for selective test runs.

## Tasks

- [x] 1. Test infrastructure and configuration
  - [x] 1.1 Update `backend/pytest.ini` with markers
    - Add `markers` section with `unit`, `integration`, `property`, `slow`
    - Keep existing `asyncio_mode`, `addopts`, `testpaths`
    - _Requirements: 1.3_

  - [x] 1.2 Extend `backend/tests/conftest.py` with new shared fixtures
    - Add `mock_firestore_async_client` fixture that returns a `MagicMock` mimicking `google.cloud.firestore.AsyncClient` with `collection().document().get()`, `.set()`, `.update()` async mocks
    - Add `negotiation_start_payload` fixture returning a valid `StartNegotiationRequest`-compatible dict with email, scenario_id, and active_toggles
    - Add `sample_history` fixture returning a multi-turn history array with negotiator, regulator, and observer entries
    - _Requirements: 1.4_

  - [x] 1.3 Verify test suite runs under 120s
    - Run `pytest -q --co` to count total tests
    - Run full suite and record wall time
    - If over 120s, add `@pytest.mark.slow` to the slowest Hypothesis tests and configure `--hypothesis-seed` for determinism
    - _Requirements: 1.2_

- [x] 2. SSE event formatting tests (highest priority)
  - [x] 2.1 Create `backend/tests/unit/test_snapshot_to_events.py`
    - Import `_snapshot_to_events` from `app.routers.negotiation`
    - Test negotiator snapshot → yields `agent_thought` event then `agent_message` event (verify ordering)
    - Test regulator snapshot with CLEAR status → regulator event
    - Test regulator snapshot with WARNING status → regulator warning event
    - Test regulator snapshot with BLOCKED status → regulator block event
    - Test observer snapshot → observer event
    - Test dispatcher with `deal_status: "Agreed"` → `negotiation_complete` event
    - Test dispatcher with `deal_status: "Failed"` → `negotiation_complete` event
    - Test dispatcher with `deal_status: "Blocked"` → `negotiation_complete` event
    - Validate every event string matches `data: <valid JSON>\n\n` format
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.2 Create `backend/tests/unit/test_participant_summaries.py`
    - Import `_build_participant_summaries`, `_build_block_advice`, `_format_outcome_value`, `_format_price_for_summary` from `app.routers.negotiation`
    - Test 2-agent summaries (buyer + seller)
    - Test 4-agent summaries (negotiators + regulator + observer)
    - Test block advice with regulator warnings in history
    - Test `_format_outcome_value` with currency format
    - Test `_format_outcome_value` with percentage format
    - Test `_format_price_for_summary` with currency and custom label
    - Test edge cases: empty history, single turn, no regulator
    - _Requirements: 2.4, 2.5, 2.6_

  - [x] 2.3 Create SSE format property test
    - Add to `backend/tests/property/test_sse_event_properties.py`
    - **Property 1: SSE event format compliance** — generate random valid snapshot dicts, verify every yielded event matches `data: <valid JSON>\n\n`
    - _Requirements: 2.2_

- [x] 3. Checkpoint — SSE tests
  - Run `pytest tests/unit/test_snapshot_to_events.py tests/unit/test_participant_summaries.py -v` and verify all pass. Check coverage delta on `app/routers/negotiation.py`.

- [x] 4. Model mapping and pure logic tests
  - [x] 4.1 Create `backend/tests/unit/test_model_mapping.py`
    - Test `model_override` set → returns override
    - Test `model_map_json` with valid JSON → returns mapped value
    - Test `model_map_json` with invalid JSON → falls through to defaults
    - Test default mapping for `openai` provider with `gemini-2.5-flash` → `gpt-4o-mini`
    - Test default mapping for `anthropic` provider with `gemini-2.5-pro` → `claude-sonnet-4-20250514`
    - Test default mapping for `ollama` provider → `ollama/{model}`
    - Test unknown model_id → provider default fallback
    - Test unknown provider → returns model_id as-is
    - Test `ollama_model` override → dynamic mapping
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 4.2 Add model mapping property test
    - Add to `backend/tests/property/test_model_mapping_properties.py` (extend existing if present)
    - **Property 2: Model mapping resolution determinism** — for any inputs, `resolve_model_id()` returns a non-empty string; if `model_override` is non-empty, return equals `model_override`
    - _Requirements: 4.1, 4.3_

- [x] 5. Database client tests
  - [x] 5.1 Create `backend/tests/unit/test_sqlite_client.py` (new or extend existing)
    - Use `SQLiteSessionClient(":memory:")` for all tests
    - Test `create_session` → `get_session` round-trip preserves key fields
    - Test `get_session_doc` returns dict with expected keys
    - Test `update_session` modifies fields correctly
    - Test `get_session` for non-existent ID raises `SessionNotFoundError`
    - Test concurrent session creation (two different session_ids)
    - _Requirements: 5.1, 5.2_

  - [x] 5.2 Create `backend/tests/unit/test_firestore_client.py`
    - Mock `google.cloud.firestore.AsyncClient`
    - Test `create_session` calls Firestore `set()` with serialized state
    - Test `get_session` deserializes document snapshot to `NegotiationStateModel`
    - Test `get_session_doc` returns raw dict from document snapshot
    - Test non-existent document (snapshot.exists = False) raises `SessionNotFoundError`
    - _Requirements: 5.3_

  - [x] 5.3 Create `backend/tests/unit/test_profile_client.py`
    - Mock Firestore async client
    - Test `get_or_create_profile` when profile doesn't exist → creates with defaults
    - Test `get_or_create_profile` when profile exists → returns existing
    - Test `get_profile` returns None for non-existent email
    - Test `get_profile` returns dict for existing email
    - Test `update_profile` calls Firestore `update()` with correct fields
    - _Requirements: 5.4_

  - [x] 5.4 Add SQLite round-trip property test
    - **Property 3: SQLite session round-trip** — generate valid `NegotiationStateModel` instances, create then retrieve, verify key fields match
    - File: `backend/tests/property/test_sqlite_client_properties.py` (extend existing if present)
    - _Requirements: 5.1, 5.2_

- [x] 6. Checkpoint — Database and model mapping tests
  - Run coverage on `app/db/`, `app/orchestrator/model_mapping.py`. Verify coverage increased.

- [x] 7. Middleware tests
  - [x] 7.1 Create `backend/tests/unit/test_event_buffer.py`
    - Test `append` returns sequential event IDs (1, 2, 3)
    - Test `replay_after(session, 0)` returns all events for that session
    - Test `replay_after(session, 2)` returns only events with ID > 2
    - Test terminal event flag is stored
    - Test different sessions are isolated (append to session A, replay session B → empty)
    - Test `replay_after` on non-existent session → empty list
    - _Requirements: 6.1_

  - [x] 7.2 Extend `backend/tests/unit/test_sse_limiter.py`
    - Verify existing tests cover: acquire under limit → True, acquire at limit → False, release → allows new acquire, total_active_connections reflects state
    - Add any missing test cases
    - _Requirements: 6.2_

  - [x] 7.3 Add event buffer replay property test
    - **Property 5: Event buffer replay correctness** — generate random append sequences, verify `replay_after` returns exactly the events after the given ID in order
    - File: `backend/tests/property/test_event_buffer_properties.py`
    - _Requirements: 6.1_

- [x] 8. Auth service tests
  - [x] 8.1 Create `backend/tests/unit/test_auth_service.py`
    - Test `hash_password` → `verify_password` round-trip succeeds
    - Test `verify_password` with wrong password returns False
    - Test 72-byte bcrypt truncation: password of 100 chars hashes same as first 72 bytes
    - Test `validate_google_token` with mocked `requests.get`: status 200 with valid claims → returns claims
    - Test `validate_google_token`: status 200 but missing `sub` → raises ValueError
    - Test `validate_google_token`: status 401 → raises ValueError
    - Test `check_google_oauth_id_unique`: no existing profile → True
    - Test `check_google_oauth_id_unique`: existing profile same email → True
    - Test `check_google_oauth_id_unique`: existing profile different email → False
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 8.2 Add password hash property test
    - **Property 4: Password hash round-trip** — generate random strings (1-72 chars), verify `verify_password(pw, hash_password(pw))` is True
    - File: `backend/tests/property/test_auth_service_properties.py`
    - Use `@settings(max_examples=20)` since bcrypt is slow
    - _Requirements: 7.1_

- [x] 9. Checkpoint — Middleware and auth tests
  - Run coverage on `app/middleware/`, `app/services/`. Verify coverage increased.

- [x] 10. Negotiation router integration tests
  - [x] 10.1 Create `backend/tests/integration/test_negotiation_start.py`
    - Use existing `test_client` fixture with mocked dependencies
    - Test `POST /api/v1/negotiation/start` with valid payload → 200, response has `session_id` and `tokens_remaining`
    - Test invalid `scenario_id` → 404
    - Test missing required fields (no email) → 422
    - Test `created_at` is set on session document after start
    - _Requirements: 3.1, 3.2_

  - [x] 10.2 Extend `backend/tests/integration/test_stream.py`
    - Add test for event replay: set `Last-Event-ID` header, verify only events after that ID are returned
    - Add test verifying SSE content contains expected event types for a completed negotiation
    - _Requirements: 3.3_

  - [x] 10.3 Extend `backend/tests/integration/test_auth_endpoints.py`
    - Verify existing tests cover: login success, login failure (wrong password), set-password, check-email
    - Add tests for: Google login (mocked), change-password, link/unlink Google
    - _Requirements: 3.1_

  - [x] 10.4 Extend `backend/tests/integration/test_profile_endpoints.py`
    - Verify existing tests cover: get profile, update profile
    - Add tests for: email verification request, profile creation on first access
    - _Requirements: 3.1_

- [x] 11. Evaluator and orchestrator gap tests
  - [x] 11.1 Extend `backend/tests/unit/orchestrator/test_evaluator.py`
    - Add tests for the main evaluation function with mocked LLM returning valid evaluation JSON
    - Add test for LLM returning invalid JSON → graceful fallback
    - Add test for evaluation with different scenario types
    - _Requirements: 10.1_

  - [x] 11.2 Extend `backend/tests/unit/orchestrator/test_evaluator_prompts.py`
    - Add tests for prompt construction with 2-agent scenario
    - Add tests for prompt construction with 4-agent scenario (negotiators + regulator + observer)
    - Add tests verifying prompt contains scenario context, agent roles, and history
    - _Requirements: 10.2_

  - [x] 11.3 Extend `backend/tests/unit/orchestrator/test_confirmation_node.py`
    - Add tests for confirmation with accept response
    - Add tests for confirmation with reject response
    - Add tests for confirmation with invalid JSON from LLM
    - _Requirements: 10.1_

  - [x] 11.4 Extend `backend/tests/unit/orchestrator/test_milestone_generator.py`
    - Add tests for milestone generation at different negotiation stages
    - Add tests for milestone summary formatting
    - _Requirements: 10.1_

- [x] 12. Scenario module gap tests
  - [x] 12.1 Extend `backend/tests/unit/test_toggle_injector.py`
    - Add test: toggle injection adds hidden context to correct agent
    - Add test: multiple toggles applied to different agents
    - Add test: toggle targeting non-existent agent role is handled gracefully
    - Add test: empty toggles list → no changes to state
    - _Requirements: 11.1_

  - [x] 12.2 Extend `backend/tests/unit/test_pretty_printer.py`
    - Add test: scenario pretty print produces readable output
    - Add test: scenario with all fields populated
    - Add test: scenario with minimal fields
    - _Requirements: 11.2_

  - [x] 12.3 Verify `test_scenario_loader.py` and `test_scenario_registry.py` error paths
    - Check existing tests cover: missing file, invalid JSON, duplicate scenario IDs
    - Add any missing error path tests
    - _Requirements: 11.3_

- [x] 13. Checkpoint — Backend coverage gate
  - Run `pytest --cov=app --cov-fail-under=70 -q` and verify it passes. If not, identify remaining gaps and add targeted tests.

- [x] 14. Frontend API client tests
  - [x] 14.1 Create `frontend/__tests__/lib/auth.test.ts`
    - Mock `global.fetch` with `vi.fn()`
    - Test `checkEmail`: 200 → returns `{ has_password }`, non-200 → throws
    - Test `loginWithPassword`: 200 → returns LoginResponse, 401 → throws "Invalid password", other → throws generic
    - Test `loginWithGoogle`: 200 → returns LoginResponse, 404 → throws specific message, other → throws generic
    - Test `setPassword`: 200 → resolves, non-200 → throws with detail from body
    - Test `changePassword`: 200 → resolves, 401 → throws "Invalid current password", other → throws
    - Test `linkGoogle`: 200 → returns response, 409 → throws "already linked", other → throws
    - Test `unlinkGoogle`: 200 → resolves, non-200 → throws
    - _Requirements: 8.1, 8.2_

  - [x] 14.2 Create `frontend/__tests__/lib/profile.test.ts`
    - Mock `global.fetch` with `vi.fn()`
    - Test `getProfile`: 200 → returns ProfileResponse, non-200 → throws
    - Test `updateProfile`: 200 → returns ProfileResponse, non-200 → throws
    - Test `requestEmailVerification`: 200 → resolves, non-200 → throws
    - _Requirements: 8.3, 8.4_

- [x] 15. Frontend component tests
  - [x] 15.1 Create `frontend/__tests__/components/WaitlistForm.test.tsx`
    - Render WaitlistForm, verify email input and submit button exist
    - Simulate valid email submission → success callback fired
    - Simulate invalid email → error message displayed
    - Simulate API error → error message displayed
    - _Requirements: 9.1_

  - [x] 15.2 Create `frontend/__tests__/components/TokenDisplay.test.tsx`
    - Render with token count (e.g., 50) → displays "50"
    - Render with 0 tokens → displays "0"
    - Render with undefined/null → handles gracefully
    - _Requirements: 9.2_

  - [x] 15.3 Create `frontend/__tests__/components/StartNegotiationButton.test.tsx`
    - Render enabled (tokens > 0) → button is clickable
    - Render disabled (tokens = 0) → button is disabled
    - Click fires the provided callback
    - _Requirements: 9.3_

- [-] 16. Final checkpoint — Full coverage verification
  - Run `cd backend && pytest --cov=app --cov-fail-under=70 -q` → must pass
  - Run `cd frontend && npx vitest run --coverage` → must pass with 70% thresholds
  - Verify CI workflow (`.github/workflows/pr-tests.yml`) would pass with these changes
  - Document final coverage numbers

## Notes

- Tasks are ordered by impact: SSE formatting (Req 2) and model mapping (Req 4) are pure logic with zero deps — fastest to write, highest coverage ROI.
- Database client tests (Task 5) require careful mocking but cover 245 statements at 0%.
- Frontend tests (Tasks 14-15) are straightforward fetch mocks and RTL renders.
- If the 70% gate is still not met after all tasks, the remaining gap is likely in `app/routers/negotiation.py` (458 stmts) and `app/orchestrator/agent_node.py` (393 stmts) — the two largest files. Additional targeted tests for specific branches in those files should close the gap.
- Spec 150 (Admin Dashboard) is in progress and will add coverage for `app/routers/admin.py` (303 stmts at 0%). This spec does NOT duplicate that work.
