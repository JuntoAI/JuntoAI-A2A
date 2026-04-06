# Implementation Plan: AI Scenario Builder

## Dependency

This spec requires **Spec 140 (User Profile Token Upgrade)** to be fully implemented before starting. The builder depends on:
- `profiles` Firestore collection and `ProfileClient` for user identity verification
- `TierCalculator` for tier-aware token deduction (20/50/100 tokens/day)
- Custom scenarios stored as sub-collection `profiles/{email}/custom_scenarios`

## Overview

Incremental implementation of the AI-powered scenario builder: foundational backend models and SSE events first, then session management and LLM agent, then health check analyzer with sub-computations, then Firestore persistence (as profile sub-collection), then API router with all endpoints, then frontend components (modal, chat, preview, progress, health report), then ScenarioSelector updates, then integration wiring. Each task builds on the previous — nothing is left orphaned.

## Tasks

- [x] 1. Backend data models and SSE events
  - [x] 1.1 Create builder SSE event models (`backend/app/builder/events.py`)
    - Create `backend/app/builder/__init__.py` and `backend/app/builder/events.py`
    - Define Pydantic models: `BuilderTokenEvent`, `BuilderJsonDeltaEvent`, `BuilderCompleteEvent`, `BuilderErrorEvent`, `HealthCheckStartEvent`, `HealthCheckFindingEvent`, `HealthCheckCompleteEvent`
    - Each model must have a `event_type` Literal field matching the design discriminators
    - `BuilderJsonDeltaEvent` must include `section: str` and `data: dict`
    - `HealthCheckFindingEvent` must include `check_name`, `severity` (Literal["critical","warning","info"]), `agent_role: str | None`, `message: str`
    - _Requirements: 12.1, 12.2, 12.3, 23.1, 23.2, 23.3, 23.4_

  - [x] 1.2 Create health check report models (`backend/app/builder/models.py`)
    - Define `AgentPromptScore`, `BudgetOverlapResult`, `StallRiskResult`, `HealthCheckReport`, `CustomScenarioDocument`
    - `HealthCheckReport.readiness_score` must be `Field(ge=0, le=100)`
    - `HealthCheckReport.tier` must be `Literal["Ready", "Needs Work", "Not Ready"]`
    - `BudgetOverlapResult` must include `overlap_zone`, `overlap_percentage`, `target_gap`, `agreement_threshold`, `threshold_ratio`
    - _Requirements: 22.1, 22.2, 22.5, 17.5_

  - [x] 1.3 Write property test: SSE event structure and wire format (Property 3)
    - **Property 3: Builder SSE event structure and wire format**
    - Create `backend/tests/property/test_builder_properties.py`
    - For each builder SSE event model, verify `format_sse_event(event, event_id)` produces `id: <id>\ndata: <valid JSON>\n\n` with correct `event_type` literal and all required fields (note: the existing `format_sse_event` includes an `id:` field when `event_id` is provided — builder events use this for reconnection support)
    - Use Hypothesis `st.one_of()` strategy generating all 7 event types
    - **Validates: Requirements 12.1, 12.2, 12.3, 23.1, 23.2, 23.3, 23.4**


- [x] 2. Builder session management
  - [x] 2.1 Implement `BuilderSessionManager` (`backend/app/builder/session_manager.py`)
    - Define `BuilderSession` dataclass with fields: `session_id`, `email`, `conversation_history: list[dict]`, `partial_scenario: dict`, `message_count: int`, `created_at`, `last_activity`
    - Implement `create_session(email) -> BuilderSession` generating a UUID session_id
    - Implement `get_session(session_id) -> BuilderSession | None`
    - Implement `add_message(session_id, role, content)` — must reject if `message_count >= 50` for user messages
    - Implement `update_scenario(session_id, section, data)` — merges section data into `partial_scenario`
    - Implement `delete_session(session_id)`
    - Implement `cleanup_stale(max_age_minutes=60) -> int` — removes sessions older than TTL
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 2.2 Write property test: Session conversation history preservation (Property 11)
    - **Property 11: Session conversation history preservation**
    - For any sequence of N messages added to a BuilderSession, `conversation_history` contains exactly N entries in order with matching role and content
    - **Validates: Requirements 9.1**

  - [x] 2.3 Write property test: Session message limit enforcement (Property 12)
    - **Property 12: Session message limit enforcement**
    - For any session with 50 user messages, the 51st user message is rejected and `message_count` remains 50
    - **Validates: Requirements 9.4**

  - [x] 2.4 Write unit tests for BuilderSessionManager
    - Test create, get, add_message, update_scenario, delete, cleanup_stale
    - Test message limit enforcement at boundary (49, 50, 51)
    - Test stale session cleanup with mocked timestamps
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 4. LinkedIn URL detection and progress computation utilities
  - [x] 4.1 Implement LinkedIn URL detector (`backend/app/builder/linkedin.py`)
    - Create a function `is_linkedin_url(text: str) -> bool` matching `https://www.linkedin.com/in/.+`
    - _Requirements: 8.1_

  - [x] 4.2 Write property test: LinkedIn URL pattern recognition (Property 10)
    - **Property 10: LinkedIn URL pattern recognition**
    - For any string matching `https://www\.linkedin\.com/in/.+`, detector returns True; for non-matching strings, returns False
    - Use Hypothesis `st.from_regex` for positive cases and `st.text()` filtered for negative cases
    - **Validates: Requirements 8.1**

  - [x] 4.3 Implement progress percentage calculator (`backend/app/builder/progress.py`)
    - Create `compute_progress(partial_scenario: dict) -> int` that counts populated top-level sections (id, name, description, agents, toggles, negotiation_params, outcome_receipt) and returns `round((count / 7) * 100)`
    - A section is "populated" if the key exists and the value is non-empty (non-empty string, non-empty list, non-empty dict)
    - _Requirements: 5.1_

  - [x] 4.4 Write property test: Progress percentage computation (Property 4)
    - **Property 4: Progress percentage computation**
    - For any subset of the 7 sections being populated, progress equals `round((populated_count / 7) * 100)`
    - Use Hypothesis `st.sets(st.sampled_from([...]))` to generate section subsets
    - **Validates: Requirements 5.1**


- [x] 5. Health check sub-computations
  - [x] 5.1 Implement budget overlap analysis (`backend/app/builder/health_checks/budget_overlap.py`)
    - Create `backend/app/builder/health_checks/__init__.py`
    - Implement `compute_budget_overlap(agents: list[AgentDefinition]) -> BudgetOverlapResult`
    - Compute overlap zone as `[max(min1, min2), min(max1, max2)]` for each negotiator pair
    - Flag "no_overlap" if no intersection exists; flag "excessive_overlap" if overlap > 50% of both ranges
    - Compute target gap vs agreement_threshold ratio; flag if gap < 3x threshold
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [x] 5.2 Write property test: Budget overlap computation (Property 15)
    - **Property 15: Budget overlap computation and flagging**
    - For any two budget ranges, overlap zone is `[max(min1,min2), min(max1,max2)]` when valid, else None
    - Verify "no_overlap" and "excessive_overlap" flags trigger correctly
    - **Validates: Requirements 17.1, 17.2, 17.3**

  - [x] 5.3 Write property test: Agreement threshold vs target gap (Property 16)
    - **Property 16: Agreement threshold vs target gap analysis**
    - For any scenario with negotiators, verify gap < 3x threshold triggers convergence warning
    - **Validates: Requirements 17.4, 17.5**


  - [x] 5.4 Implement turn order and turn limit validation (`backend/app/builder/health_checks/turn_sanity.py`)
    - Implement `check_turn_sanity(agents, negotiation_params) -> tuple[int, list[HealthCheckFindingEvent]]`
    - Verify every agent role appears in turn_order; flag missing negotiators as critical
    - Verify max_turns >= 2 * unique roles in turn_order; flag insufficient turns as warning
    - Verify regulator agents appear at least once per cycle
    - Return turn_sanity_score (0-100) and list of findings
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_

  - [x] 5.5 Write property test: Turn order completeness and cycle validation (Property 17)
    - **Property 17: Turn order completeness and cycle validation**
    - For any scenario, missing negotiators flagged as critical, insufficient turns flagged as warning
    - **Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5**

  - [x] 5.6 Implement stall risk assessment (`backend/app/builder/health_checks/stall_risk.py`)
    - Implement `assess_stall_risk(agents, negotiation_params) -> StallRiskResult`
    - Flag "instant_convergence_risk" if target prices within agreement_threshold
    - Flag "price_stagnation_risk" if budget range (max-min) < 3 * agreement_threshold
    - Return stall_risk_score 0-100
    - _Requirements: 20.1, 20.2, 20.4, 20.5_

  - [x] 5.7 Write property test: Stall risk assessment (Property 18)
    - **Property 18: Stall risk assessment**
    - Verify instant_convergence_risk and price_stagnation_risk flags trigger correctly
    - Verify stall_risk_score is in [0, 100]
    - **Validates: Requirements 20.1, 20.2, 20.4**


  - [x] 5.8 Implement readiness score computation (`backend/app/builder/health_checks/readiness.py`)
    - Implement `compute_readiness_score(prompt_quality, tension, budget_overlap, toggle_effectiveness, turn_sanity, stall_risk) -> tuple[int, str]`
    - Formula: `round(pq*0.25 + t*0.20 + bo*0.20 + te*0.15 + ts*0.10 + (100-sr)*0.10)`
    - Tier: "Ready" 80-100, "Needs Work" 60-79, "Not Ready" 0-59
    - _Requirements: 22.1, 22.2_

  - [x] 5.9 Write property test: Readiness score computation and tier classification (Property 19)
    - **Property 19: Readiness score computation and tier classification**
    - For any 6 sub-scores in [0,100], verify weighted formula and tier boundaries
    - Use Hypothesis `st.integers(min_value=0, max_value=100)` for each sub-score
    - **Validates: Requirements 22.1, 22.2, 14.4, 14.5**

- [x] 6. Checkpoint — Ensure all health check sub-computation tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 7. Health Check Analyzer (LLM-powered)
  - [x] 7.1 Implement `HealthCheckAnalyzer` (`backend/app/builder/health_check.py`)
    - Implement `async analyze(scenario: ArenaScenario, gold_standard_scenarios: list[ArenaScenario]) -> AsyncIterator[HealthCheckSSEEvent]`
    - Load gold-standard scenarios (talent-war, b2b-sales, ma-buyout, freelance-gig, urban-development) as few-shot examples
    - Run 7 checks in sequence: prompt quality, goal tension, budget overlap, toggle effectiveness, turn sanity, stall risk, regulator feasibility
    - For prompt quality (Req 15) and goal tension (Req 16): use Claude Opus 4.6 via Vertex AI with structured prompts
    - For toggle effectiveness (Req 18) and regulator feasibility (Req 21): use Claude Opus 4.6 with agent-specific evaluation
    - For budget overlap, turn sanity, stall risk: delegate to the pure-function sub-computations from task 5
    - Stream `HealthCheckStartEvent`, individual `HealthCheckFindingEvent`s, then `HealthCheckCompleteEvent` with full report
    - Assemble final `HealthCheckReport` with weighted readiness_score via `compute_readiness_score`
    - Order recommendations: critical findings first, then warnings sorted by score impact
    - _Requirements: 14.1, 14.2, 14.6, 15.1, 15.2, 15.3, 15.4, 16.1, 16.2, 16.3, 16.4, 18.1, 18.2, 18.3, 18.4, 21.1, 21.2, 21.3, 21.4, 22.3, 22.4, 22.5_

  - [x] 7.2 Write property test: Health check report structure completeness (Property 20)
    - **Property 20: Health check report structure completeness**
    - For any HealthCheckReport, verify all required fields present, every critical/warning finding has a recommendation, recommendations ordered by severity
    - **Validates: Requirements 22.3, 22.4, 22.5, 15.4, 20.5**

  - [x] 7.3 Write unit tests for HealthCheckAnalyzer
    - Mock Vertex AI calls, verify correct SSE event sequence emitted
    - Test that gold-standard scenarios are loaded and included in prompts
    - Test prompt quality evaluation per-agent scoring
    - Test goal tension detection for opposing vs aligned goals
    - Test toggle effectiveness evaluation
    - Test regulator feasibility check
    - _Requirements: 14.1, 14.2, 14.6, 15.1, 16.1, 18.1, 21.1_


- [x] 8. Builder LLM Agent
  - [x] 8.1 Implement `BuilderLLMAgent` (`backend/app/builder/llm_agent.py`)
    - Implement `async stream_response(conversation_history, partial_scenario, system_prompt) -> AsyncIterator[BuilderSSEEvent]`
    - Use Claude Opus 4.6 via Vertex AI (same model config as health check)
    - System prompt instructs structured collection order: metadata → agents → toggles → params → receipt
    - Emit `BuilderTokenEvent` for streaming tokens, `BuilderJsonDeltaEvent` when a section is populated, `BuilderCompleteEvent` at end
    - Emit `BuilderErrorEvent` on LLM call failure
    - Detect LinkedIn URLs in user messages via `is_linkedin_url` and trigger persona generation flow
    - Enforce minimum 2 agents with at least 1 negotiator before proceeding past agents section
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 8.1, 8.2, 8.3, 8.4_

  - [x] 8.2 Write property test: Agent minimum validation (Property 5)
    - **Property 5: Agent minimum validation**
    - For any partial scenario with <2 agents or no negotiator, validation rejects proceeding past agents section
    - **Validates: Requirements 3.7**

  - [x] 8.3 Write unit tests for BuilderLLMAgent
    - Mock Vertex AI, verify token streaming produces correct SSE events
    - Test LinkedIn URL detection triggers persona generation
    - Test agent minimum enforcement
    - Test error handling on LLM failure produces BuilderErrorEvent
    - _Requirements: 3.3, 3.4, 3.7, 8.1, 8.2_


- [x] 9. Custom Scenario Store (Firestore CRUD)
  - [x] 9.1 Implement `CustomScenarioStore` (`backend/app/builder/scenario_store.py`)
    - Implement using Firestore sub-collection: `profiles/{email}/custom_scenarios/{scenario_id}`
    - Obtain Firestore `AsyncClient` via the shared `get_firestore_db()` factory from `backend/app/db/__init__.py` (introduced by Spec 140) — do NOT create a new Firestore client instance
    - Constructor takes `ProfileClient` (from Spec 140) dependency to verify profile existence
    - Implement `async save(email, scenario: ArenaScenario) -> str` — verify profile exists (403 if not), generate scenario_id, store document at `profiles/{email}/custom_scenarios/{scenario_id}`, enforce MAX_PER_USER=20
    - Implement `async list_by_email(email) -> list[dict]`
    - Implement `async get(email, scenario_id) -> dict | None`
    - Implement `async delete(email, scenario_id) -> bool`
    - Implement `async count_by_email(email) -> int`
    - Document fields: `scenario_json`, `created_at`, `updated_at` (email is implicit from parent path, NOT stored in document)
    - For local mode (`RUN_MODE=local`): implement `SQLiteCustomScenarioStore` that stores custom scenarios in the same SQLite database (`data/juntoai.db`) in a `custom_scenarios` table with columns: `scenario_id`, `email`, `scenario_json` (JSON text), `created_at`, `updated_at`. Add a `get_custom_scenario_store()` factory in `backend/app/db/__init__.py`
    - _Requirements: 7.1, 7.2, 7.5, 7.6_

  - [x] 9.2 Write property test: Scenario persistence round-trip (Property 7)
    - **Property 7: Scenario persistence round-trip**
    - For any valid ArenaScenario and email with an existing profile, save then retrieve from `profiles/{email}/custom_scenarios` produces equivalent scenario via `load_scenario_from_dict`
    - Mock Firestore client and ProfileClient
    - **Validates: Requirements 7.1, 7.2**

  - [x] 9.3 Write property test: Custom scenario limit enforcement (Property 8)
    - **Property 8: Custom scenario limit enforcement**
    - For any user with 20 scenarios, 21st save is rejected, count remains 20
    - **Validates: Requirements 7.5**

  - [x] 9.4 Write unit tests for CustomScenarioStore
    - Test save, list, get, delete, count with mocked Firestore and ProfileClient
    - Test limit enforcement at boundary (19, 20, 21)
    - Test document structure includes all required fields (scenario_json, created_at, updated_at — no email field)
    - Test save fails with 403 when no profile document exists
    - Test sub-collection path is `profiles/{email}/custom_scenarios/{scenario_id}`
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6_

- [x] 10. Checkpoint — Ensure all backend component tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 11. Builder Router (API endpoints)
  - [x] 11.1 Implement builder router (`backend/app/routers/builder.py`)
    - Create FastAPI router mounted at `/api/v1/builder`
    - Define request/response models: `BuilderChatRequest`, `BuilderSaveRequest`, `BuilderSaveResponse`
    - `POST /builder/chat` — validate email (401 if missing), verify profile exists via ProfileClient (403 if not), check token balance using tier-aware system from Spec 140 (429 if zero), deduct 1 token, create/get session, call `BuilderLLMAgent.stream_response`, return `StreamingResponse` with SSE events
    - `POST /builder/save` — validate email, verify profile exists, validate scenario against `ArenaScenario` (422 on failure with specific errors), perform round-trip validation via `pretty_print` + re-parse, run `HealthCheckAnalyzer.analyze` streaming SSE events, persist via `CustomScenarioStore.save` (sub-collection under profile), return `BuilderSaveResponse`
    - `GET /builder/scenarios?email=` — validate email, return `CustomScenarioStore.list_by_email`
    - `DELETE /builder/scenarios/{scenario_id}?email=` — validate email, delete via `CustomScenarioStore.delete`, 404 if not found
    - All endpoints return 401 for missing/empty email, 403 for missing profile
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 6.1, 6.2, 6.3, 6.4, 7.6, 10.1, 10.2, 14.1, 14.3, 14.4, 14.5_

  - [x] 11.2 Register builder router in FastAPI app (`backend/app/main.py`)
    - Import builder router and add `api_router.include_router(builder_router)`
    - Ensure `DELETE` is in CORS `allow_methods` list (Spec 140 will have already added `PUT` and `DELETE` — verify they are present, add if not)
    - _Requirements: 11.1_

  - [x] 11.3 Write property test: ArenaScenario validation error specificity (Property 6)
    - **Property 6: ArenaScenario validation error specificity**
    - For any invalid scenario dict, validation errors contain at least one error with specific `loc` and `msg`
    - **Validates: Requirements 6.1, 6.2**

  - [x] 11.4 Write property test: ArenaScenario pretty_print round-trip (Property 1)
    - **Property 1: ArenaScenario pretty_print round-trip**
    - For any valid ArenaScenario, `pretty_print` → JSON parse → `model_validate` produces equivalent `model_dump()`
    - Add to `backend/tests/property/test_builder_properties.py`
    - **Validates: Requirements 6.4, 13.1**

  - [x] 11.5 Write property test: ArenaScenario model_dump round-trip (Property 2)
    - **Property 2: ArenaScenario model_dump round-trip**
    - For any valid ArenaScenario, `model_dump()` → `load_scenario_from_dict()` produces equivalent `model_dump()`
    - **Validates: Requirements 13.2**

  - [x] 11.6 Write property test: Missing email returns 401 (Property 14)
    - **Property 14: Missing email returns 401**
    - For each builder endpoint, request without valid email returns HTTP 401
    - **Validates: Requirements 11.5**

  - [x] 11.7 Write property test: Token budget enforcement (Property 13)
    - **Property 13: Token budget enforcement**
    - For user with balance N>0, chat message results in balance N-1; for balance 0, returns HTTP 429
    - **Validates: Requirements 10.1, 10.2**


  - [x] 11.8 Write integration tests for builder router
    - Test `POST /builder/chat`: valid request returns SSE stream, missing email returns 401, missing profile returns 403, zero tokens returns 429
    - Test `POST /builder/save`: valid scenario saves and returns summary, invalid scenario returns 422 with errors, scenario limit returns 409, missing profile returns 403
    - Test `GET /builder/scenarios`: returns user's scenarios, empty list for new user
    - Test `DELETE /builder/scenarios/{id}`: deletes owned scenario, 404 for non-existent
    - Test round-trip: save then retrieve then `load_scenario_from_dict` then `create_initial_state`
    - Mock Firestore, Vertex AI, and ProfileClient (from Spec 140)
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 7.4, 7.6_

  - [x] 11.9 Write property test: Custom scenario usability for negotiation (Property 9)
    - **Property 9: Custom scenario usability for negotiation**
    - For any valid custom scenario, `create_initial_state(session_id, scenario_json)` produces valid NegotiationState with turn_order containing only defined agent roles
    - **Validates: Requirements 7.4**

- [x] 12. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 13. Frontend TypeScript types and API client
  - [x] 13.1 Create builder TypeScript types (`frontend/lib/builder/types.ts`)
    - Create `frontend/lib/builder/` directory
    - Define `BuilderEventType` union, `BuilderTokenEvent`, `BuilderJsonDeltaEvent`, `BuilderCompleteEvent`, `BuilderErrorEvent`
    - Define `HealthCheckFinding`, `HealthCheckFullReport` with all sub-score fields
    - Define `BuilderChatMessage` type for chat UI
    - _Requirements: 12.1, 23.1_

  - [x] 13.2 Create builder SSE client (`frontend/lib/builder/sse-client.ts`)
    - Implement `streamBuilderChat(email, sessionId, message)` using `fetch` with SSE parsing
    - Parse `data: <JSON>\n\n` events and dispatch to typed callbacks: `onToken`, `onJsonDelta`, `onComplete`, `onError`, `onHealthStart`, `onHealthFinding`, `onHealthComplete`
    - Implement reconnection with exponential backoff (max 3 retries)
    - Handle JSON parse errors gracefully (log and skip malformed events)
    - _Requirements: 3.3, 12.3, 23.4_

  - [x] 13.3 Create builder API client (`frontend/lib/builder/api.ts`)
    - Implement `saveScenario(email, scenarioJson)` — POST to `/api/v1/builder/save`
    - Implement `listCustomScenarios(email)` — GET `/api/v1/builder/scenarios?email=`
    - Implement `deleteCustomScenario(email, scenarioId)` — DELETE `/api/v1/builder/scenarios/{id}?email=`
    - _Requirements: 11.2, 11.3, 11.4_


- [x] 14. Frontend builder components
  - [x] 14.1 Implement `JsonPreview` component (`frontend/components/builder/JsonPreview.tsx`)
    - Render partial scenario JSON with 2-space indentation
    - Syntax highlighting for keys, strings, numbers, booleans using Tailwind classes
    - Display placeholder markers (`"<not yet defined>"`) for unpopulated sections
    - Section highlight animation: 2-second fade on update using CSS transition
    - Accept `scenarioJson: Partial<ArenaScenario>` and `highlightedSection: string | null` props
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 14.2 Write property test: JSON preview placeholder rendering (Property 21)
    - **Property 21: JSON preview placeholder rendering**
    - For any partial scenario, unpopulated sections show placeholders, populated sections show valid JSON
    - Implement as a Vitest test with generated partial scenario objects
    - **Validates: Requirements 4.2**

  - [x] 14.3 Write property test: JSON preview 2-space indentation (Property 22)
    - **Property 22: JSON preview 2-space indentation**
    - For any scenario JSON rendered in preview, output uses 2-space indentation
    - **Validates: Requirements 4.4**

  - [x] 14.4 Implement `ProgressIndicator` component (`frontend/components/builder/ProgressIndicator.tsx`)
    - Track 7 sections: id, name, description, agents, toggles, negotiation_params, outcome_receipt
    - Display percentage bar with current completion
    - Show "Save Scenario" button when 100% and valid
    - Update within 500ms of JSON delta event
    - Accept `scenarioJson`, `isValid`, `onSave` props
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 14.5 Implement `BuilderChat` component (`frontend/components/builder/BuilderChat.tsx`)
    - Message list with user/assistant chat bubbles (distinct styling per role)
    - Input field with Enter-to-send, disabled when waiting for response
    - Streaming token display with typewriter effect for assistant messages
    - LinkedIn URL detection visual indicator (highlight pasted LinkedIn URLs)
    - Wire to `streamBuilderChat` SSE client for sending messages
    - Dispatch `onJsonDelta` and `onHealthReport` callbacks from SSE events
    - Accept `sessionId`, `email`, `onJsonDelta`, `onHealthReport` props
    - _Requirements: 3.1, 3.3, 3.5, 3.6, 8.1_


  - [x] 14.6 Implement `HealthCheckReport` component (`frontend/components/builder/HealthCheckReport.tsx`)
    - Progressive rendering of findings as they stream in
    - Display readiness_score with tier badge ("Ready" green, "Needs Work" yellow, "Not Ready" red)
    - Per-agent prompt quality scores
    - Findings list with severity icons (critical=red, warning=yellow, info=blue)
    - Ordered recommendations list
    - Loading state while `isAnalyzing` is true
    - 60-second timeout: display "Health check timed out" with retry option
    - Accept `findings`, `report`, `isAnalyzing` props
    - _Requirements: 14.3, 14.4, 14.5, 22.2, 22.5, 23.1_

  - [x] 14.7 Implement `BuilderModal` component (`frontend/components/builder/BuilderModal.tsx`)
    - Full-screen overlay with z-index above all page content
    - Split-screen layout: BuilderChat left, JsonPreview right
    - Responsive: stack vertically below 1024px viewport width
    - ProgressIndicator at top
    - Token balance display
    - Close button with unsaved-progress confirmation dialog ("Continue Building" / "Discard & Close")
    - Generate session_id on open, clean up on close
    - Wire BuilderChat → JsonPreview updates via `onJsonDelta`
    - Wire save flow: ProgressIndicator "Save" → API save → SSE health check stream → HealthCheckReport
    - If readiness_score < 60, show report and recommend iteration; if >= 60, allow save
    - Accept `isOpen`, `onClose`, `onScenarioSaved`, `email`, `tokenBalance` props
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 10.3, 14.4, 14.5_

  - [x] 14.8 Write unit tests for frontend builder components
    - Test BuilderModal: renders split-screen, responsive stacking, close confirmation dialog
    - Test BuilderChat: message rendering, input validation, SSE event handling
    - Test JsonPreview: syntax highlighting, placeholder rendering, section highlight
    - Test ProgressIndicator: percentage calculation, save button enable/disable
    - Test HealthCheckReport: finding rendering, score display, tier badge, timeout handling
    - Use Vitest + React Testing Library
    - _Requirements: 2.1, 2.3, 2.4, 3.1, 4.1, 4.2, 5.1, 5.3, 14.3_

- [x] 15. Checkpoint — Ensure all frontend component tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 16. ScenarioSelector enhancement and integration wiring
  - [x] 16.1 Update `ScenarioSelector` component (`frontend/components/arena/ScenarioSelector.tsx`)
    - Add `customScenarios: ScenarioSummary[]` and `onBuildOwn: () => void` props to interface
    - Add "My Scenarios" `<optgroup>` between pre-built scenarios and "Build Your Own"
    - Add "Build Your Own Scenario" option at bottom, visually separated with a divider
    - "Build Your Own" selection invokes `onBuildOwn` callback instead of `onSelect`
    - Custom scenario selection invokes `onSelect` with the custom scenario ID
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 16.2 Wire ScenarioSelector and BuilderModal in Arena page (`frontend/app/(protected)/arena/page.tsx`)
    - Add state for `customScenarios`, `showBuilder`, `tokenBalance`
    - Fetch custom scenarios via `listCustomScenarios(email)` on page load
    - Pass `customScenarios` and `onBuildOwn` to ScenarioSelector
    - Render BuilderModal controlled by `showBuilder` state
    - On `onScenarioSaved`, refresh custom scenarios list and close modal
    - When custom scenario selected, fetch full scenario JSON and use for negotiation initialization
    - _Requirements: 1.1, 1.2, 1.3, 7.3, 7.4_

  - [x] 16.3 Write unit tests for updated ScenarioSelector
    - Test "My Scenarios" group renders with custom scenarios
    - Test "Build Your Own Scenario" option renders and triggers callback
    - Test custom scenario selection triggers onSelect
    - Test empty custom scenarios hides "My Scenarios" group
    - _Requirements: 1.1, 1.2, 1.3_

- [x] 17. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- **Spec 140 must be completed before starting this spec** — the profile system, tier-aware tokens, and `ProfileClient` are prerequisites
- Custom scenarios are stored at `profiles/{email}/custom_scenarios/{scenario_id}` (Firestore sub-collection), NOT in a separate top-level collection
- The `CustomScenarioStore` takes a `ProfileClient` dependency and verifies profile existence before any write operation
- The `CustomScenarioStore` obtains its Firestore `AsyncClient` via the shared `get_firestore_db()` factory from `backend/app/db/__init__.py` (introduced by Spec 140) — it does NOT create its own Firestore client
- Local mode (`RUN_MODE=local`): `SQLiteCustomScenarioStore` stores custom scenarios in the same SQLite database (`data/juntoai.db`), following the existing `SessionStore` pattern. The builder is fully functional in local mode
- Token deduction uses the tier-aware daily limit from Spec 140 (20/50/100), not a hardcoded 100
- Builder SSE events use the same `format_sse_event(event, event_id)` utility as negotiation events, including sequential event IDs for reconnection support
- CORS: Spec 140 adds `PUT` and `DELETE` to `allow_methods` before this spec runs. Task 11.2 should verify they are present rather than blindly adding
- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend uses Python (pytest + Hypothesis), frontend uses TypeScript (Vitest + React Testing Library)
- All Vertex AI and Firestore calls must be mocked in tests per testing guidelines
