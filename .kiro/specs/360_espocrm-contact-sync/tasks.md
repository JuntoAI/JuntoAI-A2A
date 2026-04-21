# Implementation Plan: EspoCRM Contact Sync

## Overview

Add EspoCRM contact synchronisation to the A2A backend. Deliver two code paths — fire-and-forget auto-sync on signup and an awaited admin manual sync endpoint — backed by a single isolated service module. All HTTP calls use `httpx.AsyncClient`. The integration is cloud-only; local mode skips silently.

## Tasks

- [x] 1. Add EspoCRM settings to `backend/app/config.py`
  - Add four fields to the `Settings` class: `ESPOCRM_URL: str = ""`, `ESPOCRM_API_KEY: str = ""`, `ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID: str = ""`, `ESPOCRM_JUNTOAI_TEAM_ID: str = ""`
  - Fields must use the existing `SettingsConfigDict(env_file=".env")` mechanism — no extra wiring needed
  - Verify `httpx` is present in `backend/requirements.txt`; add it with a pinned version (e.g. `httpx==0.27.2`) if missing
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

- [x] 2. Add `CrmSyncResult` model to `backend/app/models/admin.py`
  - Append the Pydantic V2 model after the existing models:
    ```python
    class CrmSyncResult(BaseModel):
        email: str
        action: Literal["created", "updated", "skipped", "error"]
        detail: str | None = None
    ```
  - Import `Literal` is already present in the file — no new imports needed
  - _Requirements: 4.6_

- [x] 3. Implement `build_contact_payload` in `backend/app/services/espocrm_service.py`
  - Create the new file; implement `build_contact_payload(email, waitlist_data, profile_data)` as a pure function (no I/O, no side effects)
  - Normalise email: `email.lower().strip()`
  - Name splitting: if `profile_data` has a non-empty `display_name`, split on first space → `firstName` / `lastName`; otherwise derive `firstName` from the email local part (before `@`) and set `lastName = ""`
  - Hardcoded fields: `juntoaiServices=["a2a"]`, `juntoaiMarketingEmail=True`
  - `juntoaiRegisteredAt`: use `waitlist_data["signed_up_at"]` formatted as ISO 8601 UTC string; fall back to `datetime.now(timezone.utc).isoformat()` if absent
  - `juntoaiConsentTimestamp`: identical value to `juntoaiRegisteredAt`
  - `accountId`: `settings.ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID`
  - `teamsIds`: `[settings.ESPOCRM_JUNTOAI_TEAM_ID]`
  - All nine keys must always be present in the returned dict
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

  - [x] 3.1 Write property test — Property 1: email normalisation round-trip
    - File: `backend/tests/property/test_espocrm_properties.py`
    - `@given(email=st.emails())` — assert `payload["emailAddress"] == email.lower().strip()`
    - Annotate: `# Feature: 360_espocrm-contact-sync, Property 1`
    - `@settings(max_examples=100, deadline=None)`, `@pytest.mark.property`, `@pytest.mark.slow`
    - **Property 1: Email normalisation round-trip**
    - **Validates: Requirements 2.1, 2.10**

  - [x] 3.2 Write property test — Property 2: all required fields always present
    - Same file as 3.1
    - `@given(email=st.emails(), waitlist_data=st.fixed_dictionaries({}), profile_data=st.none() | st.fixed_dictionaries({}))`
    - Assert all nine keys exist in the returned payload
    - Annotate: `# Feature: 360_espocrm-contact-sync, Property 2`
    - **Property 2: All required fields always present**
    - **Validates: Requirements 2.11**

  - [x] 3.3 Write property test — Property 3: hardcoded field invariants
    - Same file
    - `@given(email=st.emails(), ...)` — assert `juntoaiServices == ["a2a"]`, `juntoaiMarketingEmail is True`, `accountId == settings.ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID`, `teamsIds == [settings.ESPOCRM_JUNTOAI_TEAM_ID]`
    - Annotate: `# Feature: 360_espocrm-contact-sync, Property 3`
    - **Property 3: Hardcoded field invariants**
    - **Validates: Requirements 2.4, 2.6, 2.8, 2.9**

  - [x] 3.4 Write property test — Property 4: name splitting from display_name
    - Same file
    - `@given(display_name=st.text(min_size=3).filter(lambda s: " " in s.strip()))` — assert `firstName == display_name.split(" ", 1)[0]` and `lastName == display_name.split(" ", 1)[1]`
    - Annotate: `# Feature: 360_espocrm-contact-sync, Property 4`
    - **Property 4: Name splitting from display_name**
    - **Validates: Requirements 2.2**

  - [x] 3.5 Write property test — Property 5: name fallback from email local part
    - Same file
    - `@given(email=st.emails())` with `profile_data=None` — assert `firstName == email.split("@")[0]` and `lastName == ""`
    - Annotate: `# Feature: 360_espocrm-contact-sync, Property 5`
    - **Property 5: Name fallback from email local part**
    - **Validates: Requirements 2.3**

  - [x] 3.6 Write property test — Property 6: consent timestamp equals registered-at
    - Same file
    - `@given(email=st.emails(), ...)` — assert `payload["juntoaiConsentTimestamp"] == payload["juntoaiRegisteredAt"]`
    - Annotate: `# Feature: 360_espocrm-contact-sync, Property 6`
    - **Property 6: Consent timestamp equals registered-at**
    - **Validates: Requirements 2.7**

- [x] 4. Implement `sync_contact` in `backend/app/services/espocrm_service.py`
  - Add the async function `sync_contact(email, waitlist_data, profile_data) -> CrmSyncResult` to the same file
  - Guard 1: if `settings.RUN_MODE == "local"` → return `CrmSyncResult(email=email, action="skipped")`
  - Guard 2: if `settings.ESPOCRM_URL` or `settings.ESPOCRM_API_KEY` is empty → log WARNING, return `CrmSyncResult(email=email, action="skipped")`
  - Call `build_contact_payload` to produce the payload
  - Open `httpx.AsyncClient(timeout=10.0)` with `X-Api-Key` header on every request
  - `GET /api/v1/Contact?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}` — check `response.json()["total"]`
  - If `total == 0`: `POST /api/v1/Contact` → return `action="created"`
  - If `total >= 1`: `PUT /api/v1/Contact/{list[0]["id"]}` → return `action="updated"`
  - Catch `httpx.HTTPStatusError`: log status code + body truncated to 500 chars, return `action="error"` with detail
  - Catch `httpx.RequestError` and bare `Exception`: log exception type + message, return `action="error"` with detail
  - Function must never raise — all paths return a `CrmSyncResult`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 1.12_

  - [x] 4.1 Write unit tests for `sync_contact` in `backend/tests/unit/test_espocrm_service.py`
    - Create the new file; mock `httpx.AsyncClient` with `unittest.mock.AsyncMock` — no real HTTP calls
    - Cover: new contact creation (GET total=0 → POST called), existing contact update (GET total=1 → PUT called with correct ID), skip in local mode (no HTTP calls), skip when `ESPOCRM_URL` empty, skip when `ESPOCRM_API_KEY` empty, `X-Api-Key` header present on requests, timeout=10.0 used, HTTP 4xx → `action="error"`, HTTP 5xx → `action="error"`, `httpx.TimeoutException` → `action="error"`
    - Also cover `build_contact_payload` examples: with `display_name`, without `display_name`, hardcoded fields, `CrmSyncResult` model field validation
    - Mark with `@pytest.mark.unit`
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.8, 1.9, 1.10, 1.11, 2.2, 2.3, 2.4, 2.6, 2.8, 2.9, 4.6, 6.1_

  - [x] 4.2 Write property test — Property 7: `sync_contact` never raises
    - File: `backend/tests/property/test_espocrm_properties.py`
    - `@given(email=st.text(), waitlist_data=st.dictionaries(...), profile_data=st.none() | st.dictionaries(...))`
    - Mock `httpx.AsyncClient` to raise `Exception("boom")` — assert `sync_contact` returns a `CrmSyncResult` without propagating
    - `@pytest.mark.asyncio`, `@settings(max_examples=50, deadline=None)`, `@pytest.mark.property`, `@pytest.mark.slow`
    - Annotate: `# Feature: 360_espocrm-contact-sync, Property 7`
    - **Property 7: sync_contact never raises**
    - **Validates: Requirements 1.12**

- [x] 5. Checkpoint — run unit and property tests for the service module
  - Ensure all tests pass, ask the user if questions arise.
  - Run: `cd backend && pytest tests/unit/test_espocrm_service.py tests/property/test_espocrm_properties.py -v`

- [x] 6. Wire auto-sync into `backend/app/routers/auth.py`
  - In the `not doc.exists` branch (cloud mode, Firestore path only), after the `waitlist_ref.set(...)` call, add the fire-and-forget task:
    ```python
    if settings.RUN_MODE == "cloud":
        import asyncio
        from app.services.espocrm_service import sync_contact as _sync_contact

        waitlist_snapshot = {"email": email_key, "signed_up_at": datetime.now(timezone.utc).isoformat()}

        async def _crm_task() -> None:
            result = await _sync_contact(email_key, waitlist_snapshot, None)
            if result.action == "error":
                logger.warning("CRM auto-sync failed for %s: %s", email_key, result.detail)

        asyncio.create_task(_crm_task())
    ```
  - The task must NOT be scheduled for existing users (the `else` branch) or in local mode
  - The router must not `await` the task — fire-and-forget only
  - The `LoginResponse` returned to the caller is never modified regardless of CRM outcome
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 7. Add `POST /admin/users/{email}/sync-crm` to `backend/app/routers/admin.py`
  - Import `CrmSyncResult` from `app.models.admin` at the top of the file
  - Add the new endpoint after the existing user management endpoints:
    ```python
    @router.post(
        "/users/{email}/sync-crm",
        response_model=CrmSyncResult,
        dependencies=[Depends(verify_admin_session)],
    )
    async def admin_sync_crm(email: str) -> CrmSyncResult:
        ...
    ```
  - Steps inside the handler:
    1. Normalise email: `email.lower().strip()`
    2. Fetch `waitlist` doc — raise `HTTPException(404, "User not found")` if not found
    3. Fetch `profiles` doc — pass `None` if not found (profile is optional)
    4. `await sync_contact(email_key, waitlist_data, profile_data)` — synchronous, awaited
    5. Return the `CrmSyncResult` with HTTP 200 regardless of `action` value
  - `require_cloud_mode` is already enforced by `verify_admin_session` — no extra guard needed (503 in local mode)
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7_

  - [x] 7.1 Write unit tests for the admin sync endpoint in `backend/tests/unit/test_espocrm_service.py`
    - Add tests using FastAPI `TestClient` or `httpx.AsyncClient` against the app
    - Cover: successful sync returns 200 + `CrmSyncResult`, user not found returns 404, local mode returns 503, `sync_contact` returning `action="error"` still returns 200 with the error detail
    - Mock `sync_contact` and Firestore reads with `unittest.mock.patch` / `AsyncMock`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 6.2_

- [x] 8. Final checkpoint — full backend test suite
  - Ensure all tests pass, ask the user if questions arise.
  - Run: `cd backend && pytest --cov=app --cov-fail-under=70 -x -q`
  - Verify overall coverage remains at or above 70%

## Notes

- Sub-tasks marked with `*` are optional and can be skipped for a faster MVP iteration
- All property tests use `@pytest.mark.property` and `@pytest.mark.slow` — run selectively with `pytest -m "not slow"` to skip them in fast CI passes
- Use `--hypothesis-seed=0` for reproducible property test runs in CI
- `httpx` must be pinned in `requirements.txt` — open ranges are not acceptable
- The `sync_contact` function is the only place that touches EspoCRM's API; keep it that way
- Do not add a `signed_up_at` re-read from Firestore in the auth router — pass the value written in the same request to avoid a redundant round-trip
