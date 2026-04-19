# Requirements Document

## Introduction

This document defines the requirements for the CRM Integration API — a thin API layer on top of the existing JuntoAI A2A negotiation engine. The API enables external CRM systems (EspoCRM, HubSpot, Salesforce, custom integrations) to programmatically trigger AI negotiation simulations, poll for results, and receive completion callbacks. It adds API key authentication, rate limiting, CRM context injection, and async execution to the existing core engine without duplicating any engine logic.

Reference architecture documents:
- `docs/A2A Integration API — Architecture & Documentation.md`
- `docs/CRM Integration Plugin — Universal Architecture Guide.md`

## Glossary

- **Integration_API**: The FastAPI router and service layer exposing `/api/v1/integrations/*` endpoints for external system consumption.
- **API_Key_Service**: The service responsible for generating, hashing, validating, and rate-limiting API keys.
- **API_Key_Store**: The persistence layer (Firestore or SQLite) for API key records, following the existing dual-mode `Protocol` pattern.
- **Context_Injector**: The component that transforms CRM context fields into a structured preamble prepended to agent persona prompts at simulation start.
- **Webhook_Dispatcher**: The component that delivers HMAC-SHA256 signed HTTP POST callbacks to external systems when simulations complete.
- **Rate_Limiter**: The component that enforces per-key daily and per-minute request limits and attaches rate limit headers to all responses.
- **API_Key**: A secret credential in the format `a2a_live_<base64url-encoded random bytes>` used to authenticate Integration API requests via the `X-API-Key` header.
- **Scope**: A permission string (`simulate`, `read_sessions`, `list_scenarios`, `manage_keys`) attached to an API key that controls which endpoints the key can access.
- **Context_Preamble**: A structured text block built from CRM data fields, prepended to each agent's persona prompt to influence negotiation behavior with real-world context.
- **Callback_URL**: An optional HTTPS URL provided in a simulate request where the Webhook_Dispatcher sends completion notifications.
- **Key_Prefix**: The first 4 characters after `a2a_live_` stored alongside the key hash for admin identification without exposing the full key.
- **Triggered_By**: An optional field on simulate requests identifying the individual CRM user (email or display name) who initiated the simulation. Used for attribution and audit, not for authentication.
- **Dynamic_Scenario**: A scenario generated on-the-fly by the BuilderLLMAgent from CRM profile data (my persona + their persona + deal context), as opposed to a pre-built scenario from the ScenarioRegistry.
- **Scenario_Builder_Object**: The structured input in a simulate request that describes both parties and the deal context, used to generate a Dynamic_Scenario.

## Requirements

### Requirement 1: API Key Generation and Storage

**User Story:** As an integration administrator, I want to generate organization-level API keys with specific scopes and rate limits, so that I can control how my CRM system accesses the A2A engine on behalf of all users in my organization.

#### Acceptance Criteria

1. WHEN a valid `manage_keys`-scoped API key is used to call `POST /api/v1/integrations/keys` with an `org_name` and optional `scopes` and `rate_limit_daily`, THE API_Key_Service SHALL generate a new API key in the format `a2a_live_<base64url-encoded 32 random bytes>`, return the raw key exactly once in the response, and persist only the SHA-256 hash alongside the key metadata.
2. THE API_Key_Service SHALL store each API key record with the fields: `key_id`, `key_hash`, `key_prefix` (first 4 chars after `a2a_live_`), `org_name`, `created_by_email`, `scopes`, `rate_limit_daily`, `rate_limit_per_minute`, `active`, `created_at`, `last_used_at`, and `usage_today`.
3. WHEN no `scopes` are specified in the creation request, THE API_Key_Service SHALL assign the default scopes: `simulate`, `read_sessions`, `list_scenarios`.
4. WHEN no `rate_limit_daily` is specified, THE API_Key_Service SHALL assign a default daily limit of 100 in cloud mode and 1000 in local mode.
5. WHEN a valid `manage_keys`-scoped API key is used to call `DELETE /api/v1/integrations/keys/{key_id}`, THE API_Key_Service SHALL set the key's `active` field to `false` without deleting the record, preserving the audit trail.
6. API keys are per-organization, not per-user. A single key is stored server-side in the CRM admin configuration and shared by all CRM users in that organization. Individual CRM users are identified via the `triggered_by` field on each simulate request (see Requirement 6), not via separate API keys.

### Requirement 2: API Key Validation and Authentication

**User Story:** As the A2A system, I want to validate API keys on every integration request, so that only authorized external systems can access the API.

#### Acceptance Criteria

1. WHEN a request arrives at any `/api/v1/integrations/*` endpoint with an `X-API-Key` header, THE API_Key_Service SHALL compute the SHA-256 hash of the provided key and query the API_Key_Store for a matching `key_hash`.
2. IF no matching key hash is found, THEN THE Integration_API SHALL return HTTP 401 with error code `invalid_api_key`.
3. IF a matching key is found but `active` is `false`, THEN THE Integration_API SHALL return HTTP 403 with error code `key_deactivated`.
4. IF a matching key is found but the required scope for the endpoint is not in the key's `scopes` list, THEN THE Integration_API SHALL return HTTP 403 with error code `insufficient_scope`.
5. WHEN a key is successfully validated, THE API_Key_Service SHALL update the key's `last_used_at` timestamp.

### Requirement 3: Rate Limiting

**User Story:** As the A2A system, I want to enforce per-key rate limits, so that no single integration consumer can exhaust LLM API resources or degrade service for others.

#### Acceptance Criteria

1. THE Rate_Limiter SHALL track daily usage (`usage_today`) per API key and reset the counter at midnight UTC.
2. IF a request arrives and the key's `usage_today` is greater than or equal to `rate_limit_daily`, THEN THE Rate_Limiter SHALL return HTTP 429 with error code `rate_limit_exceeded`, a `retry_after_seconds` field, and the `limit` and `used` counts.
3. THE Integration_API SHALL include the headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` on all successful responses from `/api/v1/integrations/*` endpoints.
4. IF a request arrives and the key has exceeded its `rate_limit_per_minute` within the current 60-second window, THEN THE Rate_Limiter SHALL return HTTP 429 with error code `rate_limit_exceeded`.

### Requirement 4: Health Check Endpoint

**User Story:** As a CRM plugin developer, I want a health check endpoint that validates my API key and shows rate limit status, so that I can verify connectivity and monitor usage from the CRM admin panel.

#### Acceptance Criteria

1. WHEN a valid API key is used to call `GET /api/v1/integrations/health`, THE Integration_API SHALL return HTTP 200 with the fields: `status` ("ok"), `version` (from app settings), `key_valid` (true), `org_name`, and a `rate_limit` object containing `daily_limit`, `used_today`, `remaining`, and `resets_at` (ISO 8601 UTC midnight timestamp).

### Requirement 5: List Scenarios Endpoint

**User Story:** As a CRM plugin, I want to fetch available negotiation scenarios with their metadata, toggles, and context field definitions, so that I can render a scenario picker UI and auto-fill CRM entity fields.

#### Acceptance Criteria

1. WHEN a valid API key with `list_scenarios` scope calls `GET /api/v1/integrations/scenarios`, THE Integration_API SHALL return a list of available scenarios from the ScenarioRegistry, each containing: `id`, `name`, `description`, `category`, `difficulty`, `agents` (role, name, type only — no `model_id` or `persona_prompt`), `toggles` (id, label, target_agent_role only — no `hidden_context_payload`), and `context_fields` with `required` and `optional` arrays.
2. THE Integration_API SHALL exclude internal implementation details (`model_id`, `persona_prompt`, `hidden_context_payload`, `budget`, `goals`, `output_fields`) from the scenario response.

### Requirement 6: Create Simulation Endpoint

**User Story:** As a CRM plugin, I want to trigger a negotiation simulation with CRM context data and receive a session reference immediately, so that the CRM user does not wait for the full simulation to complete.

#### Acceptance Criteria

1. WHEN a valid API key with `simulate` scope calls `POST /api/v1/integrations/simulate` with a valid `scenario_id`, optional `active_toggles`, optional `context` object, optional `callback_url`, and optional `triggered_by` (email or name of the CRM user who initiated the simulation), THE Integration_API SHALL validate the scenario server-side against the ScenarioRegistry, validate that all `active_toggles` reference valid toggle IDs defined in the scenario, create a new negotiation session, start the simulation as a background task, create a share record for the viewer URL, and return HTTP 201 with `session_id`, `status` ("running"), `viewer_url`, `estimated_duration_seconds`, and `created_at`.
2. IF the `scenario_id` does not exist in the ScenarioRegistry, THEN THE Integration_API SHALL return HTTP 404 with error code `scenario_not_found`.
3. IF any value in `active_toggles` does not match a toggle ID defined in the resolved scenario, THEN THE Integration_API SHALL return HTTP 422 with error code `validation_error` and a message listing the invalid toggle IDs.
4. IF the request body fails Pydantic validation, THEN THE Integration_API SHALL return HTTP 422 with error code `validation_error`.
5. ALL scenario and toggle validation SHALL happen server-side in the A2A backend. CRM plugins SHALL NOT perform validation logic — they only present options fetched from `GET /integrations/scenarios` and submit the user's selection.
6. WHEN `triggered_by` is provided, THE Integration_API SHALL persist it on the session record so simulation history can be attributed to individual CRM users within the organization.

### Requirement 7: CRM Context Injection

**User Story:** As a CRM user, I want the AI agents to be aware of real contact and deal data from my CRM, so that the negotiation simulation is personalized and relevant to the actual business context.

#### Acceptance Criteria

1. WHEN a simulate request includes a `context` object, THE Context_Injector SHALL build a structured text preamble from the standard fields (`contact_name`, `company`, `role`, `industry`, `deal_value`, `deal_stage`, `pain_points`, `competing_vendors`, `budget_approved`) and any `custom_fields`.
2. THE Context_Injector SHALL prepend the context preamble to each agent's `persona_prompt` before the negotiation session is created.
3. WHEN a `context` field value is a list, THE Context_Injector SHALL join the list elements with commas. WHEN a value is a boolean, THE Context_Injector SHALL render it as "Yes" or "No". WHEN `deal_value` is numeric, THE Context_Injector SHALL format it as a currency string.
4. WHEN the `context` object is empty or not provided, THE Context_Injector SHALL start the simulation without any context preamble, using the original persona prompts unmodified.
5. FOR ALL valid context objects, building a preamble and then parsing the preamble's key-value lines SHALL recover the original field names and values (round-trip property).

### Requirement 8: Session Status Polling Endpoint

**User Story:** As a CRM plugin, I want to poll for simulation status and results, so that I can update the CRM record when the negotiation completes.

#### Acceptance Criteria

1. WHEN a valid API key with `read_sessions` scope calls `GET /api/v1/integrations/sessions/{session_id}` for a running session, THE Integration_API SHALL return HTTP 200 with `session_id`, `scenario_id`, `scenario_name`, `status` ("running"), `viewer_url`, `turns_completed`, `current_offer`, and `created_at`.
2. WHEN a valid API key with `read_sessions` scope calls `GET /api/v1/integrations/sessions/{session_id}` for a completed session, THE Integration_API SHALL return HTTP 200 with the running fields plus `status` ("completed"), `completed_at`, and an `outcome` object containing exactly these fields:
   - `deal_status`: one of "Agreed", "Blocked", "Failed"
   - `summary`: a 1-2 sentence human-readable outcome description (e.g., "Deal reached at €125,000 with 3 days remote work per week.")
   - `final_offer`: the final numeric offer value (float)
   - `turns_completed`: number of negotiation turns (int)
   - `warning_count`: number of regulator warnings issued (int)
   - `duration_seconds`: wall-clock simulation duration (int)
   - `participant_summaries`: array of objects, each with `role` (string), `name` (string), `agent_type` ("negotiator"/"regulator"/"observer"), and `summary` (1-2 sentence string describing the agent's final position or stance)
   - `evaluation_scores`: object with `fairness` (1-10), `mutual_respect` (1-10), `value_creation` (1-10), `satisfaction` (1-10), `overall_score` (1-10), or `null` if evaluation was not run
3. IF the `session_id` does not exist, THEN THE Integration_API SHALL return HTTP 404 with error code `session_not_found`.
4. THE Integration_API SHALL NOT return any internal session data in the status response — no raw history, no hidden_context, no custom_prompts, no model_overrides, no agent_states, no agent_memories. Only the fields listed in criteria 1 and 2 are exposed.

### Requirement 9: Cross-Visibility — CRM-Triggered Sessions in A2A Dashboard

**User Story:** As a user who triggers simulations from EspoCRM, I want to see those simulations in my A2A session history when I log into the web app, so that I have a single view of all my simulations regardless of where I triggered them.

#### Acceptance Criteria

1. WHEN `triggered_by` is a valid email address, THE Integration_API SHALL store it as the `owner_email` on the session record, making the session visible in the existing `/negotiation/history` endpoint for that email.
2. WHEN `triggered_by` is a valid email address, THE Integration_API SHALL also store a `source` field on the session record with the value `"integration"` and an `integration_org` field with the API key's `org_name`, so the A2A frontend can distinguish CRM-triggered sessions from manually-triggered ones.
3. WHEN `triggered_by` is not a valid email (e.g., a display name like "Jane Smith") or is not provided, THE Integration_API SHALL store the `owner_email` as `"integration:<org_name>"` (a synthetic owner) and the session SHALL NOT appear in any user's personal history. It remains accessible only via the Integration API's `GET /integrations/sessions/{session_id}` endpoint.
4. THE existing `/negotiation/history` endpoint SHALL NOT require any changes — it already filters by `owner_email`, so CRM-triggered sessions with a real email as `owner_email` will appear automatically.

### Requirement 10: Dynamic Scenario Building from CRM Data

**User Story:** As a CRM user, I want to simulate a negotiation between myself and a specific contact from my CRM, with agents that represent my persona and the contact's persona based on real CRM data, so that I can rehearse an upcoming call with a realistic AI counterpart.

#### Acceptance Criteria

1. WHEN a valid API key with `simulate` scope calls `POST /api/v1/integrations/simulate` with `scenario_id` set to `"_dynamic"` and a `scenario_builder` object in the request body, THE Integration_API SHALL use the existing Scenario Builder (`BuilderLLMAgent`) to generate a complete `ArenaScenario` from the provided CRM data, then run the simulation using that generated scenario.
2. THE `scenario_builder` object SHALL accept the following fields:
   - `simulation_type`: required string — the type of interaction to simulate (e.g., "investor_pitch", "sales_call", "contract_negotiation", "salary_negotiation")
   - `my_profile`: required object — the CRM user's persona with fields: `name`, `role`, `company`, `goals` (list of strings), `constraints` (list of strings), `tone` (optional, e.g., "assertive", "collaborative")
   - `their_profile`: required object — the contact's persona with fields: `name`, `role`, `company`, `industry`, `goals` (list of strings), `constraints` (list of strings), `tone` (optional)
   - `deal_context`: optional object — deal-specific data: `value`, `stage`, `competing_vendors` (list), `deadline`, `key_terms` (list of strings)
   - `regulator`: optional object — if provided, adds a regulator/observer agent: `name`, `role`, `rules` (list of strings describing what to enforce)
   - `additional_instructions`: optional string — free-text instructions for scenario generation (e.g., "The client is very price-sensitive and has a competing offer from Salesforce")
3. THE Integration_API SHALL pass the `scenario_builder` data to the `BuilderLLMAgent` which generates a complete `ArenaScenario` JSON including agent definitions, budgets, persona prompts, toggles, and negotiation parameters. The generated scenario SHALL be validated against the `ArenaScenario` Pydantic model before execution.
4. IF the `BuilderLLMAgent` fails to generate a valid scenario (validation error, LLM timeout, or malformed output), THEN THE Integration_API SHALL return HTTP 422 with error code `scenario_generation_failed` and a message describing what went wrong.
5. THE generated scenario SHALL be persisted in the custom scenario store (same as the existing builder save flow) linked to the `triggered_by` email or the API key's `org_name`, so it can be re-run later without regeneration.
6. WHEN `scenario_id` is NOT `"_dynamic"`, THE Integration_API SHALL use the existing flow (look up scenario in ScenarioRegistry, inject context, run simulation) — the dynamic builder is an additional capability, not a replacement.

### Requirement 11: Webhook Completion Callbacks

**User Story:** As a CRM plugin developer, I want to receive an automatic callback when a simulation completes, so that the CRM can update in real time without polling.

#### Acceptance Criteria

1. WHEN a simulation completes and the originating simulate request included a `callback_url`, THE Webhook_Dispatcher SHALL send an HTTP POST to the `callback_url` with a JSON body containing `event` ("simulation.completed"), `session_id`, `scenario_id`, `status`, `outcome` (deal_status, summary, final_offer, turns_completed), `viewer_url`, and `timestamp`.
2. THE Webhook_Dispatcher SHALL sign the request body with HMAC-SHA256 using the originating API key as the secret and include the signature in the `X-A2A-Signature` header in the format `sha256=<hex digest>`.
3. IF the webhook delivery fails (non-2xx response or network error), THEN THE Webhook_Dispatcher SHALL retry up to 3 times with exponential backoff delays of 5 seconds, 30 seconds, and 120 seconds.
4. IF all 3 retry attempts fail, THEN THE Webhook_Dispatcher SHALL log the failure and cease further delivery attempts for that callback.
5. WHILE operating in local mode, THE Webhook_Dispatcher SHALL attempt delivery once without retries (best-effort).

### Requirement 12: Dual-Mode Persistence (Firestore + SQLite)

**User Story:** As a developer running the A2A engine locally, I want the Integration API to work with SQLite just like it does with Firestore in cloud mode, so that I can develop and test integrations without any cloud dependencies.

#### Acceptance Criteria

1. THE API_Key_Store SHALL implement the same `Protocol` interface for both Firestore (cloud mode) and SQLite (local mode), following the existing `SessionStore` and `ShareStore` dual-mode pattern in `backend/app/db/base.py`.
2. THE `backend/app/db/__init__.py` module SHALL provide a `get_api_key_store()` factory function that returns the appropriate implementation based on `settings.RUN_MODE`.
3. WHEN running in local mode, THE API_Key_Store SHALL use the same SQLite database file specified by `settings.SQLITE_DB_PATH` and create the `integration_api_keys` table on first access if it does not exist.

### Requirement 13: Error Response Consistency

**User Story:** As a CRM plugin developer, I want all error responses to follow a consistent JSON format, so that I can implement reliable error handling in my integration code.

#### Acceptance Criteria

1. THE Integration_API SHALL return all error responses in the format `{"error": "<error_code>", "message": "<human-readable description>", "details": {}}` for status codes 401, 403, 404, 422, 429, 500, and 503.
2. THE Integration_API SHALL use the following error codes consistently: `invalid_api_key` (401), `key_deactivated` (403), `insufficient_scope` (403), `scenario_not_found` (404), `session_not_found` (404), `validation_error` (422), `scenario_generation_failed` (422), `rate_limit_exceeded` (429), `simulation_failed` (500), `service_unavailable` (503).

### Requirement 14: Integration API Pydantic Models

**User Story:** As a backend developer, I want well-defined Pydantic V2 request and response models for all integration endpoints, so that input validation and API documentation are automatic and consistent.

#### Acceptance Criteria

1. THE Integration_API SHALL define Pydantic V2 models for: `CreateKeyRequest`, `CreateKeyResponse`, `SimulateRequest`, `SimulateResponse`, `SessionStatusResponse`, `ScenarioListResponse`, `HealthResponse`, `WebhookPayload`, `IntegrationErrorResponse`, `ScenarioBuilderInput`, `MyProfileInput`, `TheirProfileInput`, `DealContextInput`, and `RegulatorInput`.
2. THE SimulateRequest model SHALL validate that `scenario_id` is a non-empty string (use `"_dynamic"` for dynamic scenario building), `active_toggles` is an optional list of strings, `context` is an optional dict with known standard fields and a `custom_fields` sub-dict, `callback_url` is an optional valid HTTPS URL (or HTTP in local mode), `triggered_by` is an optional non-empty string, and `scenario_builder` is an optional `ScenarioBuilderInput` object (required when `scenario_id` is `"_dynamic"`, forbidden otherwise).
3. FOR ALL valid Pydantic model instances, serializing to JSON and deserializing back SHALL produce an equivalent model instance (round-trip property).
