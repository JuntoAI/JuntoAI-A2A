# Implementation Plan: Admin Dashboard

## Overview

Cloud-only admin dashboard for JuntoAI. Backend: new FastAPI admin router with auth, rate limiting, CRUD, export endpoints. Modifications to negotiation router for session metadata and user status checks. Frontend: Next.js server-rendered admin pages with Tailwind CSS. All admin data from existing Firestore collections (`waitlist`, `profiles`, `negotiation_sessions`).

## Tasks

- [ ] 1. Backend config, models, and auth foundation
  - [ ] 1.1 Add `ADMIN_PASSWORD` to `Settings` in `backend/app/config.py`
    - Add `ADMIN_PASSWORD: str = ""` field to the `Settings` class
    - _Requirements: 1.1, 1.6_

  - [ ] 1.2 Create Pydantic models in `backend/app/models/admin.py`
    - Create `UserStatus` enum, request models (`AdminLoginRequest`, `TokenAdjustRequest`, `StatusChangeRequest`), response models (`OverviewResponse`, `UserListResponse`, `SimulationListResponse`, etc.), and query parameter models (`UserListParams`, `SimulationListParams`) as defined in the design
    - _Requirements: 9.6, 4.2, 4.5, 4.6, 5.2_

  - [ ] 1.3 Create admin router file `backend/app/routers/admin.py` with auth dependencies
    - Implement `require_cloud_mode` dependency (checks `RUN_MODE == "local"` → 503)
    - Implement `verify_admin_session` dependency using `itsdangerous.URLSafeTimedSerializer` with `max_age=28800`
    - Implement `LoginRateLimiter` class with in-memory dict, 10 attempts per IP per 5-minute window, TTL cleanup
    - Implement `compute_tier()` helper reusing Spec 140 logic (profile_completed_at → 3, email_verified → 2, else → 1)
    - _Requirements: 1.2, 1.4, 1.5, 1.8, 9.1, 9.2, 9.3, 9.4_

  - [ ] 1.4 Implement `POST /admin/login` and `POST /admin/logout` endpoints
    - Login: validate password with `hmac.compare_digest`, check rate limiter, set signed `admin_session` cookie with `HttpOnly`, `Secure` (non-dev), `SameSite=Strict`, `Path=/`, `max_age=28800`
    - Logout: clear the `admin_session` cookie, return 200
    - Log all login/logout actions at INFO level with timestamp, IP, action type
    - _Requirements: 1.3, 1.4, 1.5, 1.7, 9.3, 9.5_

  - [ ] 1.5 Register admin router conditionally in `backend/app/main.py`
    - If `settings.ADMIN_PASSWORD` is truthy, import and include admin router on `api_router`
    - If not set, log error "ADMIN_PASSWORD not set — admin routes disabled"
    - Add `PATCH` to `allow_methods` in CORS middleware
    - _Requirements: 1.6_

  - [ ]* 1.6 Write property test for rate limiter (Property 1)
    - **Property 1: Rate limiter blocks after threshold**
    - Generate random (IP, timestamp) sequences; verify `is_rate_limited` returns True after 10 attempts within 5 minutes, False otherwise; verify TTL cleanup ignores old attempts
    - File: `backend/tests/property/test_admin_properties.py`
    - **Validates: Requirements 1.5**

  - [ ]* 1.7 Write property test for tier computation (Property 4)
    - **Property 4: Tier computation correctness**
    - Generate random profile dicts (with/without `profile_completed_at`, `email_verified`); verify tier is 3, 2, or 1 per Spec 140 logic
    - File: `backend/tests/property/test_admin_properties.py`
    - **Validates: Requirements 4.2**

  - [ ]* 1.8 Write unit tests for admin auth and login
    - Test missing cookie → 401, invalid cookie → 401, expired cookie → 401, valid cookie → passes
    - Test correct password → 200 + cookie set, wrong password → 401, rate limited → 429
    - Test logout → cookie cleared + 200
    - Test `RUN_MODE=local` → 503 on all admin endpoints
    - Test `ADMIN_PASSWORD` empty → admin routes not registered (404)
    - File: `backend/tests/unit/test_admin_auth.py`
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 9.1, 9.2, 9.4_

- [ ] 2. Checkpoint — Auth foundation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Session metadata and user status in negotiation router
  - [ ] 3.1 Add `created_at` to session document in `start_negotiation()`
    - In `backend/app/routers/negotiation.py`, after building `doc_data`, set `doc_data["created_at"] = datetime.now(timezone.utc).isoformat()` (cloud mode) and equivalent for local mode state
    - _Requirements: 8.1_

  - [ ] 3.2 Add `completed_at` and `duration_seconds` in `event_stream()` finally block
    - In the finally block of `event_stream()`, after token deduction, compute `completed_at` and `duration_seconds` from `created_at`, write via `db.update_session()` (cloud mode only)
    - _Requirements: 8.2, 8.3_

  - [ ] 3.3 Add user status check in `start_negotiation()` (cloud mode)
    - Before scenario validation, read `user_status` from waitlist doc; return 403 "Account suspended" or "Account banned" if not active; treat missing `user_status` as "active"
    - _Requirements: 4.7, 4.10_

  - [ ]* 3.4 Write property test for duration computation (Property 9)
    - **Property 9: Duration computation correctness**
    - Generate random `created_at` and `completed_at` ISO 8601 timestamp pairs; verify `duration_seconds` equals integer difference in seconds
    - File: `backend/tests/property/test_admin_properties.py`
    - **Validates: Requirements 8.3**

  - [ ]* 3.5 Write unit tests for session metadata and user status
    - Test `created_at` is set on `start_negotiation()`
    - Test suspended user → 403, banned user → 403, active user → proceeds, missing `user_status` → proceeds
    - File: `backend/tests/unit/test_admin_sessions.py`
    - _Requirements: 4.7, 4.10, 8.1, 8.2, 8.3_

- [ ] 4. Checkpoint — Session metadata
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Admin overview endpoint
  - [ ] 5.1 Implement `GET /admin/overview` endpoint
    - Query `waitlist` collection for total user count
    - Query `negotiation_sessions` for today's simulations (UTC), sum `total_tokens_used` for AI tokens today
    - Read `SSEConnectionTracker.total_active_connections`
    - Compute scenario analytics: run_count and avg_tokens_used per scenario_id
    - Compute model performance from `agent_calls` arrays: avg latency, avg tokens, error count per model_id; skip sessions without `agent_calls`
    - Fetch last 50 sessions ordered by `created_at` descending for recent simulations feed
    - Return `OverviewResponse`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ]* 5.2 Write property test for scenario analytics aggregation (Property 2)
    - **Property 2: Scenario analytics aggregation correctness**
    - Generate random session lists with varying `scenario_id` and `total_tokens_used`; verify per-scenario `run_count` and `avg_tokens_used` match actual counts and arithmetic means
    - File: `backend/tests/property/test_admin_properties.py`
    - **Validates: Requirements 3.5**

  - [ ]* 5.3 Write property test for model performance aggregation (Property 3)
    - **Property 3: Model performance aggregation correctness**
    - Generate random `agent_calls` records; verify per-model averages and error counts match actual arithmetic means and counts
    - File: `backend/tests/property/test_admin_properties.py`
    - **Validates: Requirements 3.6**

  - [ ]* 5.4 Write unit/integration tests for overview endpoint
    - Mock Firestore collections, verify all metrics returned correctly
    - File: `backend/tests/integration/test_admin_overview.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

- [ ] 6. User management endpoints
  - [ ] 6.1 Implement `GET /admin/users` endpoint with pagination and filtering
    - Query `waitlist` collection with cursor-based pagination (cursor = `signed_up_at` timestamp, default page_size=50, max=200, sorted by `signed_up_at` descending)
    - Join with `profiles` collection to compute tier per user
    - Support filtering by `tier` and `status` query parameters
    - Treat missing `user_status` as "active" for backward compatibility
    - Return `UserListResponse` with `next_cursor`
    - _Requirements: 4.1, 4.2, 4.3, 4.9, 4.10_

  - [ ] 6.2 Implement `PATCH /admin/users/{email}/tokens` endpoint
    - Validate `token_balance` is non-negative integer via `TokenAdjustRequest` model
    - Update `token_balance` in waitlist document; return 404 if user not found
    - Log action at INFO level with timestamp, IP, action type, target email
    - _Requirements: 4.4, 4.5, 9.5_

  - [ ] 6.3 Implement `PATCH /admin/users/{email}/status` endpoint
    - Validate `user_status` is one of `active`, `suspended`, `banned` via `StatusChangeRequest` model
    - Update `user_status` in waitlist document; return 404 if user not found
    - Log action at INFO level with timestamp, IP, action type, target email
    - _Requirements: 4.6, 9.5_

  - [ ]* 6.4 Write property test for cursor-based pagination (Property 5)
    - **Property 5: Cursor-based pagination correctness**
    - Generate random ordered document lists, cursor values, page_size (1-200), sort direction; verify page contains at most `page_size` items, only items after cursor, correct order, and `next_cursor` equals sort field of last item
    - File: `backend/tests/property/test_admin_properties.py`
    - **Validates: Requirements 4.3, 5.3, 5.5**

  - [ ]* 6.5 Write property test for collection filtering (Property 6)
    - **Property 6: Collection filtering correctness**
    - Generate random user/simulation documents and filter criteria; verify every result matches all criteria and no matching item is excluded
    - File: `backend/tests/property/test_admin_properties.py`
    - **Validates: Requirements 4.9, 5.4**

  - [ ]* 6.6 Write unit tests for user management endpoints
    - Test valid token update, negative token rejected (422), user not found (404)
    - Test valid status change, invalid status rejected (422), user not found (404)
    - Test backward compat: missing `user_status` → "active"
    - Test pagination: cursor, page_size, ordering
    - Test filtering: by tier, by status, combined
    - File: `backend/tests/unit/test_admin_users.py`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.9, 4.10_

- [ ] 7. Checkpoint — User management
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Simulation endpoints and downloads
  - [ ] 8.1 Implement `GET /admin/simulations` endpoint with pagination and filtering
    - Query `negotiation_sessions` with cursor-based pagination (cursor = `created_at`, default page_size=50, max=200)
    - Support filtering by `scenario_id`, `deal_status`, `owner_email`
    - Support ordering by `created_at` ascending or descending (default desc)
    - Return `SimulationListResponse` with `next_cursor`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 8.2 Implement `GET /admin/simulations/{session_id}/transcript` endpoint
    - Reconstruct `Simulation_Transcript` from session `history` array using the deterministic format defined in the design (turn headers, role headers, Thought/Message/Status/Price fields)
    - Return as plain text with `Content-Disposition: attachment; filename="transcript_{session_id}.txt"`
    - Return 404 if session not found
    - _Requirements: 6.1, 6.2, 6.3, 6.6_

  - [ ] 8.3 Implement `GET /admin/simulations/{session_id}/json` endpoint
    - Return raw session document as JSON file download
    - Set `Content-Disposition: attachment; filename="session_{session_id}.json"`
    - Return 404 if session not found
    - _Requirements: 6.4, 6.5, 6.6_

  - [ ]* 8.4 Write property test for transcript round-trip (Property 7)
    - **Property 7: Transcript round-trip**
    - Generate random valid history arrays; format to transcript text then parse back; verify agent role, turn number, and public message are preserved for each entry
    - File: `backend/tests/property/test_admin_properties.py`
    - **Validates: Requirements 6.7, 6.2**

  - [ ]* 8.5 Write unit/integration tests for simulation endpoints and downloads
    - Test simulation list pagination, filtering, ordering
    - Test transcript download: Content-Disposition header, text format, 404 for missing session
    - Test JSON download: Content-Disposition header, JSON format, 404 for missing session
    - File: `backend/tests/integration/test_admin_downloads.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 9. CSV export endpoints
  - [ ] 9.1 Implement `GET /admin/export/users` endpoint
    - Export all users as CSV with columns: email, signed_up_at, token_balance, last_reset_date, tier, email_verified, display_name, status
    - Use Python `csv` module with `StringIO` for RFC 4180 compliance
    - Set `Content-Disposition: attachment; filename="users_export_{YYYY-MM-DD}.csv"`
    - Support same filter query params as `GET /admin/users`
    - _Requirements: 7.1, 7.2, 7.3, 7.7, 7.8_

  - [ ] 9.2 Implement `GET /admin/export/simulations` endpoint
    - Export all simulations as CSV with columns: session_id, scenario_id, owner_email, deal_status, turn_count, max_turns, total_tokens_used, active_toggles, model_overrides, created_at
    - Set `Content-Disposition: attachment; filename="simulations_export_{YYYY-MM-DD}.csv"`
    - Support same filter query params as `GET /admin/simulations`
    - _Requirements: 7.4, 7.5, 7.6, 7.7, 7.8_

  - [ ]* 9.3 Write property test for CSV round-trip (Property 8)
    - **Property 8: CSV serialization round-trip**
    - Generate random records with field values containing commas, double quotes, newlines, Unicode; serialize to CSV and parse back; verify field values are identical
    - File: `backend/tests/property/test_admin_properties.py`
    - **Validates: Requirements 7.9, 7.8**

  - [ ]* 9.4 Write unit tests for CSV export endpoints
    - Test CSV headers, column names, Content-Disposition header, date in filename
    - Test proper escaping of special characters
    - Test filter params applied to exports
    - File: `backend/tests/integration/test_admin_downloads.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

- [ ] 10. Checkpoint — Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Frontend admin layout and login
  - [ ] 11.1 Update Next.js middleware for `/admin/*` routes
    - Add `/admin/:path*` to the middleware matcher
    - For `/admin` routes: check `admin_session` cookie; if missing, redirect to `/admin/login`; skip redirect for `/admin/login` itself
    - Keep existing `/arena` logic unchanged
    - File: `frontend/middleware.ts`
    - _Requirements: 2.1, 2.4, 9.7_

  - [ ] 11.2 Create admin layout at `frontend/app/admin/layout.tsx`
    - Server component with sidebar navigation (Overview, Users, Simulations) and logout button
    - Reads `admin_session` cookie; if absent, render login form
    - Separate from `(protected)` route group — admin auth is cookie-based
    - _Requirements: 2.1, 2.4, 2.5, 9.7_

  - [ ] 11.3 Create admin login page at `frontend/app/admin/login/page.tsx`
    - Server-rendered password input form
    - POST to `/api/v1/admin/login`; on success redirect to `/admin`; on failure display "Invalid password"
    - _Requirements: 2.2, 2.3, 2.4_

- [ ] 12. Frontend admin pages
  - [ ] 12.1 Create admin overview page at `frontend/app/admin/page.tsx`
    - Server component calling `GET /api/v1/admin/overview` with admin cookie forwarded
    - Render stat cards (total users, simulations today, active SSE connections, AI tokens today)
    - Render scenario analytics table (runs per scenario, avg tokens)
    - Render model performance table (avg latency, avg tokens, error count per model)
    - Render recent simulations feed (last 50)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ] 12.2 Create admin users page at `frontend/app/admin/users/page.tsx`
    - Server component with client-side pagination controls
    - User table: email, tier, token balance, status, signed up date, action buttons
    - Filter controls for tier and status
    - Token adjustment and status change actions via PATCH endpoints
    - Cursor-based pagination (load more button)
    - _Requirements: 4.1, 4.2, 4.3, 4.8, 4.9_

  - [ ] 12.3 Create admin simulations page at `frontend/app/admin/simulations/page.tsx`
    - Server component with client-side pagination
    - Table: session ID (truncated 8 chars), scenario, user email, outcome, turns, AI tokens, created date
    - Click row → detail view
    - Filter controls for scenario_id, deal_status, owner_email
    - _Requirements: 5.1, 5.2, 5.6_

  - [ ] 12.4 Create simulation detail page at `frontend/app/admin/simulations/[id]/page.tsx`
    - Server component showing full session metadata and agent configuration
    - Download buttons for transcript (.txt) and raw JSON
    - _Requirements: 5.7, 6.1, 6.4_

  - [ ]* 12.5 Write frontend tests for admin pages
    - Test admin middleware redirect (no cookie → /admin/login)
    - Test login form submit → success redirect, error display
    - Test overview page renders stat cards and tables with mock data
    - Test user table columns, pagination, filter controls
    - Test simulation table columns, pagination, detail link
    - Files: `frontend/__tests__/middleware/admin-middleware.test.ts`, `frontend/__tests__/pages/admin-login.test.tsx`, `frontend/__tests__/pages/admin-overview.test.tsx`, `frontend/__tests__/pages/admin-users.test.tsx`, `frontend/__tests__/pages/admin-simulations.test.tsx`
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 4.8, 5.6_

- [ ] 13. Final checkpoint — Full integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 9 correctness properties defined in the design
- Backend tasks (1-10) should be completed before frontend tasks (11-12) since the frontend depends on the API
- `itsdangerous` must be added to `backend/requirements.txt`
