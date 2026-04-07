# Requirements Document

## Introduction

Negotiation History panel for the JuntoAI A2A arena page. Users currently have no way to review past negotiations — what scenarios they ran, how deals landed, or what reasoning the agents used. This spec adds a "Negotiation History" panel below the "Start Negotiation" button on the `/arena` page, showing past sessions grouped by day. Token costs appear as secondary metadata per session and as daily totals, giving users budget awareness without making it the focal point.

Since the daily token limit (100 tokens/day for Tier 3) resets at midnight UTC, the history is naturally grouped by UTC day. Each session entry leads with the scenario name and deal outcome, with token cost shown as a supporting detail.

The feature requires a new backend endpoint to query completed sessions for a given user, aggregated by day, and a new frontend component on the arena page to render the grouped history with navigation to replay past negotiations.

## Glossary

- **Negotiation_History_Panel**: A UI section rendered below the InitializeButton on the `/arena` page that displays the user's past negotiation sessions grouped by UTC day, with token costs shown as secondary metadata.
- **Day_Group**: A collection of completed negotiation sessions belonging to the same UTC calendar day (based on `created_at` timestamp). Each group shows the date, a list of individual sessions, and the total tokens spent that day.
- **Session_Summary**: A compact representation of a single completed negotiation session within a Day_Group, showing scenario name, deal outcome, and token cost as a secondary detail, with a link to replay the session.
- **Token_Cost**: The number of user tokens deducted for a negotiation, computed as `max(1, ceil(total_tokens_used / 1000))` — 1 user token per 1,000 AI tokens, rounded up, minimum 1.
- **Arena_Page**: The `/arena` route (Screen 2) where users select scenarios, configure agents, and start negotiations.
- **Session_Document**: The Firestore (cloud) or SQLite (local) document storing the full negotiation state, including `owner_email`, `created_at`, `completed_at`, `scenario_id`, `deal_status`, `total_tokens_used`, and `session_id`.

## Requirements

### Requirement 1: Negotiation History API Endpoint

**User Story:** As a user, I want an API endpoint that returns my past negotiation sessions grouped by day, so that the frontend can render my negotiation history with token context.

#### Acceptance Criteria

1. THE Backend SHALL expose a `GET /api/v1/negotiation/history` endpoint that accepts an `email` query parameter and returns the authenticated user's completed negotiation sessions.
2. THE endpoint SHALL return sessions sorted by `created_at` in descending order (most recent first).
3. THE endpoint SHALL group sessions by UTC calendar day derived from the `created_at` timestamp.
4. WHEN a `days` query parameter is provided (integer, 1–90), THE endpoint SHALL return only sessions from the last N UTC days. WHEN `days` is omitted, THE endpoint SHALL default to 7 days.
5. THE endpoint SHALL return for each session: `session_id`, `scenario_id`, `scenario_name` (resolved from the scenario registry), `deal_status`, `total_tokens_used` (AI tokens), `token_cost` (user tokens deducted), `created_at`, and `completed_at`.
6. THE endpoint SHALL return for each Day_Group: `date` (UTC date string in YYYY-MM-DD format), `total_token_cost` (sum of token_cost for all sessions in the group), and `sessions` (list of Session_Summary objects).
7. WHEN the user has no completed sessions in the requested range, THE endpoint SHALL return an empty `days` list with `total_token_cost` of zero.
8. IF the `email` parameter is missing or empty, THEN THE endpoint SHALL return HTTP 422 with a descriptive error.
9. WHEN `RUN_MODE` is `local`, THE endpoint SHALL query the SQLite `negotiation_sessions` table filtering by `owner_email` in the session data JSON.
10. WHEN `RUN_MODE` is `cloud`, THE endpoint SHALL query the Firestore `negotiation_sessions` collection filtering by `owner_email`.

### Requirement 2: Session History Response Schema

**User Story:** As a developer, I want a well-defined Pydantic schema for the history response, so that the data contract between backend and frontend is explicit and validated.

#### Acceptance Criteria

1. THE system SHALL define a `SessionHistoryItem` Pydantic V2 model with fields: `session_id` (str), `scenario_id` (str), `scenario_name` (str), `deal_status` (str), `total_tokens_used` (int, ge=0), `token_cost` (int, ge=1), `created_at` (str), and `completed_at` (str, optional).
2. THE system SHALL define a `DayGroup` Pydantic V2 model with fields: `date` (str, YYYY-MM-DD format), `total_token_cost` (int, ge=0), and `sessions` (list of SessionHistoryItem).
3. THE system SHALL define a `SessionHistoryResponse` Pydantic V2 model with fields: `days` (list of DayGroup), `total_token_cost` (int, ge=0), and `period_days` (int, ge=1).
4. FOR ALL valid SessionHistoryResponse instances, serializing to JSON via `.model_dump_json()` and deserializing back via `SessionHistoryResponse.model_validate_json()` SHALL produce an equivalent object (round-trip property).

### Requirement 3: Token Cost Calculation

**User Story:** As a user, I want to see how many of my daily tokens each negotiation consumed, so that I understand my spending alongside my negotiation history.

#### Acceptance Criteria

1. THE Token_Cost for a session SHALL be computed as `max(1, ceil(total_tokens_used / 1000))`, matching the deduction logic in the `stream_negotiation` function.
2. WHEN `total_tokens_used` is zero (session created but negotiation did not produce AI calls), THE Token_Cost SHALL be 1 (minimum cost).
3. THE Token_Cost calculation SHALL be a pure function in a shared utility module so both the history endpoint and the deduction logic reference the same formula.
4. FOR ALL non-negative integer values of `total_tokens_used`, THE Token_Cost SHALL be a positive integer greater than or equal to 1.

### Requirement 4: Negotiation History Frontend Panel

**User Story:** As a user, I want to see my past negotiations below the "Start Negotiation" button on the arena page, so that I can review what I've run and how deals landed.

#### Acceptance Criteria

1. WHEN the user is authenticated and on the Arena_Page, THE Negotiation_History_Panel SHALL render below the InitializeButton component with `data-testid="negotiation-history"`.
2. THE Negotiation_History_Panel SHALL display Day_Groups in reverse chronological order (today first).
3. THE Negotiation_History_Panel SHALL display each Day_Group as a collapsible section showing the UTC date (formatted as a human-readable string, e.g. "Mon, Jun 23") and the total tokens spent that day (e.g. "5 tokens used").
4. WHEN a Day_Group is expanded, THE Negotiation_History_Panel SHALL list each Session_Summary showing: scenario name as the primary label, deal outcome (with a colored status badge — green for Agreed, red for Failed, yellow for Blocked), token cost as secondary metadata, and a "View" link.
5. WHEN the user clicks the "View" link on a Session_Summary, THE Arena_Page SHALL navigate to `/arena/session/{session_id}` to replay the past negotiation.
6. WHEN the history API returns an empty `days` list, THE Negotiation_History_Panel SHALL display a message: "No negotiations yet. Start one above."
7. THE Negotiation_History_Panel SHALL show a loading skeleton while the history API request is in flight.
8. IF the history API request fails, THEN THE Negotiation_History_Panel SHALL display an inline error message and a "Retry" button.

### Requirement 5: Day Group Presentation

**User Story:** As a user, I want the history grouped by day with clear daily totals, so that I can see my negotiation activity and token budget at a glance.

#### Acceptance Criteria

1. THE Day_Group header SHALL display the daily token cost as a fraction of the user's daily limit (e.g. "12 / 100 tokens used") using the `dailyLimit` value from SessionContext.
2. WHEN the Day_Group date matches the current UTC date, THE header SHALL display "Today" instead of the date string.
3. WHEN the Day_Group date matches yesterday's UTC date, THE header SHALL display "Yesterday" instead of the date string.
4. THE today Day_Group SHALL be expanded by default. All other Day_Groups SHALL be collapsed by default.

### Requirement 6: Session Replay Navigation

**User Story:** As a user, I want to view old negotiations from the history panel, so that I can review past outcomes and agent reasoning.

#### Acceptance Criteria

1. WHEN the user navigates to `/arena/session/{session_id}` for a completed session, THE Glass_Box UI SHALL load the session's stored history and render it as a read-only replay (no SSE streaming).
2. WHEN a session is in a terminal state (Agreed, Blocked, or Failed) and the user navigates to it, THE system SHALL load the session data from the database instead of opening an SSE stream.
3. IF the session_id does not exist or does not belong to the authenticated user, THEN THE system SHALL display a "Session not found" error and provide a link back to the arena.

### Requirement 7: Responsive Layout

**User Story:** As a user, I want the negotiation history to work on both mobile and desktop, so that I can review past sessions from any device.

#### Acceptance Criteria

1. THE Negotiation_History_Panel SHALL render correctly on viewports from 320px to 1920px wide.
2. WHILE the viewport width is below 1024px, THE Negotiation_History_Panel SHALL use a single-column stacked layout for Day_Groups and Session_Summaries.
3. WHILE the viewport width is 1024px or above, THE Negotiation_History_Panel SHALL use the same max-width container as the rest of the Arena_Page (`max-w-4xl`).

### Requirement 8: Local Mode Compatibility

**User Story:** As a developer running locally, I want the negotiation history to work with SQLite, so that the feature is testable without GCP.

#### Acceptance Criteria

1. WHEN `RUN_MODE` is `local`, THE history endpoint SHALL query the SQLite `negotiation_sessions` table and extract `owner_email` from the JSON `data` column.
2. WHEN `RUN_MODE` is `local`, THE Negotiation_History_Panel SHALL still render but the token cost display SHALL show "∞" for the daily limit since local mode has unlimited tokens.
3. THE SQLite query SHALL use the `created_at` column for date filtering and sorting, avoiding full-table JSON parsing where possible.
