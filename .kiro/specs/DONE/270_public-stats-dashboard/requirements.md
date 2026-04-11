# Requirements Document

## Introduction

Public-facing statistics dashboard for the JuntoAI A2A Protocol Sandbox. The Stats_Dashboard is a new page (following the release notes page pattern) that displays real-time platform usage metrics without requiring authentication. The page is linked from the site footer and updates live via Server-Sent Events. It gives visitors and investors an at-a-glance view of platform activity: users, simulations, token consumption, model usage, and performance.

## Glossary

- **Stats_Dashboard**: The public-facing page at `/stats` that displays aggregated platform metrics in real time
- **Stats_API**: The backend FastAPI endpoint(s) under `/api/v1/stats` that compute and serve aggregated metrics
- **Stats_SSE**: The Server-Sent Events endpoint that pushes metric updates to connected Stats_Dashboard clients
- **Time_Window**: A period used for metric aggregation — either "today" (current UTC day since midnight) or "last 7 days" (rolling 7-day window from current UTC time)
- **Session_Store**: The existing database layer (Firestore in cloud mode, SQLite in local mode) that persists negotiation sessions
- **Model_ID**: The LLM model identifier used by an agent (e.g. `gemini-2.5-flash`, `claude-sonnet-4`)
- **Simulation**: A single negotiation session from start to terminal state (Agreed, Blocked, or Failed)
- **Active_Simulation**: A negotiation session currently in "Negotiating" status
- **Footer**: The shared site-wide footer component rendered on every page
- **Custom_Scenario**: A user-created ArenaScenario stored in the Firestore sub-collection `profiles/{email}/custom_scenarios` (from Spec 130 — AI Scenario Builder)
- **Custom_Agent_Session**: A negotiation session where at least one agent role was overridden with an external endpoint URL via the BYOA flow (from Spec 230 — Bring Your Own Agent)

## Requirements

### Requirement 1: Stats Page Routing and Layout

**User Story:** As a visitor, I want to access a public stats page so that I can see platform activity without needing to log in.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL be accessible at the `/stats` URL path without authentication
2. THE Stats_Dashboard SHALL render a page title, subtitle, and a "Back to Home" link consistent with the release notes page layout
3. THE Stats_Dashboard SHALL include appropriate HTML meta tags for SEO (title, description)
4. THE Stats_Dashboard SHALL use the shared Header and Footer components from the root layout

### Requirement 2: Footer Navigation Link

**User Story:** As a visitor, I want to find the stats page from the footer so that I can discover platform metrics from any page.

#### Acceptance Criteria

1. THE Footer SHALL display a "Platform Stats" link that navigates to the `/stats` page
2. THE Footer SHALL place the "Platform Stats" link adjacent to the existing "Release Notes" link
3. THE Footer SHALL style the "Platform Stats" link consistently with the existing footer link styles

### Requirement 3: User Activity Metrics

**User Story:** As a visitor, I want to see how many users are active on the platform so that I can gauge community size and growth.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display the count of unique users who started at least one simulation today (UTC)
2. THE Stats_Dashboard SHALL display the count of unique users who started at least one simulation in the last 7 days
3. THE Stats_API SHALL compute unique user counts by counting distinct email values from negotiation sessions within each Time_Window

### Requirement 4: Simulation Metrics

**User Story:** As a visitor, I want to see simulation volume so that I can understand how actively the platform is being used.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display the total number of simulations started today (UTC)
2. THE Stats_Dashboard SHALL display the total number of simulations started in the last 7 days
3. THE Stats_Dashboard SHALL display the count of currently Active_Simulations
4. THE Stats_Dashboard SHALL display a breakdown of completed simulations by outcome (Agreed, Blocked, Failed) for today and the last 7 days
5. THE Stats_API SHALL compute simulation counts from negotiation session records within each Time_Window

### Requirement 5: Token Consumption Metrics

**User Story:** As a visitor, I want to see total token usage so that I can understand the scale of AI computation on the platform.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display the total tokens consumed across all simulations today (UTC)
2. THE Stats_Dashboard SHALL display the total tokens consumed across all simulations in the last 7 days
3. THE Stats_API SHALL compute total token counts by summing the `total_tokens_used` field from negotiation sessions within each Time_Window

### Requirement 6: Per-Model Token Breakdown

**User Story:** As a visitor, I want to see token usage broken down by AI model so that I can understand which models are most utilized.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display a table or card grid showing token consumption per Model_ID for today (UTC)
2. THE Stats_Dashboard SHALL display a table or card grid showing token consumption per Model_ID for the last 7 days
3. THE Stats_API SHALL compute per-model token counts by aggregating token usage grouped by the Model_ID assigned to each agent in completed sessions within each Time_Window

### Requirement 7: Model Performance Metrics

**User Story:** As a visitor, I want to see average thinking time per model so that I can compare model responsiveness.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display the average response time per Model_ID for simulations completed today (UTC)
2. THE Stats_Dashboard SHALL display the average response time per Model_ID for simulations completed in the last 7 days
3. THE Stats_API SHALL compute average response times from timing data recorded during agent turns, grouped by Model_ID

### Requirement 8: Scenario Popularity Metrics

**User Story:** As a visitor, I want to see which scenarios are most popular so that I can understand what types of negotiations people find interesting.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display a ranked list of scenarios by simulation count for today (UTC) and the last 7 days
2. THE Stats_Dashboard SHALL display the scenario name alongside the simulation count
3. THE Stats_API SHALL compute scenario popularity by counting sessions grouped by `scenario_id` within each Time_Window

### Requirement 9: Average Turns to Resolution

**User Story:** As a visitor, I want to see how many turns negotiations typically take so that I can understand negotiation complexity.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display the average number of turns for completed simulations today (UTC)
2. THE Stats_Dashboard SHALL display the average number of turns for completed simulations in the last 7 days
3. THE Stats_API SHALL compute average turn counts from the `turn_count` field of sessions with a terminal `deal_status` (Agreed, Blocked, or Failed) within each Time_Window

### Requirement 10: Real-Time Updates via SSE

**User Story:** As a visitor, I want the stats page to update in real time so that I can see live platform activity without refreshing.

#### Acceptance Criteria

1. WHEN the Stats_Dashboard page loads, THE Stats_Dashboard SHALL establish an SSE connection to the Stats_SSE endpoint
2. WHEN the Stats_SSE endpoint emits a `stats_update` event, THE Stats_Dashboard SHALL update all displayed metrics with the new data without a full page reload
3. THE Stats_SSE endpoint SHALL emit a `stats_update` event at a regular interval of 30 seconds
4. IF the SSE connection drops, THEN THE Stats_Dashboard SHALL attempt to reconnect with exponential backoff up to a maximum interval of 60 seconds
5. WHILE the SSE connection is disconnected, THE Stats_Dashboard SHALL display a visual indicator that data may be stale

### Requirement 11: Stats API Endpoint

**User Story:** As a developer, I want a REST endpoint for stats so that the dashboard and other consumers can fetch aggregated metrics.

#### Acceptance Criteria

1. THE Stats_API SHALL expose a GET endpoint at `/api/v1/stats` that returns all aggregated metrics as a JSON response
2. THE Stats_API SHALL return metrics for both Time_Windows (today and last 7 days) in a single response
3. THE Stats_API SHALL respond within 2 seconds under normal load
4. THE Stats_API SHALL be accessible without authentication
5. IF the Session_Store is unavailable, THEN THE Stats_API SHALL return HTTP 503 with a descriptive error message

### Requirement 12: Responsive Dashboard Layout

**User Story:** As a mobile visitor, I want the stats page to be usable on my phone so that I can check platform metrics on any device.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display metrics in a multi-column card grid on screens 1024px and wider
2. THE Stats_Dashboard SHALL stack metric cards in a single column on screens narrower than 1024px
3. THE Stats_Dashboard SHALL render all text at a minimum size that maintains a 4.5:1 contrast ratio against the background
4. THE Stats_Dashboard SHALL display numeric values with appropriate formatting (comma separators for thousands, one decimal place for averages)

### Requirement 13: Dual-Mode Compatibility

**User Story:** As a local-mode developer, I want the stats page to work with SQLite so that I can see stats in my local environment.

#### Acceptance Criteria

1. WHILE the application runs in cloud mode, THE Stats_API SHALL query Firestore for session data
2. WHILE the application runs in local mode, THE Stats_API SHALL query SQLite for session data
3. THE Stats_API SHALL use the existing Session_Store abstraction to remain database-agnostic

### Requirement 14: Stats Data Recording

**User Story:** As a platform operator, I want negotiation sessions to record the data needed for stats so that metrics can be computed accurately.

#### Acceptance Criteria

1. WHEN a negotiation session is created, THE Session_Store SHALL record a `created_at` timestamp in UTC
2. WHEN a negotiation session completes, THE Session_Store SHALL record an `updated_at` timestamp in UTC
3. THE Session_Store SHALL persist the `total_tokens_used`, `deal_status`, `scenario_id`, `turn_count`, and agent `model_id` values for each session
4. THE Stats_API SHALL derive all metrics from data already persisted in the Session_Store without requiring additional tracking tables

### Requirement 15: Custom Scenario Creation Metrics

**User Story:** As a visitor, I want to see how many custom scenarios the community has created, so that I can gauge how actively users are building their own negotiation content.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display the total number of Custom_Scenarios created across all users today (UTC)
2. THE Stats_Dashboard SHALL display the total number of Custom_Scenarios created across all users in the last 7 days
3. THE Stats_Dashboard SHALL display the cumulative total of Custom_Scenarios that exist on the platform (all time)
4. THE Stats_API SHALL compute custom scenario counts by querying the `custom_scenarios` sub-collections across all profile documents, using the `created_at` timestamp for Time_Window filtering
5. THE Stats_API SHALL include custom scenario counts in the existing `/api/v1/stats` JSON response alongside the other metrics

### Requirement 16: Custom Agent Usage Metrics

**User Story:** As a visitor, I want to see how many simulations used community-built external agents, so that I can understand how actively developers are bringing their own agents to the platform.

#### Acceptance Criteria

1. THE Stats_Dashboard SHALL display the total number of Custom_Agent_Sessions started today (UTC)
2. THE Stats_Dashboard SHALL display the total number of Custom_Agent_Sessions started in the last 7 days
3. THE Stats_Dashboard SHALL display the cumulative total of Custom_Agent_Sessions across all time
4. THE Stats_API SHALL identify Custom_Agent_Sessions by checking for the presence of `endpoint_overrides` in the session document (recorded per Spec 230, Requirement 2, Criterion 6)
5. THE Stats_API SHALL include custom agent session counts in the existing `/api/v1/stats` JSON response alongside the other metrics
