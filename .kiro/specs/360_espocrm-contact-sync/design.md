# Design Document — EspoCRM Contact Sync

## Overview

This feature adds EspoCRM contact synchronisation to the A2A backend. Two code paths deliver it:

1. **Auto-sync on signup** — `POST /auth/join` fires a background task (`asyncio.create_task`) after writing the new user to Firestore. The task calls the EspoCRM service and its result is logged but never surfaced to the caller. Signup latency is unaffected.

2. **Admin manual sync** — `POST /api/v1/admin/users/{email}/sync-crm` is an awaited, synchronous call so the admin sees the result immediately.

Both paths share a single `EspoCRM_Service` module. The service is the only place that knows about EspoCRM's API shape, authentication, and upsert logic. All other code just calls `sync_contact(email, waitlist_data, profile_data)` and inspects the returned `CrmSyncResult`.

The integration is cloud-only. `RUN_MODE == "local"` causes an immediate `action="skipped"` return with no HTTP calls. Missing config (empty `ESPOCRM_URL` or `ESPOCRM_API_KEY`) produces the same result.

---

## Architecture

```
POST /auth/join (cloud, new user)
  │
  ├─ Firestore write (waitlist doc)
  │
  └─ asyncio.create_task(sync_contact(...))   ← fire-and-forget
       │
       └─ EspoCRM_Service.sync_contact()
            │
            ├─ build_contact_payload()         ← pure function, no I/O
            │
            ├─ GET /api/v1/Contact?where...    ← search by email
            │
            ├─ POST /api/v1/Contact            ← create (0 results)
            │   OR
            └─ PUT  /api/v1/Contact/{id}       ← update (≥1 result)


POST /api/v1/admin/users/{email}/sync-crm
  │
  ├─ verify_admin_session
  ├─ Firestore read (waitlist + profile docs)
  │
  └─ await sync_contact(...)                  ← synchronous, result returned
       │
       └─ (same EspoCRM_Service path as above)
```

### Key design decisions

**`httpx.AsyncClient` over `requests`** — FastAPI is async-native. Using `requests` (synchronous) inside an async handler blocks the event loop. `httpx` is the correct choice.

**Fire-and-forget via `asyncio.create_task`** — CRM latency (network round-trip to `crm.juntoai.org`) must not add to signup response time. The task runs concurrently; any failure is logged at WARNING level and the `LoginResponse` is returned unchanged.

**Admin sync is awaited** — The admin explicitly triggered the sync and needs to know whether it worked. Returning a `CrmSyncResult` with `action="error"` and the error detail is more useful than a 5xx.

**`build_contact_payload` is a pure function** — No I/O, no side effects, deterministic output. This makes it fully unit-testable without mocks and is the primary target for property-based tests.

**Graceful skip on missing config** — The service checks `RUN_MODE` and config completeness before making any HTTP call. This prevents crashes in local dev and in CI where EspoCRM credentials are not present.

**Never raises to caller** — All exceptions (HTTP errors, network failures, unexpected exceptions) are caught inside `sync_contact`. The caller always gets a `CrmSyncResult` back.

---

## Components and Interfaces

### `backend/app/services/espocrm_service.py` (new)

```python
async def sync_contact(
    email: str,
    waitlist_data: dict,
    profile_data: dict | None,
) -> CrmSyncResult:
    """Upsert a Contact in EspoCRM. Never raises."""
    ...

def build_contact_payload(
    email: str,
    waitlist_data: dict,
    profile_data: dict | None,
) -> dict:
    """Pure function. Build the EspoCRM Contact JSON payload."""
    ...
```

`sync_contact` is the only public async entry point. `build_contact_payload` is a public pure function (exported for direct testing).

Internal flow of `sync_contact`:
1. Guard: return `action="skipped"` if `RUN_MODE == "local"` or config is empty.
2. Call `build_contact_payload` to produce the payload dict.
3. Open `httpx.AsyncClient(timeout=10.0)`.
4. `GET /api/v1/Contact?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}` with `X-Api-Key` header.
5. If `response.json()["total"] == 0`: `POST /api/v1/Contact` → return `action="created"`.
6. Else: `PUT /api/v1/Contact/{list[0]["id"]}` → return `action="updated"`.
7. On `httpx.HTTPStatusError` (4xx/5xx): log status + truncated body, return `action="error"`.
8. On `httpx.RequestError` or any other exception: log exception, return `action="error"`.

### `backend/app/models/admin.py` (modified)

Add `CrmSyncResult`:

```python
class CrmSyncResult(BaseModel):
    email: str
    action: Literal["created", "updated", "skipped", "error"]
    detail: str | None = None
```

### `backend/app/config.py` (modified)

Add four settings with empty-string defaults:

```python
ESPOCRM_URL: str = ""
ESPOCRM_API_KEY: str = ""
ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID: str = ""
ESPOCRM_JUNTOAI_TEAM_ID: str = ""
```

### `backend/app/routers/auth.py` (modified)

In the `not doc.exists` branch (cloud mode only), after the Firestore write:

```python
if settings.RUN_MODE == "cloud":
    import asyncio
    from app.services.espocrm_service import sync_contact

    async def _crm_task():
        result = await sync_contact(email_key, {"email": email_key, ...}, None)
        if result.action == "error":
            logger.warning("CRM auto-sync failed for %s: %s", email_key, result.detail)

    asyncio.create_task(_crm_task())
```

The task is only scheduled in cloud mode. The router does not `await` it.

### `backend/app/routers/admin.py` (modified)

New endpoint:

```python
@router.post(
    "/users/{email}/sync-crm",
    response_model=CrmSyncResult,
    dependencies=[Depends(verify_admin_session)],
)
async def admin_sync_crm(email: str) -> CrmSyncResult:
    ...
```

Steps:
1. `require_cloud_mode()` is enforced by `verify_admin_session` chain (503 in local mode).
2. Fetch `waitlist` doc — 404 if not found.
3. Fetch `profiles` doc — `None` if not found (profile is optional).
4. `await sync_contact(email, waitlist_data, profile_data)` — synchronous.
5. Return `CrmSyncResult` with HTTP 200 regardless of `action` value.

---

## Data Models

### `CrmSyncResult`

| Field    | Type                                              | Description                                      |
|----------|---------------------------------------------------|--------------------------------------------------|
| `email`  | `str`                                             | Normalised email that was synced                 |
| `action` | `"created" \| "updated" \| "skipped" \| "error"` | Outcome of the sync attempt                      |
| `detail` | `str \| None`                                     | Human-readable message or truncated error detail |

### EspoCRM Contact Payload

`build_contact_payload` produces this dict (all fields always present):

| Key                      | Source                                                                 | Notes                                    |
|--------------------------|------------------------------------------------------------------------|------------------------------------------|
| `emailAddress`           | `email.lower().strip()`                                                | Dedup key in EspoCRM                     |
| `firstName`              | `profile_data["display_name"].split(" ", 1)[0]` or email local part   | Fallback when no display_name            |
| `lastName`               | `profile_data["display_name"].split(" ", 1)[1]` or `""`               | Empty string when no display_name        |
| `accountId`              | `settings.ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID`                            | Hardcoded to JuntoAI Mini account        |
| `teamsIds`               | `[settings.ESPOCRM_JUNTOAI_TEAM_ID]`                                  | Single-element list                      |
| `juntoaiServices`        | `["a2a"]`                                                              | Hardcoded Multi-Enum for this service    |
| `juntoaiRegisteredAt`    | `waitlist_data["signed_up_at"]` as ISO 8601 UTC, or `utcnow()`        | First registration timestamp             |
| `juntoaiMarketingEmail`  | `True`                                                                 | Implicit consent at signup               |
| `juntoaiConsentTimestamp`| Same value as `juntoaiRegisteredAt`                                    | Consent recorded at signup time          |

### EspoCRM API interaction

| Operation      | Method | Path                                                                                                                    |
|----------------|--------|-------------------------------------------------------------------------------------------------------------------------|
| Search contact | GET    | `/api/v1/Contact?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}`                        |
| Create contact | POST   | `/api/v1/Contact`                                                                                                       |
| Update contact | PUT    | `/api/v1/Contact/{id}`                                                                                                  |

Authentication: `X-Api-Key: {ESPOCRM_API_KEY}` header on every request.

Search response shape (EspoCRM standard):
```json
{"total": 0, "list": []}
{"total": 1, "list": [{"id": "abc123", ...}]}
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

PBT applies here because `build_contact_payload` is a pure function with a large input space (arbitrary email strings, arbitrary dict shapes for waitlist/profile data). Property tests will catch normalization bugs, missing fields, and hardcoded-value regressions that example tests miss. `sync_contact`'s "never raises" guarantee is also a universal property worth testing.

### Property 1: Email normalization round-trip

*For any* string used as an email input, `build_contact_payload` SHALL produce a payload where `emailAddress` equals `email.lower().strip()`.

**Validates: Requirements 2.1, 2.10**

### Property 2: All required fields are always present

*For any* valid email string and any dict inputs for `waitlist_data` and `profile_data`, `build_contact_payload` SHALL produce a payload containing all nine required keys: `emailAddress`, `firstName`, `lastName`, `juntoaiServices`, `juntoaiRegisteredAt`, `juntoaiMarketingEmail`, `juntoaiConsentTimestamp`, `accountId`, `teamsIds`.

**Validates: Requirements 2.11**

### Property 3: Hardcoded field invariants

*For any* input, `build_contact_payload` SHALL produce a payload where:
- `juntoaiServices == ["a2a"]`
- `juntoaiMarketingEmail is True`
- `accountId == settings.ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID`
- `teamsIds == [settings.ESPOCRM_JUNTOAI_TEAM_ID]`

**Validates: Requirements 2.4, 2.6, 2.8, 2.9**

### Property 4: Name splitting from display_name

*For any* `display_name` string containing at least one space, `build_contact_payload` SHALL set `firstName` to the substring before the first space and `lastName` to the remainder after the first space.

**Validates: Requirements 2.2**

### Property 5: Name fallback from email local part

*For any* email string and any `profile_data` that lacks a non-empty `display_name`, `build_contact_payload` SHALL set `firstName` to the local part of the email (before `@`) and `lastName` to `""`.

**Validates: Requirements 2.3**

### Property 6: Consent timestamp equals registered-at

*For any* input, `build_contact_payload` SHALL produce a payload where `juntoaiConsentTimestamp == juntoaiRegisteredAt`.

**Validates: Requirements 2.7**

### Property 7: sync_contact never raises

*For any* email string and any dict inputs, `sync_contact` SHALL return a `CrmSyncResult` without raising an exception, even when the underlying `httpx` client raises arbitrary exceptions.

**Validates: Requirements 1.12**

---

## Error Handling

| Scenario                                  | Behavior                                                                                  |
|-------------------------------------------|-------------------------------------------------------------------------------------------|
| `RUN_MODE == "local"`                     | Return `action="skipped"` immediately, no HTTP calls                                      |
| `ESPOCRM_URL` or `ESPOCRM_API_KEY` empty  | Log WARNING, return `action="skipped"`                                                    |
| EspoCRM 4xx response                      | Log status code + truncated body (500 chars), return `action="error"` with detail         |
| EspoCRM 5xx response                      | Log status code + truncated body (500 chars), return `action="error"` with detail         |
| Network timeout (`httpx.TimeoutException`)| Log exception type + message, return `action="error"` with detail                        |
| Any other exception                       | Log exception type + message, return `action="error"` with detail                        |
| Auto-sync task error (router level)       | Log at WARNING, return normal `LoginResponse` — caller is never affected                  |
| Admin sync error                          | Return HTTP 200 with `CrmSyncResult(action="error", detail=...)` — admin sees the detail  |

No exception ever propagates out of `sync_contact`. The function is a black box that always returns a `CrmSyncResult`.

Logging follows the existing project convention: structured log lines with `action=`, `email=` (normalised only — no raw PII in log messages beyond the email key which is already used as a Firestore document ID throughout the codebase).

---

## Testing Strategy

### Unit tests — `backend/tests/unit/test_espocrm_service.py`

These use `unittest.mock.patch` / `AsyncMock` to mock `httpx.AsyncClient`. No real HTTP calls.

| Test | Covers |
|------|--------|
| `test_sync_contact_creates_new_contact` | Req 1.8 — GET returns total=0, POST is called |
| `test_sync_contact_updates_existing_contact` | Req 1.9 — GET returns total=1, PUT is called with correct ID |
| `test_sync_contact_skips_in_local_mode` | Req 1.2 — no HTTP calls, action="skipped" |
| `test_sync_contact_skips_when_url_empty` | Req 1.3 — empty ESPOCRM_URL |
| `test_sync_contact_skips_when_key_empty` | Req 1.3 — empty ESPOCRM_API_KEY |
| `test_sync_contact_sets_api_key_header` | Req 1.4 — X-Api-Key header present |
| `test_sync_contact_uses_10s_timeout` | Req 1.5 — timeout=10.0 |
| `test_sync_contact_handles_4xx` | Req 1.10 — action="error", detail populated |
| `test_sync_contact_handles_5xx` | Req 1.10 — action="error", detail populated |
| `test_sync_contact_handles_timeout` | Req 1.11 — httpx.TimeoutException → action="error" |
| `test_build_contact_payload_with_display_name` | Req 2.2 — firstName/lastName split |
| `test_build_contact_payload_without_display_name` | Req 2.3 — firstName from email local part |
| `test_build_contact_payload_hardcoded_fields` | Req 2.4, 2.6, 2.8, 2.9 |
| `test_crm_sync_result_model_fields` | Req 4.6 — model has email, action, detail |

### Integration tests — `backend/tests/integration/`

| Test | Covers |
|------|--------|
| `test_admin_sync_crm_success` | Req 4.1, 4.2 — 200 + CrmSyncResult |
| `test_admin_sync_crm_user_not_found` | Req 4.3 — 404 |
| `test_admin_sync_crm_local_mode` | Req 4.5 — 503 |
| `test_admin_sync_crm_error_result` | Req 4.4 — 200 with action="error" |
| `test_join_triggers_crm_task_for_new_user` | Req 3.1, 3.2 — task scheduled for new user |
| `test_join_no_crm_task_for_existing_user` | Req 3.5 — no task for returning user |
| `test_join_no_crm_task_in_local_mode` | Req 3.4 — no task in local mode |

### Property tests — `backend/tests/property/test_espocrm_properties.py`

Uses Hypothesis with `@pytest.mark.property` and `@pytest.mark.slow`. Minimum 100 examples per property.

```python
# Feature: 360_espocrm-contact-sync, Property 1: Email normalization round-trip
@given(email=st.emails())
@settings(max_examples=100, deadline=None)
def test_email_normalization_round_trip(email): ...

# Feature: 360_espocrm-contact-sync, Property 2: All required fields present
@given(email=st.emails(), waitlist_data=st.fixed_dictionaries({...}), ...)
@settings(max_examples=100, deadline=None)
def test_all_required_fields_present(email, waitlist_data, profile_data): ...

# Feature: 360_espocrm-contact-sync, Property 3: Hardcoded field invariants
@given(email=st.emails(), ...)
@settings(max_examples=100, deadline=None)
def test_hardcoded_field_invariants(email, ...): ...

# Feature: 360_espocrm-contact-sync, Property 4: Name splitting from display_name
@given(display_name=st.text(min_size=3).filter(lambda s: " " in s.strip()))
@settings(max_examples=100, deadline=None)
def test_name_splitting_from_display_name(display_name): ...

# Feature: 360_espocrm-contact-sync, Property 5: Name fallback from email local part
@given(email=st.emails())
@settings(max_examples=100, deadline=None)
def test_name_fallback_from_email(email): ...

# Feature: 360_espocrm-contact-sync, Property 6: Consent timestamp equals registered-at
@given(email=st.emails(), ...)
@settings(max_examples=100, deadline=None)
def test_consent_timestamp_equals_registered_at(email, ...): ...

# Feature: 360_espocrm-contact-sync, Property 7: sync_contact never raises
@given(email=st.text(), ...)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
def test_sync_contact_never_raises(email, ...): ...
```

Property 7 mocks `httpx.AsyncClient` to raise `Exception("boom")` so no real HTTP calls are made. The test verifies that `sync_contact` returns a `CrmSyncResult` rather than propagating the exception.

### Coverage

The new service module (`espocrm_service.py`) is pure Python with no external dependencies beyond `httpx` and `settings`. With the unit tests above, line coverage for the new module should exceed 90%. Overall backend coverage remains above the 70% threshold.
