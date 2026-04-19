# Implementation Plan: CRM Integration API

## Overview

This plan implements the CRM Integration API as a thin, authenticated layer on top of the existing A2A negotiation engine. The implementation follows the established project patterns: dual-mode persistence via Protocol classes, FastAPI dependency injection, Pydantic V2 models, and pytest + Hypothesis testing. Each task builds incrementally — persistence first, then services, then router wiring, then tests — so there is never orphaned code.

## Tasks

- [x] 1. Define Pydantic V2 request/response models
  - [x] 1.1 Create `backend/app/models/integrations.py` with all Pydantic V2 models
    - Define `CreateKeyRequest`, `CreateKeyResponse`, `CRMContext`, `MyProfileInput`, `TheirProfileInput`, `DealContextInput`, `RegulatorInput`, `ScenarioBuilderInput`, `SimulateRequest` (with `model_validator` for `_dynamic` / `scenario_builder` mutual exclusion), `SimulateResponse`, `ParticipantSummary`, `EvaluationScores`, `SessionOutcome`, `SessionStatusResponse`, `ScenarioAgent`, `ScenarioToggle`, `ScenarioContextFields`, `ScenarioListItem`, `ScenarioListResponse`, `RateLimitInfo`, `HealthResponse`, `WebhookPayload`, `IntegrationErrorResponse`
    - Validate `callback_url` as HTTPS (or HTTP when `RUN_MODE=local`)
    - _Requirements: 14.1, 14.2_

  - [x] 1.2 Write property test for Pydantic model serialization round-trip
    - **Property 14: Pydantic Model Serialization Round-Trip**
    - Use Hypothesis strategies to generate valid instances of `CreateKeyRequest`, `SimulateRequest`, `CRMContext`, `SessionStatusResponse`, `HealthResponse`, `WebhookPayload`, `ScenarioBuilderInput`, `IntegrationErrorResponse`
    - Assert `.model_dump_json()` → `.model_validate_json()` produces equivalent instance
    - **Validates: Requirements 14.3**

- [x] 2. Implement API Key persistence layer (dual-mode)
  - [x] 2.1 Add `ApiKeyStore` Protocol to `backend/app/db/base.py`
    - Define `create_key`, `get_key_by_hash`, `get_key_by_id`, `update_key`, `deactivate_key`, `increment_usage`, `reset_daily_usage` methods following the existing `SessionStore`/`ShareStore` pattern
    - _Requirements: 12.1_

  - [x] 2.2 Create `backend/app/db/api_key_store.py` with Firestore and SQLite implementations
    - Implement `FirestoreApiKeyClient` using `integration_api_keys` collection
    - Implement `SQLiteApiKeyClient` with auto-creating `integration_api_keys` table and `idx_api_keys_hash` index on first access
    - Store `scopes` as JSON array in SQLite, native array in Firestore
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 2.3 Add `get_api_key_store()` factory function to `backend/app/db/__init__.py`
    - Follow the existing `get_session_store()` / `get_share_store()` singleton pattern
    - Return `SQLiteApiKeyClient` in local mode, `FirestoreApiKeyClient` in cloud mode
    - _Requirements: 12.2_

- [x] 3. Implement API Key Service
  - [x] 3.1 Create `backend/app/services/api_key_service.py`
    - Implement `generate_raw_key()` → `a2a_live_<base64url 32 random bytes>`
    - Implement `hash_key()` → SHA-256 hex digest
    - Implement `generate_key()` → creates key record with all required fields (`key_id`, `key_hash`, `key_prefix`, `org_name`, `created_by_email`, `scopes`, `rate_limit_daily`, `rate_limit_per_minute`, `active`, `created_at`, `last_used_at`, `usage_today`), applies default scopes (`simulate`, `read_sessions`, `list_scenarios`) and default rate limits (100 cloud / 1000 local) when not specified
    - Implement `validate_key()` → hash lookup, return key record or None, update `last_used_at`
    - Implement `check_rate_limit()` → daily counter check with midnight UTC reset, per-minute window check, returns `(allowed, rate_info)` dict
    - Implement `deactivate_key()` → set `active=false`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.5, 3.1, 3.2, 3.4_

  - [x] 3.2 Write property test for API key generation and validation round-trip
    - **Property 1: API Key Generation and Validation Round-Trip**
    - Generate keys with arbitrary valid `org_name`, `scopes`, `rate_limit_daily`
    - Assert hashing the raw key and querying the store returns the original record with matching metadata
    - **Validates: Requirements 1.1, 2.1**

  - [x] 3.3 Write property test for API key record completeness
    - **Property 2: API Key Record Completeness**
    - For any generated key, assert all required fields exist with correct types
    - Assert `key_prefix` equals first 4 chars after `a2a_live_` in the raw key
    - **Validates: Requirements 1.2**

  - [x] 3.4 Write property test for rate limit enforcement
    - **Property 4: Rate Limit Enforcement**
    - For any key with `rate_limit_daily=D` and `usage_today=U`, assert `U >= D` → rejected with 429
    - For any key with `rate_limit_per_minute=M` and `minute_window_count=C`, assert `C >= M` → rejected
    - Assert each successful request increments counters
    - **Validates: Requirements 3.1, 3.2, 3.4**

- [x] 4. Implement API key auth dependency and context injection
  - [x] 4.1 Create `backend/app/middleware/api_key_auth.py`
    - Implement `validate_api_key()` FastAPI dependency: extract `X-API-Key` header, hash it, query store, check `active`, check scope, check rate limits
    - Implement `require_scope(scope)` factory that returns a dependency enforcing a specific scope
    - Raise `HTTPException(401)` with `invalid_api_key` for missing/invalid key
    - Raise `HTTPException(403)` with `key_deactivated` for inactive key
    - Raise `HTTPException(403)` with `insufficient_scope` for missing scope
    - Raise `HTTPException(429)` with `rate_limit_exceeded` for exceeded limits, include `retry_after_seconds`, `limit`, `used` in details
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.2, 3.4, 13.1, 13.2_

  - [x] 4.2 Write property test for scope-based access control
    - **Property 3: Scope-Based Access Control**
    - For any key with scopes `S` and required scope `R` where `R ∉ S`, assert rejection with 403 `insufficient_scope`
    - **Validates: Requirements 2.4**

  - [x] 4.3 Implement context injection in `backend/app/services/integration_service.py` (context methods only)
    - Implement `build_context_preamble(context)` → structured text from CRM fields (lists as comma-separated, booleans as "Yes"/"No", `deal_value` as currency string)
    - Implement `parse_context_preamble(preamble)` → recover original field names and values
    - Implement `inject_context_into_prompts(scenario, context)` → prepend preamble to each agent's `persona_prompt`
    - Return unmodified prompts when context is empty or None
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 4.4 Write property test for context preamble round-trip
    - **Property 7: Context Preamble Round-Trip**
    - For any valid `CRMContext`, assert `parse_context_preamble(build_context_preamble(ctx))` recovers original field names and values
    - **Validates: Requirements 7.1, 7.3, 7.5**

  - [x] 4.5 Write property test for context injection preserving original prompt
    - **Property 8: Context Preamble Injection Preserves Original Prompt**
    - For any non-empty `CRMContext` and any `persona_prompt`, assert injected prompt starts with preamble and ends with original prompt content
    - **Validates: Requirements 7.2**

- [x] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Webhook Dispatcher
  - [x] 6.1 Create `backend/app/services/webhook_dispatcher.py`
    - Implement `compute_signature(payload_bytes, secret)` → HMAC-SHA256 hex digest
    - Implement `verify_signature(payload_bytes, secret, signature)` → constant-time comparison
    - Implement `deliver(callback_url, payload, api_key_raw, local_mode)` → HTTP POST with `X-A2A-Signature` header, 3 retries with exponential backoff (5s, 30s, 120s) in cloud mode, single attempt in local mode
    - Log failure and cease delivery after all retries exhausted
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 6.2 Write property test for HMAC-SHA256 webhook signature correctness
    - **Property 12: HMAC-SHA256 Webhook Signature Correctness**
    - For any payload bytes and key string, assert `compute_signature` matches `hmac.new(key.encode(), payload, hashlib.sha256).hexdigest()`
    - Assert `verify_signature` returns True for correct signature, False for tampered payload or wrong key
    - **Validates: Requirements 11.2**

- [x] 7. Implement Integration Service (simulation orchestration)
  - [x] 7.1 Complete `backend/app/services/integration_service.py` with simulation orchestration
    - Implement `create_simulation()` → validate scenario against ScenarioRegistry, validate toggle IDs, inject CRM context, create session, start negotiation as background task, create share record, schedule webhook callback on completion
    - Handle `scenario_id="_dynamic"` → pass `scenario_builder` to `BuilderLLMAgent`, validate generated `ArenaScenario`, persist to custom scenario store
    - Set `owner_email` based on `triggered_by`: valid email → use as owner + set `source="integration"` and `integration_org`; non-email or missing → use `"integration:<org_name>"` as synthetic owner
    - Implement `get_session_status()` → map internal session data to `SessionStatusResponse`, exclude internal fields (`history`, `hidden_context`, `custom_prompts`, `model_overrides`, `agent_states`, `agent_memories`)
    - Implement `list_scenarios()` → filter scenario fields to only expose `id`, `name`, `description`, `category`, `difficulty`, `agents` (role/name/type), `toggles` (id/label/target_agent_role), `context_fields`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 5.1, 5.2_

  - [x] 7.2 Write property test for scenario list field filtering
    - **Property 6: Scenario List Field Filtering**
    - For any scenario in the registry, assert response contains only allowed fields and never contains `model_id`, `persona_prompt`, `hidden_context_payload`, `budget`, `goals`, `output_fields`
    - **Validates: Requirements 5.1, 5.2**

  - [x] 7.3 Write property test for session status excluding internal data
    - **Property 9: Session Status Excludes Internal Data**
    - For any session, assert `SessionStatusResponse` does not contain `history`, `hidden_context`, `custom_prompts`, `model_overrides`, `agent_states`, `agent_memories`
    - **Validates: Requirements 8.4**

  - [x] 7.4 Write property test for email triggered_by setting owner and integration metadata
    - **Property 10: Email triggered_by Sets Owner and Integration Metadata**
    - For any simulate request with valid email `triggered_by`, assert session has `owner_email` = email, `source` = `"integration"`, `integration_org` = org_name
    - **Validates: Requirements 9.1, 9.2**

  - [x] 7.5 Write property test for non-email triggered_by using synthetic owner
    - **Property 11: Non-Email triggered_by Uses Synthetic Owner**
    - For any simulate request with non-email `triggered_by` (display name, empty, None), assert session has `owner_email` = `"integration:<org_name>"`
    - **Validates: Requirements 9.3**

- [x] 8. Implement Integration Router and wire everything together
  - [x] 8.1 Create `backend/app/routers/integrations.py` with all endpoints
    - `GET /integrations/health` → health check with rate limit status (any valid key)
    - `GET /integrations/scenarios` → list filtered scenarios (requires `list_scenarios` scope)
    - `POST /integrations/simulate` → trigger async simulation (requires `simulate` scope)
    - `GET /integrations/sessions/{session_id}` → poll session status (requires `read_sessions` scope)
    - `POST /integrations/keys` → generate new API key (requires `manage_keys` scope)
    - `DELETE /integrations/keys/{key_id}` → deactivate API key (requires `manage_keys` scope)
    - Attach `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers to all successful responses
    - Use consistent `IntegrationErrorResponse` format for all error responses (401, 403, 404, 422, 429, 500, 503)
    - _Requirements: 1.1, 1.5, 2.1, 2.2, 2.3, 2.4, 3.3, 4.1, 5.1, 6.1, 8.1, 8.2, 8.3, 13.1, 13.2_

  - [x] 8.2 Add integration settings to `backend/app/config.py`
    - Add `WEBHOOK_RETRY_DELAYS` (list of ints, default `[5, 30, 120]`), `DEFAULT_RATE_LIMIT_DAILY_CLOUD` (100), `DEFAULT_RATE_LIMIT_DAILY_LOCAL` (1000), `DEFAULT_RATE_LIMIT_PER_MINUTE` (10)
    - _Requirements: 1.4, 11.3_

  - [x] 8.3 Register integration router in `backend/app/main.py`
    - Import `integrations_router` and add `api_router.include_router(integrations_router)` following the existing pattern
    - _Requirements: (wiring)_

  - [x] 8.4 Write property test for rate limit header consistency
    - **Property 5: Rate Limit Header Consistency**
    - For any successful response from `/api/v1/integrations/*`, assert `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers are present and `Remaining` = `Limit - usage_today`
    - **Validates: Requirements 3.3**

  - [x] 8.5 Write property test for error response format consistency
    - **Property 13: Error Response Format Consistency**
    - For any error response (401, 403, 404, 422, 429, 500, 503), assert body conforms to `{"error": str, "message": str, "details": dict}` with correct error code
    - **Validates: Requirements 13.1, 13.2**

- [x] 9. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Write unit and integration tests
  - [x] 10.1 Write unit tests for API key service in `backend/tests/unit/integration_api/test_api_key_service.py`
    - Test default scopes assignment when none specified
    - Test default rate limits for cloud mode (100) and local mode (1000)
    - Test key deactivation preserves record (soft-delete)
    - Test `key_prefix` extraction from raw key
    - Test `last_used_at` update on validation
    - Test daily usage counter reset at midnight UTC
    - Test per-minute window tracking
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.5, 3.1_

  - [x] 10.2 Write unit tests for context injector in `backend/tests/unit/integration_api/test_context_injector.py`
    - Test list fields joined with commas
    - Test boolean fields rendered as "Yes"/"No"
    - Test `deal_value` formatted as currency string
    - Test empty/missing context produces no preamble
    - Test custom_fields included in preamble
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 10.3 Write unit tests for webhook dispatcher in `backend/tests/unit/integration_api/test_webhook_dispatcher.py`
    - Test 3 retries with correct delays in cloud mode
    - Test single attempt in local mode
    - Test failure logging after all retries exhausted
    - Test HMAC signature included in `X-A2A-Signature` header
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 10.4 Write unit tests for integration models in `backend/tests/unit/integration_api/test_integration_models.py`
    - Test `SimulateRequest` validator: `scenario_builder` required when `_dynamic`, forbidden otherwise
    - Test `callback_url` HTTPS validation
    - Test `CreateKeyRequest` field constraints
    - _Requirements: 14.1, 14.2_

  - [x] 10.5 Write integration tests in `backend/tests/integration/test_integration_endpoints.py`
    - Test health endpoint returns 200 with all required fields
    - Test scenarios endpoint returns filtered list without internal fields
    - Test simulate endpoint returns 201 with `session_id`, `viewer_url`, `status`
    - Test session status endpoint returns correct fields for running/completed sessions
    - Test key management: create and deactivate
    - Test auth errors: 401 for missing/invalid key, 403 for deactivated key, 403 for insufficient scope
    - Test rate limit 429 response includes `retry_after_seconds`, `limit`, `used`
    - Test scenario not found returns 404
    - Test session not found returns 404
    - Test dynamic scenario with `_dynamic` scenario_id
    - Test `triggered_by` with valid email sets `owner_email`
    - Test `triggered_by` with display name uses synthetic owner
    - Test rate limit headers present on all successful responses
    - Test all error responses match `IntegrationErrorResponse` schema
    - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4, 3.2, 3.3, 4.1, 5.1, 6.1, 6.2, 6.3, 8.1, 8.2, 8.3, 9.1, 9.3, 10.1, 13.1, 13.2_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 14 universal correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- All persistence uses in-memory SQLite (`:memory:`) in tests — no cloud dependencies
- The implementation language is Python, matching the existing backend stack
