# Design Document: Test Coverage Hardening

## Overview

Close all critical test coverage gaps in the JuntoAI A2A backend and frontend. No production code changes — only new tests, fixtures, and test configuration. Target: pass 70% backend coverage gate and ensure all critical business logic paths are exercised.

### Current State (from coverage analysis)

| Module | Stmts | Current Coverage | Gap |
|--------|-------|-----------------|-----|
| `app/routers/negotiation.py` | 458 | 12% | SSE formatting, start endpoint |
| `app/orchestrator/agent_node.py` | 393 | 8% | Many paths untested despite existing tests |
| `app/routers/admin.py` | 303 | 0% | Covered by Spec 150 (in progress) |
| `app/db/profile_client.py` | 154 | 0% | No tests |
| `app/orchestrator/stall_detector.py` | 143 | 18% | Good unit tests exist, need more paths |
| `app/orchestrator/graph.py` | 119 | 18% | Covered by integration tests partially |
| `app/orchestrator/evaluator.py` | 113 | 18% | Minimal coverage |
| `app/orchestrator/milestone_generator.py` | 109 | 12% | Minimal coverage |
| `app/orchestrator/confirmation_node.py` | 104 | 17% | Minimal coverage |
| `app/routers/profile.py` | 102 | 23% | Low |
| `app/orchestrator/model_router.py` | 93 | 20% | Low |
| `app/routers/auth.py` | 88 | 28% | Low |
| `app/models/profile.py` | 69 | 64% | Moderate |
| `app/orchestrator/state.py` | 69 | 52% | Moderate |
| `app/orchestrator/evaluator_prompts.py` | 68 | 10% | Very low |
| `app/db/sqlite_client.py` | 62 | 0% | No tests |
| `app/services/email_verifier.py` | 60 | 32% | Low |
| `app/orchestrator/outputs.py` | 49 | 100% | Done |
| `app/models/events.py` | 45 | 100% | Done |
| `app/scenarios/registry.py` | 44 | 36% | Low |
| `app/middleware/event_buffer.py` | 35 | 40% | Low |
| `app/models/negotiation.py` | 33 | 100% | Done |
| `app/models/auth.py` | 33 | 82% | Moderate |
| `app/orchestrator/model_mapping.py` | 32 | 0% | No tests |
| `app/db/firestore_client.py` | 29 | 0% | No tests |
| `app/services/auth_service.py` | 24 | 42% | Low |
| `app/scenarios/loader.py` | 23 | 30% | Low |
| `app/middleware/sse_limiter.py` | 21 | 43% | Low |
| `app/scenarios/toggle_injector.py` | 17 | 24% | Low |

### Key Design Decisions

1. **No production code changes** — All changes are test files, fixtures, and test config. If a function is hard to test, we test it as-is with appropriate mocking, not refactor it.
2. **pytest markers for selective runs** — Add `unit`, `integration`, `property`, `slow` markers. CI runs all. Developers can run `pytest -m unit` for fast feedback.
3. **Shared fixtures in conftest.py** — Extend the existing `conftest.py` with reusable fixtures for mocked Firestore, mocked profile client, and scenario state builders.
4. **Frontend: mock fetch globally** — Use `vi.fn()` to mock `global.fetch` in auth and profile client tests. No MSW needed for these simple request/response tests.
5. **In-memory SQLite for DB tests** — `SQLiteSessionClient(":memory:")` for fast, isolated tests.

## Test Structure

No restructuring of the directory layout. New files are added to existing directories:

```
backend/tests/
├── unit/
│   ├── orchestrator/
│   │   ├── test_agent_node.py          (existing — extend)
│   │   ├── test_confirmation_node.py   (existing — extend)
│   │   ├── test_evaluator.py           (existing — extend)
│   │   ├── test_evaluator_prompts.py   (existing — extend)
│   │   ├── test_milestone_generator.py (existing — extend)
│   │   ├── test_model_router.py        (existing — extend)
│   │   └── test_state.py              (existing — extend)
│   ├── test_model_mapping.py           (NEW)
│   ├── test_event_buffer.py            (NEW)
│   ├── test_snapshot_to_events.py      (NEW)
│   ├── test_participant_summaries.py   (NEW)
│   ├── test_auth_service.py            (NEW)
│   ├── test_sqlite_client.py           (NEW)
│   ├── test_firestore_client.py        (NEW)
│   ├── test_profile_client.py          (NEW)
│   ├── test_toggle_injector.py         (existing — extend)
│   └── test_pretty_printer.py          (existing — extend)
├── integration/
│   ├── test_negotiation_start.py       (NEW)
│   ├── test_auth_endpoints.py          (existing — extend)
│   └── test_profile_endpoints.py       (existing — extend)
└── conftest.py                         (extend with new fixtures)

frontend/__tests__/
├── lib/
│   ├── auth.test.ts                    (NEW)
│   └── profile.test.ts                (NEW)
└── components/
    ├── WaitlistForm.test.tsx           (NEW)
    ├── TokenDisplay.test.tsx           (NEW)
    └── StartNegotiationButton.test.tsx (NEW)
```

## Component Details

### 1. pytest.ini Updates

```ini
[pytest]
asyncio_mode = auto
addopts = --cov=app --cov-fail-under=70
testpaths = tests
markers =
    unit: Unit tests (no external deps)
    integration: Integration tests (FastAPI TestClient)
    property: Property-based tests (Hypothesis)
    slow: Slow tests (>5s)
```

### 2. SSE Event Formatting Tests (`test_snapshot_to_events.py`)

Tests the `_snapshot_to_events()` function directly by importing it and passing crafted snapshot dicts. This is the most critical gap — 458 statements in `negotiation.py` at 12% coverage.

Key test cases:
- Negotiator snapshot → yields `agent_thought` event then `agent_message` event (order matters)
- Regulator snapshot with CLEAR/WARNING/BLOCKED status → correct event types
- Observer snapshot → observation event
- Dispatcher with `deal_status: "Agreed"` → `negotiation_complete` event with agreement data
- Dispatcher with `deal_status: "Failed"` → `negotiation_complete` event with failure data
- Dispatcher with `deal_status: "Blocked"` → `negotiation_complete` event with block data
- Each event validates `data: <JSON>\n\n` format
- Milestone summary events when present

### 3. Participant Summaries Tests (`test_participant_summaries.py`)

Tests `_build_participant_summaries()`, `_build_block_advice()`, `_format_outcome_value()`, `_format_price_for_summary()` from `negotiation.py`.

Key test cases:
- 2-agent scenario: buyer + seller summaries
- 4-agent scenario: negotiators + regulator + observer summaries
- Block advice with regulator warnings
- Currency vs percentage value formatting
- Edge cases: empty history, single turn

### 4. Model Mapping Tests (`test_model_mapping.py`)

Tests `resolve_model_id()` — pure function, zero external deps.

Key test cases:
- `model_override` set → returns override regardless of other params
- `model_map_json` with valid JSON → returns mapped value
- `model_map_json` with invalid JSON → falls through to defaults
- Default mapping for each provider × known model_id
- Unknown model_id → provider default with warning
- Unknown provider → returns model_id as-is
- Ollama with `ollama_model` override → dynamic mapping

### 5. Database Client Tests

**SQLiteSessionClient** (`test_sqlite_client.py`):
- Uses `SQLiteSessionClient(":memory:")` 
- `create_session` → `get_session` round-trip
- `get_session_doc` returns dict
- `update_session` modifies fields
- `get_session` for non-existent ID raises `SessionNotFoundError`

**FirestoreSessionClient** (`test_firestore_client.py`):
- Mocks `google.cloud.firestore.AsyncClient`
- `create_session` calls `set()` with correct data
- `get_session` deserializes document to `NegotiationStateModel`
- `get_session_doc` returns raw dict
- Non-existent document raises `SessionNotFoundError`

**ProfileClient** (`test_profile_client.py`):
- Mocks Firestore async client
- `get_or_create_profile` creates new profile if not exists
- `get_or_create_profile` returns existing profile if exists
- `get_profile` returns None for non-existent
- `update_profile` calls `update()` with correct fields

### 6. Middleware Tests

**SSEEventBuffer** (`test_event_buffer.py`):
- `append` returns sequential IDs (1, 2, 3...)
- `replay_after(session, 0)` returns all events
- `replay_after(session, 2)` returns only events after ID 2
- Terminal event is stored
- Different sessions are isolated
- Empty session returns empty list

**SSEConnectionTracker** — existing `test_sse_limiter.py` extended:
- `acquire` returns True when under limit
- `acquire` returns False when at limit
- `release` allows new `acquire`
- `total_active_connections` reflects state

### 7. Auth Service Tests (`test_auth_service.py`)

- `hash_password` → `verify_password` round-trip succeeds
- `verify_password` with wrong password returns False
- 72-byte truncation: passwords longer than 72 bytes hash identically to their 72-byte prefix
- `validate_google_token` with mocked `requests.get`: 200 → returns claims, non-200 → raises ValueError, missing `sub` → raises ValueError
- `check_google_oauth_id_unique`: no existing → True, same email → True, different email → False

### 8. Negotiation Start Integration Test (`test_negotiation_start.py`)

Uses the existing `test_client` fixture with mocked dependencies:
- `POST /api/v1/negotiation/start` with valid payload → 200, response contains `session_id`
- Invalid `scenario_id` → 404
- Missing required fields → 422

### 9. Frontend Auth Client Tests (`auth.test.ts`)

Mock `global.fetch` with `vi.fn()`. Test each function:
- `checkEmail`: 200 → parsed response, non-200 → throws
- `loginWithPassword`: 200 → parsed response, 401 → "Invalid password" error, other → generic error
- `loginWithGoogle`: 200 → parsed response, 404 → specific error message, other → generic error
- `setPassword`: 200 → resolves, non-200 → throws with detail
- `changePassword`: 200 → resolves, 401 → "Invalid current password", other → throws
- `linkGoogle`: 200 → parsed response, 409 → "already linked" error, other → throws
- `unlinkGoogle`: 200 → resolves, non-200 → throws

### 10. Frontend Profile Client Tests (`profile.test.ts`)

Mock `global.fetch`:
- `getProfile`: 200 → parsed ProfileResponse, non-200 → throws
- `updateProfile`: 200 → parsed ProfileResponse, non-200 → throws
- `requestEmailVerification`: 200 → resolves, non-200 → throws

### 11. Frontend Component Tests

**WaitlistForm.test.tsx**: Render form, verify input + button exist, simulate submission with valid email, simulate submission with invalid email → error shown.

**TokenDisplay.test.tsx**: Render with token count, verify display. Render with 0 tokens. Render with undefined props.

**StartNegotiationButton.test.tsx**: Render enabled state, render disabled state (no tokens), simulate click fires callback.

## Correctness Properties

### Property 1: SSE event format compliance

*For any* valid negotiation snapshot dict, every event string yielded by `_snapshot_to_events()` SHALL match the pattern `data: <valid_json>\n\n` where `<valid_json>` is parseable by `json.loads()`.

**Validates: Requirement 2.2**

### Property 2: Model mapping resolution determinism

*For any* combination of `model_id`, `provider`, `model_override`, `model_map_json`, and `ollama_model`, `resolve_model_id()` SHALL always return a non-empty string. If `model_override` is non-empty, the return value SHALL equal `model_override` regardless of other parameters.

**Validates: Requirement 4.1, 4.3**

### Property 3: SQLite session round-trip

*For any* valid `NegotiationStateModel`, creating a session via `SQLiteSessionClient.create_session()` and retrieving it via `get_session()` SHALL return a model with identical `session_id`, `scenario_id`, `turn_count`, `max_turns`, `deal_status`, and `current_offer` values.

**Validates: Requirement 5.1, 5.2**

### Property 4: Password hash round-trip

*For any* string password (1-100 chars), `verify_password(password, hash_password(password))` SHALL return True. `verify_password(different_password, hash_password(password))` SHALL return False when `different_password != password` (within bcrypt's 72-byte limit).

**Validates: Requirement 7.1**

### Property 5: Event buffer replay correctness

*For any* sequence of `append` calls to `SSEEventBuffer` for a given session, `replay_after(session, last_id)` SHALL return exactly the events appended after `last_id`, in order, with correct event IDs.

**Validates: Requirement 6.1**

## Error Handling

No production error handling changes. Test-specific error handling:
- Tests that expect exceptions use `pytest.raises()` / `with self.assertRaises()`
- Async tests use `pytest.mark.asyncio` (already configured via `asyncio_mode = auto`)
- Hypothesis tests use `@settings(max_examples=50, deadline=None)` to avoid flakiness in CI

## Testing Strategy

This IS the testing strategy. Meta-testing: run the full suite with coverage after each task group to verify coverage is increasing toward 70%.
