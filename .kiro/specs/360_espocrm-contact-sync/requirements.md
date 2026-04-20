# Requirements Document

## Introduction

This feature adds EspoCRM contact synchronisation to the A2A backend. Two capabilities are delivered:

1. **Auto-sync on signup** — every time a new user joins via `POST /auth/join`, the backend pushes their contact data to EspoCRM directly over HTTPS (no Pub/Sub, no Cloud Function). The call is fire-and-forget: CRM failure must never block signup.

2. **Admin manual sync** — a new `POST /api/v1/admin/users/{email}/sync-crm` endpoint lets an admin backfill any existing user into EspoCRM on demand.

Marketing consent is implicit: users agree to marketing communications at signup via the button label ("by clicking you agree to marketing"). No consent checkbox, no consent field on `JoinRequest`, no consent data stored in Firestore. `juntoaiMarketingEmail` is always `true` and `juntoaiConsentTimestamp` is set to `signed_up_at`.

The integration is cloud-only. When `RUN_MODE == "local"` the CRM sync is skipped entirely.

---

## Glossary

- **EspoCRM_Service**: The new `backend/app/services/espocrm_service.py` module responsible for all EspoCRM API interactions.
- **Contact_Payload**: The JSON object sent to EspoCRM representing a user contact, containing standard and custom fields.
- **Upsert**: Search EspoCRM for an existing Contact by `emailAddress`; update if found, create if not. Never duplicate.
- **Waitlist_Document**: The Firestore document in the `waitlist` collection keyed by normalised email, storing signup metadata.
- **Profile_Document**: The Firestore document in the `profiles` collection keyed by normalised email, storing display name and verification state.
- **Admin_Router**: `backend/app/routers/admin.py` — the existing admin endpoint module.
- **Auth_Router**: `backend/app/routers/auth.py` — the existing auth endpoint module containing `POST /auth/join`.
- **JoinRequest**: The Pydantic V2 model for the `POST /auth/join` request body, currently containing only `email`.
- **CRM_Sync_Result**: The Pydantic V2 response model for the manual sync endpoint, reporting action taken and any error.
- **RUN_MODE**: The `settings.RUN_MODE` config value; `"local"` skips CRM sync, `"cloud"` enables it.
- **ESPOCRM_URL**: Settings field holding the EspoCRM base URL (e.g. `https://crm.juntoai.org`).
- **ESPOCRM_API_KEY**: Settings field holding the `X-Api-Key` value for EspoCRM authentication.
- **ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID**: Settings field holding the EspoCRM Account ID for "JuntoAI Mini".
- **ESPOCRM_JUNTOAI_TEAM_ID**: Settings field holding the EspoCRM Team ID for "JuntoAI".

---

## Requirements

### Requirement 1: EspoCRM Service Module

**User Story:** As a backend developer, I want a dedicated EspoCRM service module, so that all CRM API logic is isolated, testable, and reusable across signup and admin sync.

#### Acceptance Criteria

1. THE `EspoCRM_Service` SHALL expose an async function `sync_contact(email, waitlist_data, profile_data)` that performs the upsert and returns a `CRM_Sync_Result`.
2. WHEN `RUN_MODE == "local"`, THE `EspoCRM_Service` SHALL return immediately with `action="skipped"` and perform no HTTP calls.
3. WHEN `ESPOCRM_URL` or `ESPOCRM_API_KEY` is empty or unset, THE `EspoCRM_Service` SHALL log a warning and return with `action="skipped"`.
4. THE `EspoCRM_Service` SHALL authenticate every EspoCRM API request using the `X-Api-Key` header with the value from `ESPOCRM_API_KEY`.
5. THE `EspoCRM_Service` SHALL use `httpx.AsyncClient` for all outbound HTTP calls with a timeout of 10 seconds.
6. THE `EspoCRM_Service` SHALL build a `Contact_Payload` from the provided data using a pure function `build_contact_payload(email, waitlist_data, profile_data)`.
7. THE `EspoCRM_Service` SHALL search for an existing Contact by calling `GET /api/v1/Contact?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}` on `ESPOCRM_URL`.
8. WHEN the search returns zero results, THE `EspoCRM_Service` SHALL create a new Contact via `POST /api/v1/Contact` with the `Contact_Payload`.
9. WHEN the search returns one or more results, THE `EspoCRM_Service` SHALL update the first matching Contact via `PUT /api/v1/Contact/{id}` with the `Contact_Payload`.
10. IF an HTTP error (4xx or 5xx) is returned by EspoCRM, THEN THE `EspoCRM_Service` SHALL log the status code and response body (truncated to 500 chars) and return with `action="error"` and the error detail.
11. IF a network or timeout exception occurs, THEN THE `EspoCRM_Service` SHALL log the exception type and message and return with `action="error"` and the error detail.
12. THE `EspoCRM_Service` SHALL never raise an unhandled exception to its caller.

---

### Requirement 2: Contact Payload Builder

**User Story:** As a backend developer, I want a deterministic payload builder, so that the EspoCRM Contact fields are always populated correctly and consistently regardless of which code path triggers the sync.

#### Acceptance Criteria

1. THE `build_contact_payload` function SHALL set `emailAddress` to the normalised (lowercased, stripped) email.
2. WHEN `profile_data` contains a `display_name` field, THE `build_contact_payload` function SHALL split it on the first space to derive `firstName` and `lastName`; the remainder after the first space becomes `lastName`.
3. WHEN `profile_data` does not contain a `display_name` field or it is empty, THE `build_contact_payload` function SHALL derive `firstName` from the local part of the email (before `@`) and set `lastName` to an empty string.
4. THE `build_contact_payload` function SHALL set `juntoaiServices` to `["a2a"]` (hardcoded Multi-Enum value for this service).
5. THE `build_contact_payload` function SHALL set `juntoaiRegisteredAt` to the `signed_up_at` value from `waitlist_data`, formatted as an ISO 8601 UTC datetime string; if absent, it SHALL use the current UTC datetime.
6. THE `build_contact_payload` function SHALL set `juntoaiMarketingEmail` to `true` (hardcoded — users implicitly consent at signup).
7. THE `build_contact_payload` function SHALL set `juntoaiConsentTimestamp` to the same value as `juntoaiRegisteredAt` (i.e. `signed_up_at` from `waitlist_data`).
8. THE `build_contact_payload` function SHALL set `accountId` to `ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID` from settings.
9. THE `build_contact_payload` function SHALL set `teamsIds` to `[ESPOCRM_JUNTOAI_TEAM_ID]` from settings.
10. FOR ALL valid email strings, THE `build_contact_payload` function SHALL produce a payload where `emailAddress` equals the normalised input email (round-trip property).
11. FOR ALL valid email strings, THE `build_contact_payload` function SHALL produce a payload that contains all required fields: `emailAddress`, `firstName`, `lastName`, `juntoaiServices`, `juntoaiRegisteredAt`, `juntoaiMarketingEmail`, `juntoaiConsentTimestamp`, `accountId`, `teamsIds`.

---

### Requirement 3: Auto-Sync on Signup

**User Story:** As a product owner, I want every new A2A signup to be automatically pushed to EspoCRM, so that the CRM is always up to date without manual intervention.

#### Acceptance Criteria

1. WHEN a new user is created in `POST /auth/join` (cloud mode, `doc.exists == False`), THE `Auth_Router` SHALL call `EspoCRM_Service.sync_contact` after the Firestore write completes.
2. THE `Auth_Router` SHALL call `sync_contact` as a fire-and-forget background task using `asyncio.create_task` so that CRM latency does not add to the signup response time.
3. IF `sync_contact` raises or returns an error, THE `Auth_Router` SHALL log the error at WARNING level and return the normal `LoginResponse` to the caller without modification.
4. WHEN `RUN_MODE == "local"`, THE `Auth_Router` SHALL NOT call `sync_contact` (the service itself also guards, but the router must not even schedule the task in local mode).
5. WHEN an existing user calls `POST /auth/join` (returning user), THE `Auth_Router` SHALL NOT trigger a CRM sync.

---

### Requirement 4: Admin Manual Sync Endpoint

**User Story:** As an admin, I want to manually trigger a CRM sync for any existing user, so that I can backfill users who signed up before the integration existed.

#### Acceptance Criteria

1. THE `Admin_Router` SHALL expose `POST /api/v1/admin/users/{email}/sync-crm` protected by `verify_admin_session`.
2. WHEN the endpoint is called with a valid admin session and an email that exists in the `waitlist` collection, THE `Admin_Router` SHALL call `EspoCRM_Service.sync_contact` synchronously (awaited, not fire-and-forget) and return a `CRM_Sync_Result` with HTTP 200.
3. WHEN the endpoint is called with an email that does not exist in the `waitlist` collection, THE `Admin_Router` SHALL return HTTP 404 with `{"detail": "User not found"}`.
4. WHEN `sync_contact` returns `action="error"`, THE `Admin_Router` SHALL return HTTP 200 with the `CRM_Sync_Result` (the error detail is surfaced to the admin, not converted to a 5xx).
5. WHEN `RUN_MODE == "local"`, THE `Admin_Router` SHALL return HTTP 503 (via the existing `require_cloud_mode` dependency) before reaching the sync logic.
6. THE `CRM_Sync_Result` model SHALL contain: `email` (str), `action` (str — one of `"created"`, `"updated"`, `"skipped"`, `"error"`), `detail` (str | None — human-readable message or error).
7. THE `Admin_Router` SHALL read the `Waitlist_Document` and `Profile_Document` for the given email and pass both to `sync_contact`.

---

### Requirement 5: Configuration

**User Story:** As a DevOps engineer, I want all EspoCRM connection parameters to be environment-variable-driven, so that credentials are never hardcoded and the integration can be configured per environment.

#### Acceptance Criteria

1. THE `Settings` class in `backend/app/config.py` SHALL include `ESPOCRM_URL: str = ""`.
2. THE `Settings` class SHALL include `ESPOCRM_API_KEY: str = ""`.
3. THE `Settings` class SHALL include `ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID: str = ""`.
4. THE `Settings` class SHALL include `ESPOCRM_JUNTOAI_TEAM_ID: str = ""`.
5. WHEN any of the four EspoCRM settings are empty strings, THE `EspoCRM_Service` SHALL treat the integration as unconfigured and skip the sync (Requirement 1.3).
6. THE four EspoCRM settings SHALL be loadable from the `.env` file via the existing `pydantic-settings` `SettingsConfigDict` mechanism.

---

### Requirement 6: Unit and Property Tests

**User Story:** As a developer, I want comprehensive tests for the EspoCRM integration, so that regressions are caught before deployment and coverage stays above 70%.

#### Acceptance Criteria

1. THE test suite SHALL include unit tests for `EspoCRM_Service.sync_contact` covering: new contact creation (search returns 0 results), existing contact update (search returns 1 result), skip when `RUN_MODE == "local"`, skip when `ESPOCRM_URL` is empty, HTTP 4xx error handling, HTTP 5xx error handling, and network timeout handling.
2. THE test suite SHALL include a unit test for `POST /api/v1/admin/users/{email}/sync-crm` covering: successful sync (200 + CRM_Sync_Result), user not found (404), and local mode (503).
3. THE test suite SHALL include a property-based test using Hypothesis: FOR ALL valid email strings (RFC 5321 local part + domain), `build_contact_payload` SHALL produce a payload where `emailAddress` equals the normalised input (round-trip property — Requirement 2.10).
4. THE test suite SHALL include a property-based test: FOR ALL valid email strings, `build_contact_payload` SHALL produce a payload containing all required fields: `emailAddress`, `firstName`, `lastName`, `juntoaiServices`, `juntoaiRegisteredAt`, `juntoaiMarketingEmail`, `juntoaiConsentTimestamp`, `accountId`, `teamsIds` (Requirement 2.11).
5. ALL `httpx` calls in `EspoCRM_Service` SHALL be mocked using `unittest.mock` — no real HTTP calls in unit tests.
6. THE tests SHALL be placed in `backend/tests/unit/test_espocrm_service.py` and `backend/tests/property/test_espocrm_properties.py`, following existing project conventions.
7. THE test suite SHALL maintain overall backend coverage at or above 70% after the new code is added.
