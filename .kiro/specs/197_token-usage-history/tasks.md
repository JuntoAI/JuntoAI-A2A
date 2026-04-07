# Implementation Plan: Negotiation History Panel

## Overview

Backend-first implementation: extract shared token cost utility, add Pydantic history models, extend DB clients with `list_sessions_by_owner`, wire up the history endpoint, then build the frontend panel and integrate into the arena page. The existing catch-all Next.js proxy (`/api/v1/[...path]`) already forwards GET requests to the backend, so no separate proxy route is needed.

## Tasks

- [ ] 1. Implement `compute_token_cost` utility and refactor existing usage
  - [ ] 1.1 Create `backend/app/utils/token_cost.py` with `compute_token_cost(total_tokens_used: int) -> int`
    - Pure function: `max(1, math.ceil(total_tokens_used / 1000))`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [ ] 1.2 Refactor `stream_negotiation` in `backend/app/routers/negotiation.py` to import and use `compute_token_cost` instead of inline `max(1, (ai_tokens_used + 999) // 1000)`
    - _Requirements: 3.3_
  - [ ] 1.3 Write unit tests for `compute_token_cost` in `backend/tests/unit/test_token_cost.py`
    - Test boundary values: 0, 1, 999, 1000, 1001, large values
    - Verify minimum return value is always 1
    - _Requirements: 3.1, 3.2, 3.4_
  - [ ] 1.4 Write property test for token cost formula in `backend/tests/property/test_token_cost.py`
    - **Property 5: Token cost formula correctness**
    - For any non-negative integer `total_tokens_used`, verify `compute_token_cost(total_tokens_used) == max(1, ceil(total_tokens_used / 1000))` and result >= 1
    - **Validates: Requirements 3.1, 3.4**

- [ ] 2. Implement Pydantic V2 history response models
  - [ ] 2.1 Create `backend/app/models/history.py` with `SessionHistoryItem`, `DayGroup`, and `SessionHistoryResponse` models
    - `SessionHistoryItem`: `session_id`, `scenario_id`, `scenario_name`, `deal_status`, `total_tokens_used` (ge=0), `token_cost` (ge=1), `created_at`, `completed_at` (optional)
    - `DayGroup`: `date` (YYYY-MM-DD), `total_token_cost` (ge=0), `sessions` (list)
    - `SessionHistoryResponse`: `days` (list), `total_token_cost` (ge=0), `period_days` (ge=1)
    - _Requirements: 2.1, 2.2, 2.3_
  - [ ] 2.2 Write unit tests for history models in `backend/tests/unit/test_history_models.py`
    - Test required fields, optional `completed_at`, field constraints (ge=0, ge=1), validation errors
    - _Requirements: 2.1, 2.2, 2.3_
  - [ ] 2.3 Write property test for round-trip serialization in `backend/tests/property/test_history_models.py`
    - **Property 4: SessionHistoryResponse round-trip serialization**
    - For any valid `SessionHistoryResponse` instance, `.model_dump_json()` → `SessionHistoryResponse.model_validate_json()` produces an equal object
    - Use Hypothesis `builds()` strategy for all three models
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [ ] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Extend DB clients with `list_sessions_by_owner`
  - [ ] 4.1 Add `list_sessions_by_owner(owner_email: str, since: str) -> list[dict]` to the `SessionStore` protocol in `backend/app/db/base.py`
    - _Requirements: 1.1, 1.9, 1.10_
  - [ ] 4.2 Implement `list_sessions_by_owner` on `FirestoreSessionClient` in `backend/app/db/firestore_client.py`
    - Query `negotiation_sessions` collection with `.where("owner_email", "==", owner_email).where("created_at", ">=", since).order_by("created_at", direction="DESCENDING")`
    - _Requirements: 1.10_
  - [ ] 4.3 Implement `list_sessions_by_owner` on `SQLiteSessionClient` in `backend/app/db/sqlite_client.py`
    - SQL filter on `created_at >= ?` column, then Python filter on `owner_email` from JSON `data` column
    - _Requirements: 1.9, 8.1, 8.3_
  - [ ] 4.4 Write unit tests for `SQLiteSessionClient.list_sessions_by_owner` in `backend/tests/unit/test_sqlite_client.py`
    - Test date filtering, owner filtering, empty results, ordering
    - _Requirements: 1.9, 8.1, 8.3_

- [ ] 5. Implement history grouping logic and `GET /api/v1/negotiation/history` endpoint
  - [ ] 5.1 Add the history endpoint to `backend/app/routers/negotiation.py`
    - Accept `email` (required str) and `days` (optional int, Query(ge=1, le=90, default=7))
    - Validate email presence (422 if missing/empty)
    - Compute cutoff = `now_utc - timedelta(days=days)`
    - Call `db.list_sessions_by_owner(email, cutoff_iso)`
    - Filter to terminal sessions (`deal_status` in `{Agreed, Blocked, Failed}`)
    - Resolve `scenario_name` from `ScenarioRegistry` (fallback to `scenario_id`)
    - Compute `token_cost` via `compute_token_cost`
    - Group by UTC date, sort groups descending, sessions within each group descending by `created_at`
    - Return `SessionHistoryResponse`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_
  - [ ] 5.2 Write property test for grouping and sorting correctness in `backend/tests/property/test_history_grouping.py`
    - **Property 1: Grouping and sorting correctness**
    - For any set of sessions, verify: each session's UTC date matches its group's `date`, sessions within groups sorted descending by `created_at`, groups sorted descending by `date`
    - **Validates: Requirements 1.2, 1.3**
  - [ ] 5.3 Write property test for date range filtering in `backend/tests/property/test_history_grouping.py`
    - **Property 2: Date range filtering**
    - For any sessions spanning arbitrary dates and any `days` value 1–90, only sessions within the window appear
    - **Validates: Requirements 1.4**
  - [ ] 5.4 Write property test for DayGroup token cost sum invariant in `backend/tests/property/test_history_grouping.py`
    - **Property 3: DayGroup token cost sum invariant**
    - For any DayGroup, `total_token_cost == sum(session.token_cost for session in sessions)` and `SessionHistoryResponse.total_token_cost == sum(group.total_token_cost for group in days)`
    - **Validates: Requirements 1.6**
  - [ ] 5.5 Write integration tests for the history endpoint in `backend/tests/integration/test_history_endpoint.py`
    - Test happy path with in-memory SQLite, 422 on missing email, empty history response, date filtering
    - _Requirements: 1.1, 1.7, 1.8_

- [ ] 6. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement frontend API client and `NegotiationHistory` panel
  - [ ] 7.1 Create `frontend/lib/history.ts` with `fetchNegotiationHistory` API client
    - Define `SessionHistoryItem`, `DayGroup`, `SessionHistoryResponse` TypeScript interfaces
    - `fetchNegotiationHistory(email: string, days?: number): Promise<SessionHistoryResponse>` — calls `/api/v1/negotiation/history`
    - _Requirements: 1.1, 4.1_
  - [ ] 7.2 Create `frontend/components/arena/NegotiationHistory.tsx` panel component
    - Accept `email` and `dailyLimit` props
    - Fetch history on mount via `fetchNegotiationHistory`
    - Render loading skeleton while fetching (`data-testid="negotiation-history"`)
    - Render error state with "Retry" button on failure
    - Render empty state: "No negotiations yet. Start one above."
    - Render day groups as collapsible sections: date header (Today/Yesterday/formatted date), daily token cost as fraction of `dailyLimit` (e.g. "12 / 100 tokens used"), "∞" for local mode unlimited
    - Today group expanded by default, others collapsed
    - Session rows: scenario name, colored status badge (green=Agreed, red=Failed, yellow=Blocked), token cost, "View" link to `/arena/session/{session_id}`
    - Responsive: single-column below 1024px, `max-w-4xl` container at 1024px+
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 5.1, 5.2, 5.3, 5.4, 7.1, 7.2, 7.3, 8.2_
  - [ ] 7.3 Write component tests for `NegotiationHistory` in `frontend/__tests__/components/arena/NegotiationHistory.test.tsx`
    - Test loading, error with retry, empty state, populated state with day groups
    - Test today expanded / others collapsed, status badge colors, "∞" for local mode
    - _Requirements: 4.1, 4.3, 4.6, 4.7, 4.8, 5.4, 8.2_

- [ ] 8. Integrate NegotiationHistory into the arena page
  - [ ] 8.1 Import and render `<NegotiationHistory>` in `frontend/app/(protected)/arena/page.tsx` below `<InitializeButton>`
    - Pass `email` and `dailyLimit` from `SessionContext`
    - _Requirements: 4.1_
  - [ ] 8.2 Verify session replay works for completed sessions navigated from history
    - The existing GlassBox page SSE hook already handles terminal sessions — confirm `useSSE` detects terminal state from the first snapshot replay and renders read-only (stop button hidden, outcome receipt shown)
    - If adjustments are needed, update `frontend/app/(protected)/arena/session/[sessionId]/page.tsx`
    - _Requirements: 6.1, 6.2, 6.3_

- [ ] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The existing catch-all proxy at `frontend/app/api/v1/[...path]/route.ts` already forwards GET requests to the backend — no separate proxy route needed
- Property tests use Hypothesis (already in the project) with minimum 100 iterations
- The `stream_negotiation` refactor (task 1.2) replaces inline `max(1, (ai_tokens_used + 999) // 1000)` with the shared `compute_token_cost` import
- SQLite `list_sessions_by_owner` filters `created_at` at SQL level but checks `owner_email` in Python (JSON column)
