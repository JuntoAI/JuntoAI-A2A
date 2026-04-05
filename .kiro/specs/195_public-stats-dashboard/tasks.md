# Implementation Plan: Public Stats Dashboard

## Overview

Implement a public-facing stats dashboard at `/stats` with a FastAPI backend aggregating session metrics and a Next.js frontend rendering live-updating metric cards via SSE. Backend uses Python (FastAPI/Pydantic V2/Hypothesis), frontend uses TypeScript (Next.js 14/Tailwind/Vitest/fast-check).

## Tasks

- [ ] 1. Create Stats Pydantic models and aggregator service
  - [ ] 1.1 Create `backend/app/models/stats.py` with all response models
    - Define `OutcomeBreakdown`, `ModelTokenBreakdown`, `ModelPerformance`, `ScenarioPopularity`, and `StatsResponse` Pydantic V2 models
    - All fields must match the design data model exactly
    - _Requirements: 11.1, 11.2_

  - [ ] 1.2 Extend `SessionStore` protocol with `list_sessions` method
    - Add `list_sessions(self, since: datetime | None = None) -> list[dict]` to `backend/app/db/base.py`
    - Implement in `FirestoreSessionClient` using Firestore collection query with `created_at` filter
    - Implement in `SQLiteSessionClient` using `SELECT` with `WHERE created_at >= ?`
    - _Requirements: 13.1, 13.2, 13.3, 14.4_

  - [ ] 1.3 Create `backend/app/services/stats_aggregator.py`
    - Implement `StatsAggregator` class that takes a `SessionStore`-compatible client
    - Implement `compute_stats()` method that queries sessions via `list_sessions` and computes all metrics: unique users, simulation counts, outcome breakdown, token sums, per-model tokens, per-model avg response time, scenario popularity (sorted descending), avg turns, custom scenario counts, custom agent session counts
    - Use `.get()` with defaults for missing fields; log warnings for malformed data
    - For custom scenarios in cloud mode, query Firestore `profiles/{email}/custom_scenarios` sub-collections; return 0 in local mode
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 8.1, 8.3, 9.1, 9.2, 9.3, 15.1, 15.2, 15.3, 15.4, 16.1, 16.2, 16.3, 16.4_

  - [ ]* 1.4 Write property test: unique user count (Property 1)
    - **Property 1: Unique user count equals distinct emails in time window**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 1.5 Write property test: simulation counts and outcome breakdown (Property 2)
    - **Property 2: Simulation counts and outcome breakdown match manual computation**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

  - [ ]* 1.6 Write property test: total token sum (Property 3)
    - **Property 3: Total token sum equals aggregate of session tokens in time window**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ]* 1.7 Write property test: per-model token breakdown (Property 4)
    - **Property 4: Per-model token breakdown matches grouped aggregation**
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [ ]* 1.8 Write property test: per-model average response time (Property 5)
    - **Property 5: Per-model average response time matches manual mean computation**
    - **Validates: Requirements 7.1, 7.2, 7.3**

  - [ ]* 1.9 Write property test: scenario popularity ranking (Property 6)
    - **Property 6: Scenario popularity is ranked descending by simulation count**
    - **Validates: Requirements 8.1, 8.3**

  - [ ]* 1.10 Write property test: average turns (Property 7)
    - **Property 7: Average turns equals mean of turn_count for terminal sessions**
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [ ]* 1.11 Write property test: custom agent session classification (Property 11)
    - **Property 11: Custom agent session classification matches endpoint_overrides presence**
    - **Validates: Requirements 16.1, 16.2, 16.3, 16.4**

- [ ] 2. Checkpoint — Ensure all backend service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Create Stats Router and wire into FastAPI app
  - [ ] 3.1 Create `backend/app/routers/stats.py`
    - Implement `GET /api/v1/stats` endpoint returning `StatsResponse` JSON (no auth)
    - Implement `GET /api/v1/stats/stream` SSE endpoint emitting `stats_update` events every 30 seconds via `StreamingResponse`
    - Catch `DatabaseConnectionError` and return HTTP 503 with descriptive message
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 10.3_

  - [ ] 3.2 Register stats router in `backend/app/main.py`
    - Import and include `stats_router` in the `api_router` with the existing pattern
    - _Requirements: 11.1_

  - [ ]* 3.3 Write integration tests for stats endpoints
    - Test `GET /api/v1/stats` returns 200 with valid `StatsResponse` shape
    - Test `GET /api/v1/stats` returns 503 when session store is unavailable
    - Test `GET /api/v1/stats/stream` returns SSE-formatted `text/event-stream` response
    - _Requirements: 11.1, 11.4, 11.5, 10.3_

  - [ ]* 3.4 Write property test: session data round-trip (Property 10)
    - **Property 10: Session data round-trip preserves stats-relevant fields**
    - **Validates: Requirements 14.3**

- [ ] 4. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Build frontend Stats page and components
  - [ ] 5.1 Create `frontend/components/stats/StatCard.tsx`
    - Reusable card component displaying label, today value, 7-day value, and optional breakdown
    - Format numbers with comma separators for thousands, one decimal place for averages
    - Responsive: multi-column grid on ≥1024px, single column below
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [ ] 5.2 Create `frontend/components/stats/StatsDashboard.tsx` client component
    - Fetch initial data from `GET /api/v1/stats` on mount
    - Establish SSE connection to `/api/v1/stats/stream` using `EventSource`
    - Update all metric cards on `stats_update` events without page reload
    - Show stale-data visual indicator when SSE is disconnected
    - Reconnect with exponential backoff: `min(baseDelay * 2^n, 60000)` ms
    - Render StatCard components for all metric categories: users, simulations, tokens, per-model tokens, per-model performance, scenario popularity, avg turns, custom scenarios, custom agent sessions
    - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 6.1, 6.2, 7.1, 7.2, 8.1, 8.2, 9.1, 9.2, 10.1, 10.2, 10.3, 10.4, 10.5, 12.1, 12.2, 15.1, 15.2, 15.3, 16.1, 16.2, 16.3_

  - [ ] 5.3 Create `frontend/app/stats/page.tsx` server component
    - Follow release notes page pattern: title, subtitle, "Back to Home" link
    - Include SEO meta tags (title, description) via Next.js metadata export
    - Render `StatsDashboard` client component
    - No authentication required
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 5.4 Update `frontend/components/Footer.tsx`
    - Add "Platform Stats" link navigating to `/stats`
    - Place adjacent to existing "Release Notes" link with same styling
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 5.5 Write property test: SSE reconnect backoff (Property 8)
    - **Property 8: SSE reconnect backoff is exponential and capped at 60 seconds**
    - **Validates: Requirements 10.4**

  - [ ]* 5.6 Write property test: number formatting (Property 9)
    - **Property 9: Number formatting applies comma separators and decimal rules**
    - **Validates: Requirements 12.4**

  - [ ]* 5.7 Write unit tests for frontend stats components
    - Test StatCard renders values correctly
    - Test StatsDashboard displays stale indicator on disconnect
    - Test Footer contains "Platform Stats" link
    - Test stats page metadata
    - _Requirements: 1.2, 2.1, 10.5, 12.4_

- [ ] 6. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend: Python 3.11+, FastAPI, Pydantic V2, pytest + Hypothesis
- Frontend: Next.js 14+ App Router, Tailwind CSS, Vitest + fast-check
- Property tests validate correctness properties from the design document
- Each task references specific requirement clauses for traceability
