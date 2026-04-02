# Requirements Document

## Introduction

An internal admin dashboard for the JuntoAI A2A negotiation platform, accessible at `/admin` in the Next.js frontend with backend API endpoints at `/api/v1/admin/*`. The dashboard provides user management, simulation oversight, system health monitoring, and data export capabilities. Authentication uses a single shared password stored in an environment variable (`ADMIN_PASSWORD`) — no user accounts, no OAuth. This is an internal operations tool, not a customer-facing product. The frontend admin pages are server-side rendered to avoid exposing admin data in client JavaScript bundles.

## Glossary

- **Admin_Dashboard**: The Next.js page group at `/admin` providing user management, simulation oversight, system health, and data export views.
- **Admin_API**: The set of FastAPI endpoints under `/api/v1/admin/*` that serve admin data and accept admin mutations.
- **Admin_Auth_Middleware**: A FastAPI dependency that validates the admin password on every Admin_API request using constant-time string comparison.
- **Admin_Password**: A shared secret stored in the `ADMIN_PASSWORD` environment variable, used to authenticate all Admin_API requests.
- **Admin_Session_Cookie**: An HTTP-only cookie set on the frontend after successful password verification, used to maintain the admin login state across page navigations.
- **Waitlist_Collection**: The Firestore `waitlist` collection containing user documents keyed by email, with fields `email`, `signed_up_at`, `token_balance`, and `last_reset_date`.
- **Profiles_Collection**: The Firestore `profiles` collection containing user profile documents keyed by email, with fields `display_name`, `email_verified`, `github_url`, `linkedin_url`, `profile_completed_at`, and `created_at`.
- **Sessions_Collection**: The Firestore `negotiation_sessions` collection containing negotiation session documents keyed by session_id, with fields including `session_id`, `scenario_id`, `deal_status`, `history`, `turn_count`, `max_turns`, `total_tokens_used`, `active_toggles`, `model_overrides`, `owner_email`, and `created_at`.
- **Token_Tier**: The user's current token allocation level: Tier 1 (Unverified, 20 tokens/day), Tier 2 (Verified Email, 50 tokens/day), Tier 3 (Full Profile, 100 tokens/day).
- **SSE_Connection_Tracker**: The existing `SSEConnectionTracker` singleton that tracks active SSE streaming connections per email.
- **Simulation_Transcript**: A human-readable text reconstruction of a negotiation conversation derived from the `history` array in a session document.
- **User_Status**: The operational status of a user account: `active` (normal), `suspended` (temporarily blocked from running simulations), or `banned` (permanently blocked).

## Requirements

### Requirement 1: Admin Authentication

**User Story:** As an admin, I want to authenticate with a single shared password, so that only authorized personnel can access the admin dashboard.

#### Acceptance Criteria

1. THE Admin_API SHALL read the admin password from the `ADMIN_PASSWORD` environment variable at startup.
2. WHEN a request is made to any Admin_API endpoint without a valid admin credential, THE Admin_Auth_Middleware SHALL return a 401 status code with the message "Unauthorized".
3. WHEN a login request is made to `POST /api/v1/admin/login` with the correct password, THE Admin_API SHALL return a 200 status code and set an HTTP-only Admin_Session_Cookie.
4. THE Admin_Auth_Middleware SHALL compare the submitted password against the `ADMIN_PASSWORD` using constant-time string comparison to prevent timing attacks.
5. WHEN more than 10 failed login attempts occur from the same IP address within a 5-minute window, THE Admin_API SHALL return a 429 status code with the message "Too many login attempts".
6. IF the `ADMIN_PASSWORD` environment variable is not set or is empty, THEN THE Admin_API SHALL refuse to start and log an error message indicating the missing configuration.
7. WHEN a request is made to `POST /api/v1/admin/logout`, THE Admin_API SHALL clear the Admin_Session_Cookie and return a 200 status code.

### Requirement 2: Admin Login Page

**User Story:** As an admin, I want a login page at `/admin` that gates access to the dashboard, so that unauthenticated users cannot view admin data.

#### Acceptance Criteria

1. WHEN an unauthenticated user navigates to any `/admin/*` route, THE Admin_Dashboard SHALL display a password input form instead of the dashboard content.
2. WHEN the admin submits the correct password on the login form, THE Admin_Dashboard SHALL redirect to the admin overview page at `/admin`.
3. IF the admin submits an incorrect password, THEN THE Admin_Dashboard SHALL display an error message "Invalid password" without revealing whether the password was close to correct.
4. THE Admin_Dashboard SHALL render the login page server-side to prevent admin route structure from leaking into client JavaScript bundles.
5. WHEN the admin clicks the logout button, THE Admin_Dashboard SHALL clear the session and redirect to the login form.

### Requirement 3: Dashboard Overview

**User Story:** As an admin, I want a system health overview at a glance, so that I can quickly assess platform status without drilling into individual views.

#### Acceptance Criteria

1. WHEN the admin navigates to `/admin`, THE Admin_Dashboard SHALL display the total number of registered users from the Waitlist_Collection.
2. WHEN the admin navigates to `/admin`, THE Admin_Dashboard SHALL display the total number of simulations run today (UTC) from the Sessions_Collection.
3. WHEN the admin navigates to `/admin`, THE Admin_Dashboard SHALL display the current count of active SSE connections from the SSE_Connection_Tracker.
4. THE Admin_Dashboard SHALL display the aggregate AI token consumption for the current day (UTC) by summing `total_tokens_used` across all sessions created today.
5. THE Admin_Dashboard SHALL display scenario analytics showing the number of runs per scenario_id and the average `total_tokens_used` per scenario_id, derived from the Sessions_Collection.
6. THE Admin_Dashboard SHALL display model performance metrics including average latency per model, average token usage per model, and error count per model, derived from session metadata in the Sessions_Collection.
7. THE Admin_Dashboard SHALL display a recent simulations feed showing the last 50 sessions ordered by creation time descending, with each entry showing session_id, scenario_id, deal_status, turn_count, total_tokens_used, and owner_email.
8. THE Admin_API SHALL expose a `GET /api/v1/admin/overview` endpoint that returns all overview metrics in a single response to minimize round trips.

### Requirement 4: User Management

**User Story:** As an admin, I want to view and manage all platform users, so that I can handle support cases and enforce platform policies.

#### Acceptance Criteria

1. THE Admin_API SHALL expose a `GET /api/v1/admin/users` endpoint that returns a paginated list of users from the Waitlist_Collection joined with the Profiles_Collection.
2. WHEN the admin requests the user list, THE Admin_API SHALL return each user's email, signed_up_at, token_balance, last_reset_date, Token_Tier, and User_Status.
3. THE Admin_API SHALL support cursor-based pagination on the user list endpoint with a default page size of 50 and a maximum page size of 200.
4. WHEN the admin requests to adjust a user's token balance via `PATCH /api/v1/admin/users/{email}/tokens`, THE Admin_API SHALL update the `token_balance` field in the Waitlist_Collection document for the specified email.
5. THE Admin_API SHALL validate that the new token balance is a non-negative integer before applying the update.
6. WHEN the admin requests to change a user's status via `PATCH /api/v1/admin/users/{email}/status`, THE Admin_API SHALL update the User_Status field to the specified value (`active`, `suspended`, or `banned`).
7. WHILE a user has a User_Status of `suspended` or `banned`, THE Admin_API SHALL prevent that user from starting new negotiations by returning a 403 status code on `POST /api/v1/negotiation/start`.
8. THE Admin_Dashboard SHALL display the user list in a table with columns for email, tier, token balance, status, signed up date, and action buttons for token adjustment and status changes.
9. THE Admin_API SHALL support filtering the user list by Token_Tier and User_Status via query parameters.

### Requirement 5: Simulation List

**User Story:** As an admin, I want to browse all simulations with their outcomes and metadata, so that I can audit negotiations and gather data for future analytics.

#### Acceptance Criteria

1. THE Admin_API SHALL expose a `GET /api/v1/admin/simulations` endpoint that returns a paginated list of sessions from the Sessions_Collection.
2. WHEN the admin requests the simulation list, THE Admin_API SHALL return each session's session_id, scenario_id, owner_email, deal_status, turn_count, max_turns, total_tokens_used, active_toggles, model_overrides, and created_at.
3. THE Admin_API SHALL support cursor-based pagination on the simulation list endpoint with a default page size of 50 and a maximum page size of 200.
4. THE Admin_API SHALL support filtering simulations by scenario_id, deal_status, and owner_email via query parameters.
5. THE Admin_API SHALL support ordering simulations by created_at descending (default) or ascending.
6. THE Admin_Dashboard SHALL display the simulation list in a table with columns for session ID (truncated), scenario, user email, outcome, turns, AI tokens used, and created date.
7. THE Admin_Dashboard SHALL provide a detail view for each simulation showing the full session metadata and agent configuration.

### Requirement 6: Simulation Transcript Download

**User Story:** As an admin, I want to download a human-readable transcript and raw JSON for any simulation, so that I can review negotiations offline and feed data into analytics tools.

#### Acceptance Criteria

1. THE Admin_API SHALL expose a `GET /api/v1/admin/simulations/{session_id}/transcript` endpoint that returns a Simulation_Transcript as a plain text file.
2. THE Admin_API SHALL reconstruct the Simulation_Transcript from the `history` array in the session document, formatting each entry with the agent role, turn number, inner thought (if present), and public message.
3. THE Admin_API SHALL set the `Content-Disposition` header to `attachment; filename="transcript_{session_id}.txt"` on transcript download responses.
4. THE Admin_API SHALL expose a `GET /api/v1/admin/simulations/{session_id}/json` endpoint that returns the complete raw session document as a JSON file download.
5. THE Admin_API SHALL set the `Content-Disposition` header to `attachment; filename="session_{session_id}.json"` on JSON download responses.
6. IF the requested session_id does not exist, THEN THE Admin_API SHALL return a 404 status code with the message "Session not found".
7. FOR ALL valid session documents, converting the history array to a Simulation_Transcript and then parsing the transcript back into structured entries SHALL preserve the agent role, turn number, and public message of each history entry (round-trip property).

### Requirement 7: CSV Export

**User Story:** As an admin, I want to export user and simulation data as CSV files, so that I can perform offline analysis in spreadsheet tools.

#### Acceptance Criteria

1. THE Admin_API SHALL expose a `GET /api/v1/admin/export/users` endpoint that returns all users as a CSV file download.
2. THE Admin_API SHALL include the following columns in the user CSV: email, signed_up_at, token_balance, last_reset_date, tier, email_verified, display_name, status.
3. THE Admin_API SHALL set the `Content-Disposition` header to `attachment; filename="users_export_{date}.csv"` where `{date}` is the current UTC date in YYYY-MM-DD format.
4. THE Admin_API SHALL expose a `GET /api/v1/admin/export/simulations` endpoint that returns all simulations as a CSV file download.
5. THE Admin_API SHALL include the following columns in the simulation CSV: session_id, scenario_id, owner_email, deal_status, turn_count, max_turns, total_tokens_used, active_toggles, model_overrides, created_at.
6. THE Admin_API SHALL set the `Content-Disposition` header to `attachment; filename="simulations_export_{date}.csv"` where `{date}` is the current UTC date in YYYY-MM-DD format.
7. THE Admin_API SHALL support optional query parameter filters on the export endpoints matching the same filters available on the corresponding list endpoints.
8. THE Admin_API SHALL properly escape CSV field values containing commas, quotes, or newlines per RFC 4180.
9. FOR ALL exported CSV data, parsing the CSV output back into records SHALL produce field values identical to the original data (round-trip property for CSV serialization).

### Requirement 8: Session Metadata for Analytics

**User Story:** As a developer, I want session documents to store sufficient metadata for future analytics, so that the admin dashboard can compute model performance and scenario popularity metrics without additional data sources.

#### Acceptance Criteria

1. WHEN a new negotiation session is created, THE Admin_API SHALL ensure the session document includes a `created_at` server timestamp field.
2. WHEN a negotiation session completes, THE Admin_API SHALL ensure the session document includes a `completed_at` server timestamp field.
3. WHEN a negotiation session completes, THE Admin_API SHALL ensure the session document includes a `duration_seconds` field calculated as the difference between `completed_at` and `created_at`.
4. THE Sessions_Collection documents SHALL store `model_overrides` mapping each agent role to the model_id used, enabling per-model analytics queries.
5. THE Sessions_Collection documents SHALL store `scenario_id` enabling per-scenario analytics queries.
6. THE Sessions_Collection documents SHALL store `total_tokens_used` as an integer representing the total AI tokens consumed across all agents in the session.

### Requirement 9: Admin API Security

**User Story:** As a developer, I want the admin API to follow security best practices, so that the admin interface is resistant to common attack vectors.

#### Acceptance Criteria

1. THE Admin_Auth_Middleware SHALL apply to all Admin_API endpoints except `POST /api/v1/admin/login`.
2. THE Admin_API SHALL reject requests with an invalid or expired Admin_Session_Cookie by returning a 401 status code.
3. THE Admin_API SHALL set the Admin_Session_Cookie with `HttpOnly`, `Secure` (in production), and `SameSite=Strict` attributes.
4. THE Admin_API SHALL set the Admin_Session_Cookie to expire after 8 hours of inactivity.
5. THE Admin_API SHALL log all admin actions (login, logout, token adjustments, status changes) with the timestamp and source IP address.
6. THE Admin_API SHALL validate all path parameters and query parameters using Pydantic V2 models before processing.
7. THE Admin_Dashboard SHALL render admin pages server-side to prevent admin data from being included in client-side JavaScript bundles.
