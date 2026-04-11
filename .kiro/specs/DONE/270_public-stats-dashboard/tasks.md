# Implementation Plan: Public Stats Dashboard

## Overview

Implement a public-facing stats dashboard at `/stats` with a FastAPI backend aggregating session metrics and a Next.js frontend rendering live-updating metric cards via SSE. Backend uses Python (FastAPI/Pydantic V2/Hypothesis), frontend uses TypeScript (Next.js 14/Tailwind/Vitest/fast-check).

## Tasks

- [x] 1. Create Stats Pydantic models and aggregator service
  - [x] 1.1 Create `backend/app/models/stats.py` with all response models
    - Define `OutcomeBreakdown`, `ModelTokenBreakdown`, `ModelPerformance`, `ScenarioPopularity`, and `StatsResponse` Pydantic V2 models
    - All fields must match the design data model exactly
    - _Requirements: 11.1, 11.2_

  - [x] 1.2 Extend `SessionStore` protocol with `list_sessions` method
    - Add `list_sessions(self, since: datetime | None = None) -> list[dict]` to `backend/app/db/base.py`
    - Implement in `FirestoreSessionClient` using Firestore collection query with `created_at` filter
    - Implement in `SQLiteSessionClient` using `SELECT` with `WHERE created_at >= ?`
    - _Requirements: 13.1, 13.2, 13.3, 14.4_

  - [x] 1.3 Create `backend/app/services/stats_aggregator.py`
    - Implement `StatsAggregator` class that takes a `SessionStore`-compatible client
    - Implement `compute_stats()` method that queries sessions via `list_sessions` and computes all metrics: unique users, simulation counts, outcome breakdown, token sums, per-model tokens, per-model avg response time, scenario popularity (sorted descending), avg turns, custom scenario counts, custom agent session counts
    - Use `.get()` with defaults for missing fields; log warnings for malformed data
    - For custom scenarios in cloud mode, query Firestore `profiles/{email}/custom_scenarios` sub-collections; return 0 in local mode
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 8.1, 8.3, 9.1, 9.2, 9.3, 15.1, 15.2, 15.3, 15.4, 16.1, 16.2, 16.3, 16.4_

  - [x]* 1.4 Write property test: unique user count (Property 1)
    - **Property 1: Unique user count equals distinct emails in time window**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [x]* 1.5 Write property test: simulation counts and outcome breakdown (Property 2)
    - **Property 2: Simulation counts and outcome breakdown match manual computation**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

  - [x]* 1.6 Write property test: total token sum (Property 3)
    - **Property 3: Total token sum equals aggregate of session tokens in time window**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [x]* 1.7 Write property test: per-model token breakdown (Property 4)
    - **Property 4: Per-model token breakdown matches grouped aggregation**
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [x]* 1.8 Write property test: per-model average response time (Property 5)
    - **Property 5: Per-model average response time matches manual mean computation**
    - **Validates: Requirements 7.1, 7.2, 7.3**

  - [x]* 1.9 Write property test: scenario popularity ranking (Property 6)
    - **Property 6: Scenario popularity is ranked descending by simulation count**
    - **Validates: Requirements 8.1, 8.3**

  - [x]* 1.10 Write property test: average turns (Property 7)
    - **Property 7: Average turns equals mean of turn_count for terminal sessions**
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [x]* 1.11 Write property test: custom agent session classification (Property 11)
    - **Property 11: Custom agent session classification matches endpoint_overrides presence**
    - **Validates: Requirements 16.1, 16.2, 16.3, 16.4**

- [x] 2. Checkpoint — Ensure all backend service tests pass
  - All 9 backend property tests pass (8 aggregator + 1 round-trip)

- [x] 3. Create Stats Router and wire into FastAPI app (adapted: added to existing admin router instead of separate public router)
  - [x] 3.1 Added `GET /api/v1/admin/stats` endpoint to `backend/app/routers/admin.py`
    - Auth-protected via `verify_admin_session` (admin-only for now, will go public later)
    - Returns `StatsResponse` JSON
    - Catches exceptions and returns HTTP 503 with descriptive message
    - Enriches custom scenario counts via Firestore collection group query in cloud mode
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 3.2 No separate registration needed — endpoint added to existing admin router
    - _Requirements: 11.1_

  - [x]* 3.3 Write integration tests for stats endpoints
    - Test stats aggregation returns 200 with valid StatsResponse shape
    - Test empty sessions returns zeros
    - Test outcomes breakdown correct
    - Test model tokens and performance
    - Test scenario popularity sorted descending
    - Test custom agent session detection
    - Test avg turns only terminal sessions
    - Test router registration
    - _Requirements: 11.1, 11.4, 11.5_

  - [x]* 3.4 Write property test: session data round-trip (Property 10)
    - **Property 10: Session data round-trip preserves stats-relevant fields**
    - **Validates: Requirements 14.3**

- [x] 4. Checkpoint — Ensure all backend tests pass
  - All 17 backend tests pass (8 property + 1 round-trip + 8 integration)

- [x] 5. Build frontend Stats page and components (adapted: admin-only page instead of public)
  - [x] 5.1–5.3 Created `frontend/app/admin/stats/page.tsx` as admin server component
    - Follows existing admin page pattern (cookie auth, backendFetch, StatCard inline components)
    - Displays all metrics: unique users, simulations, tokens, outcomes, avg turns, scenario popularity, per-model tokens, per-model response times, custom scenarios, custom agent sessions
    - Number formatting with comma separators and 1 decimal for averages
    - Responsive grid layout matching existing admin pages
    - _Requirements: 3.1, 3.2, 4.1–4.4, 5.1, 5.2, 6.1, 6.2, 7.1, 7.2, 8.1, 8.2, 9.1, 9.2, 12.1–12.4, 15.1–15.3, 16.1–16.3_

  - [x] 5.4 Updated `frontend/app/admin/layout.tsx` — added "Platform Stats" to sidebar NAV_ITEMS
    - _Requirements: 2.1, 2.2, 2.3 (adapted to admin sidebar instead of footer)_

  - [ ] 5.4b (DEFERRED) Update `frontend/components/Footer.tsx` with public link — will add when making stats public
    - _Requirements: 2.1, 2.2, 2.3_

  - [x]* 5.5 Write property test: SSE reconnect backoff (Property 8)
    - **Property 8: SSE reconnect backoff is exponential and capped at 60 seconds**
    - **Validates: Requirements 10.4**

  - [x]* 5.6 Write property test: number formatting (Property 9)
    - **Property 9: Number formatting applies comma separators and decimal rules**
    - **Validates: Requirements 12.4**

  - [x]* 5.7 Write unit tests for frontend stats components
    - Test StatCard renders values correctly
    - Test admin stats page renders all metric sections
    - Test admin layout sidebar contains "Platform Stats" link adjacent to Broadcast
    - Test error/auth states
    - _Requirements: 1.2, 2.1, 10.5, 12.4_

- [x] 6. Final checkpoint — Ensure all tests pass
  - Backend: 9 property tests + 8 integration tests = 17 passing
  - Frontend: 4 property tests + 8 formatting tests + 11 unit tests = 23 passing
  - Total: 40 tests all green

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend: Python 3.11+, FastAPI, Pydantic V2, pytest + Hypothesis
- Frontend: Next.js 14+ App Router, Tailwind CSS, Vitest + fast-check
- Property tests validate correctness properties from the design document
- Each task references specific requirement clauses for traceability
