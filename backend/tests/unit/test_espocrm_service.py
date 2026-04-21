
"""Unit tests for the EspoCRM contact sync service.

Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.8, 1.9, 1.10, 1.11,
           2.2, 2.3, 2.4, 2.6, 2.8, 2.9, 4.6, 6.1
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.admin import CrmSyncResult
from app.services.espocrm_service import build_contact_payload, sync_contact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_httpx_response(status_code: int, json_data: dict) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _make_mock_client(
    search_response: MagicMock,
    create_response: MagicMock | None = None,
    update_response: MagicMock | None = None,
) -> MagicMock:
    """Build a mock httpx.AsyncClient context manager."""
    client = MagicMock()
    client.get = AsyncMock(return_value=search_response)
    if create_response is not None:
        client.post = AsyncMock(return_value=create_response)
    if update_response is not None:
        client.put = AsyncMock(return_value=update_response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


CLOUD_SETTINGS = {
    "RUN_MODE": "cloud",
    "ESPOCRM_URL": "https://crm.example.com",
    "ESPOCRM_API_KEY": "test-api-key",
    "ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID": "acc-123",
    "ESPOCRM_JUNTOAI_TEAM_ID": "team-456",
}


def _patch_settings(**overrides):
    """Return a context manager that patches settings with cloud defaults + overrides."""
    merged = {**CLOUD_SETTINGS, **overrides}

    mock_settings = MagicMock()
    for k, v in merged.items():
        setattr(mock_settings, k, v)
    return patch("app.services.espocrm_service.settings", mock_settings)


# ---------------------------------------------------------------------------
# Tests: build_contact_payload
# ---------------------------------------------------------------------------


class TestBuildContactPayload:
    """Unit tests for the pure payload builder function."""

    def test_with_display_name_splits_first_last(self):
        """Req 2.2: display_name split on first space."""
        payload = build_contact_payload(
            "user@example.com",
            {},
            {"display_name": "Jane Doe"},
        )
        assert payload["firstName"] == "Jane"
        assert payload["lastName"] == "Doe"

    def test_with_multi_word_display_name(self):
        """Req 2.2: remainder after first space becomes lastName."""
        payload = build_contact_payload(
            "user@example.com",
            {},
            {"display_name": "Mary Jane Watson"},
        )
        assert payload["firstName"] == "Mary"
        assert payload["lastName"] == "Jane Watson"

    def test_without_display_name_uses_email_local_part(self):
        """Req 2.3: no display_name → firstName from email local part, lastName empty."""
        payload = build_contact_payload("john.doe@example.com", {}, None)
        assert payload["firstName"] == "john.doe"
        assert payload["lastName"] == ""

    def test_empty_display_name_falls_back_to_email(self):
        """Req 2.3: empty display_name → fallback to email local part."""
        payload = build_contact_payload(
            "alice@example.com",
            {},
            {"display_name": ""},
        )
        assert payload["firstName"] == "alice"
        assert payload["lastName"] == ""

    def test_hardcoded_fields(self):
        """Req 2.4, 2.6, 2.8, 2.9: hardcoded field values."""
        with _patch_settings():
            payload = build_contact_payload("user@example.com", {}, None)

        assert payload["juntoaiServices"] == ["a2a"]
        assert payload["juntoaiMarketingEmail"] is True
        assert payload["accountId"] == "acc-123"
        assert payload["teamsIds"] == ["team-456"]

    def test_email_normalised(self):
        """Req 2.1: email is lowercased and stripped."""
        payload = build_contact_payload("  USER@EXAMPLE.COM  ", {}, None)
        assert payload["emailAddress"] == "user@example.com"

    def test_signed_up_at_used_for_registered_at(self):
        """Req 2.5: signed_up_at from waitlist_data used for juntoaiRegisteredAt."""
        payload = build_contact_payload(
            "user@example.com",
            {"signed_up_at": "2025-01-15T10:00:00+00:00"},
            None,
        )
        assert payload["juntoaiRegisteredAt"] == "2025-01-15T10:00:00+00:00"

    def test_consent_timestamp_equals_registered_at(self):
        """Req 2.7: juntoaiConsentTimestamp == juntoaiRegisteredAt."""
        payload = build_contact_payload(
            "user@example.com",
            {"signed_up_at": "2025-01-15T10:00:00+00:00"},
            None,
        )
        assert payload["juntoaiConsentTimestamp"] == payload["juntoaiRegisteredAt"]

    def test_all_nine_keys_present(self):
        """Req 2.11: all nine required keys always present."""
        required = {
            "emailAddress", "firstName", "lastName", "juntoaiServices",
            "juntoaiRegisteredAt", "juntoaiMarketingEmail",
            "juntoaiConsentTimestamp", "accountId", "teamsIds",
        }
        payload = build_contact_payload("user@example.com", {}, None)
        assert required.issubset(payload.keys())


# ---------------------------------------------------------------------------
# Tests: CrmSyncResult model
# ---------------------------------------------------------------------------


class TestCrmSyncResultModel:
    """Req 4.6: CrmSyncResult model field validation."""

    def test_created_action(self):
        result = CrmSyncResult(email="user@example.com", action="created")
        assert result.email == "user@example.com"
        assert result.action == "created"
        assert result.detail is None

    def test_updated_action(self):
        result = CrmSyncResult(email="user@example.com", action="updated")
        assert result.action == "updated"

    def test_skipped_action(self):
        result = CrmSyncResult(email="user@example.com", action="skipped")
        assert result.action == "skipped"

    def test_error_action_with_detail(self):
        result = CrmSyncResult(
            email="user@example.com",
            action="error",
            detail="HTTP 500: Internal Server Error",
        )
        assert result.action == "error"
        assert result.detail == "HTTP 500: Internal Server Error"

    def test_invalid_action_rejected(self):
        """Pydantic V2 should reject invalid action values."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CrmSyncResult(email="user@example.com", action="invalid")


# ---------------------------------------------------------------------------
# Tests: sync_contact
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSyncContactSkipGuards:
    """Req 1.2, 1.3: skip guards."""

    async def test_skips_in_local_mode(self):
        """Req 1.2: local mode → action=skipped, no HTTP calls."""
        with _patch_settings(RUN_MODE="local"):
            with patch("app.services.espocrm_service.httpx.AsyncClient") as mock_cls:
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "skipped"
        mock_cls.assert_not_called()

    async def test_skips_when_url_empty(self):
        """Req 1.3: empty ESPOCRM_URL → action=skipped."""
        with _patch_settings(ESPOCRM_URL=""):
            with patch("app.services.espocrm_service.httpx.AsyncClient") as mock_cls:
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "skipped"
        mock_cls.assert_not_called()

    async def test_skips_when_api_key_empty(self):
        """Req 1.3: empty ESPOCRM_API_KEY → action=skipped."""
        with _patch_settings(ESPOCRM_API_KEY=""):
            with patch("app.services.espocrm_service.httpx.AsyncClient") as mock_cls:
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "skipped"
        mock_cls.assert_not_called()


@pytest.mark.unit
class TestSyncContactUpsert:
    """Req 1.8, 1.9: create vs update logic."""

    async def test_creates_new_contact_when_total_zero(self):
        """Req 1.8: GET returns total=0 → POST called, action=created."""
        search_resp = _make_httpx_response(200, {"total": 0, "list": []})
        create_resp = _make_httpx_response(200, {"id": "new-id"})
        mock_client = _make_mock_client(search_resp, create_response=create_resp)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "created"
        mock_client.post.assert_called_once()
        mock_client.put.assert_not_called()

    async def test_updates_existing_contact_when_total_one(self):
        """Req 1.9: GET returns total=1 → PUT called with correct ID, action=updated."""
        search_resp = _make_httpx_response(
            200, {"total": 1, "list": [{"id": "existing-id-abc"}]}
        )
        update_resp = _make_httpx_response(200, {"id": "existing-id-abc"})
        mock_client = _make_mock_client(search_resp, update_response=update_resp)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "updated"
        mock_client.put.assert_called_once()
        call_url = mock_client.put.call_args[0][0]
        assert "existing-id-abc" in call_url
        mock_client.post.assert_not_called()

    async def test_updates_first_contact_when_multiple_results(self):
        """Req 1.9: GET returns total>=1 → uses first list item's ID."""
        search_resp = _make_httpx_response(
            200,
            {
                "total": 2,
                "list": [
                    {"id": "first-id"},
                    {"id": "second-id"},
                ],
            },
        )
        update_resp = _make_httpx_response(200, {"id": "first-id"})
        mock_client = _make_mock_client(search_resp, update_response=update_resp)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "updated"
        call_url = mock_client.put.call_args[0][0]
        assert "first-id" in call_url


@pytest.mark.unit
class TestSyncContactHeaders:
    """Req 1.4, 1.5: authentication header and timeout."""

    async def test_api_key_header_present(self):
        """Req 1.4: X-Api-Key header set on every request."""
        search_resp = _make_httpx_response(200, {"total": 0, "list": []})
        create_resp = _make_httpx_response(200, {"id": "new-id"})
        mock_client = _make_mock_client(search_resp, create_response=create_resp)

        with _patch_settings():
            with patch(
                "app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client
            ) as mock_cls:
                await sync_contact("user@example.com", {}, None)

        # Check that AsyncClient was instantiated with the X-Api-Key header
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("headers", {}).get("X-Api-Key") == "test-api-key"

    async def test_timeout_is_10_seconds(self):
        """Req 1.5: timeout=10.0 used."""
        search_resp = _make_httpx_response(200, {"total": 0, "list": []})
        create_resp = _make_httpx_response(200, {"id": "new-id"})
        mock_client = _make_mock_client(search_resp, create_response=create_resp)

        with _patch_settings():
            with patch(
                "app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client
            ) as mock_cls:
                await sync_contact("user@example.com", {}, None)

        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("timeout") == 10.0


@pytest.mark.unit
class TestSyncContactErrorHandling:
    """Req 1.10, 1.11, 1.12: error handling."""

    async def test_http_4xx_returns_error_action(self):
        """Req 1.10: HTTP 4xx → action=error with detail."""
        error_resp = _make_httpx_response(404, {"error": "Not Found"})
        mock_client = _make_mock_client(error_resp)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "error"
        assert result.detail is not None
        assert "404" in result.detail

    async def test_http_5xx_returns_error_action(self):
        """Req 1.10: HTTP 5xx → action=error with detail."""
        error_resp = _make_httpx_response(500, {"error": "Internal Server Error"})
        mock_client = _make_mock_client(error_resp)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "error"
        assert result.detail is not None
        assert "500" in result.detail

    async def test_timeout_exception_returns_error_action(self):
        """Req 1.11: httpx.TimeoutException → action=error."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "error"
        assert result.detail is not None

    async def test_request_error_returns_error_action(self):
        """Req 1.11: httpx.RequestError → action=error."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "error"
        assert result.detail is not None

    async def test_unexpected_exception_returns_error_action(self):
        """Req 1.12: arbitrary exception → action=error, never raises."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(side_effect=RuntimeError("unexpected"))
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                result = await sync_contact("user@example.com", {}, None)

        assert result.action == "error"
        assert "RuntimeError" in (result.detail or "")

    async def test_never_raises_to_caller(self):
        """Req 1.12: sync_contact must never propagate exceptions."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(side_effect=Exception("boom"))
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                # Should not raise
                result = await sync_contact("user@example.com", {}, None)

        assert isinstance(result, CrmSyncResult)

    async def test_email_normalised_in_result(self):
        """Result email is normalised regardless of input casing."""
        search_resp = _make_httpx_response(200, {"total": 0, "list": []})
        create_resp = _make_httpx_response(200, {"id": "new-id"})
        mock_client = _make_mock_client(search_resp, create_response=create_resp)

        with _patch_settings():
            with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
                result = await sync_contact("  USER@EXAMPLE.COM  ", {}, None)

        assert result.email == "user@example.com"


# ---------------------------------------------------------------------------
# Tests: POST /admin/users/{email}/sync-crm endpoint
# Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 6.2
# ---------------------------------------------------------------------------


def _build_admin_app(run_mode: str = "cloud", admin_password: str = "test-secret"):
    """Build a fresh app instance with the given settings."""
    import importlib

    with patch.dict(os.environ, {
        "ADMIN_PASSWORD": admin_password,
        "RUN_MODE": run_mode,
        "ENVIRONMENT": "development",
    }):
        import app.config as config_mod
        importlib.reload(config_mod)

        import app.routers.admin as admin_mod
        importlib.reload(admin_mod)

        import app.main as main_mod
        importlib.reload(main_mod)

        return main_mod.app


def _make_admin_cookie(password: str = "test-secret") -> str:
    from itsdangerous import URLSafeTimedSerializer
    s = URLSafeTimedSerializer(password)
    return s.dumps("admin")


def _make_firestore_doc_mock(exists: bool, data: dict | None = None) -> MagicMock:
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data or {}
    return doc


def _make_admin_db(
    waitlist_exists: bool = True,
    waitlist_data: dict | None = None,
    profile_exists: bool = False,
    profile_data: dict | None = None,
) -> MagicMock:
    """Build a mock Firestore db for admin sync endpoint tests."""
    db = MagicMock()

    waitlist_doc = _make_firestore_doc_mock(waitlist_exists, waitlist_data or {
        "email": "user@example.com",
        "signed_up_at": "2025-01-01T00:00:00+00:00",
        "token_balance": 20,
    })
    profile_doc = _make_firestore_doc_mock(profile_exists, profile_data or {})

    waitlist_ref = MagicMock()
    waitlist_ref.get = AsyncMock(return_value=waitlist_doc)

    profile_ref = MagicMock()
    profile_ref.get = AsyncMock(return_value=profile_doc)

    def collection_router(name):
        coll = MagicMock()
        if name == "waitlist":
            coll.document.return_value = waitlist_ref
        elif name == "profiles":
            coll.document.return_value = profile_ref
        else:
            coll.document.return_value = MagicMock()
        return coll

    db.collection.side_effect = collection_router
    return db


@pytest.mark.unit
class TestAdminSyncCrmEndpoint:
    """Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 6.2"""

    async def test_successful_sync_returns_200_with_crm_result(self):
        """Req 4.1, 4.2: valid admin session + existing user → 200 + CrmSyncResult."""
        app_instance = _build_admin_app()
        db = _make_admin_db(waitlist_exists=True)

        mock_result = CrmSyncResult(email="user@example.com", action="created")

        with patch("app.db.get_firestore_db", return_value=db):
            with patch(
                "app.services.espocrm_service.sync_contact",
                new=AsyncMock(return_value=mock_result),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app_instance),
                    base_url="http://testserver",
                ) as client:
                    resp = await client.post(
                        "/api/v1/admin/users/user@example.com/sync-crm",
                        cookies={"admin_session": _make_admin_cookie()},
                    )

        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@example.com"
        assert data["action"] == "created"

    async def test_user_not_found_returns_404(self):
        """Req 4.3: email not in waitlist → 404."""
        app_instance = _build_admin_app()
        db = _make_admin_db(waitlist_exists=False)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url="http://testserver",
            ) as client:
                resp = await client.post(
                    "/api/v1/admin/users/nobody@example.com/sync-crm",
                    cookies={"admin_session": _make_admin_cookie()},
                )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "User not found"

    async def test_local_mode_returns_503(self):
        """Req 4.5: local mode → 503 (via verify_admin_session → require_cloud_mode)."""
        app_instance = _build_admin_app(run_mode="local")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/admin/users/user@example.com/sync-crm",
                cookies={"admin_session": _make_admin_cookie()},
            )

        assert resp.status_code == 503

    async def test_sync_error_still_returns_200(self):
        """Req 4.4: sync_contact returning action=error → HTTP 200 with error detail."""
        app_instance = _build_admin_app()
        db = _make_admin_db(waitlist_exists=True)

        mock_result = CrmSyncResult(
            email="user@example.com",
            action="error",
            detail="HTTP 500: Internal Server Error",
        )

        with patch("app.db.get_firestore_db", return_value=db):
            with patch(
                "app.services.espocrm_service.sync_contact",
                new=AsyncMock(return_value=mock_result),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app_instance),
                    base_url="http://testserver",
                ) as client:
                    resp = await client.post(
                        "/api/v1/admin/users/user@example.com/sync-crm",
                        cookies={"admin_session": _make_admin_cookie()},
                    )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "error"
        assert "500" in data["detail"]

    async def test_updated_action_returned_correctly(self):
        """Req 4.2: action=updated is returned correctly."""
        app_instance = _build_admin_app()
        db = _make_admin_db(waitlist_exists=True)

        mock_result = CrmSyncResult(email="user@example.com", action="updated")

        with patch("app.db.get_firestore_db", return_value=db):
            with patch(
                "app.services.espocrm_service.sync_contact",
                new=AsyncMock(return_value=mock_result),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app_instance),
                    base_url="http://testserver",
                ) as client:
                    resp = await client.post(
                        "/api/v1/admin/users/user@example.com/sync-crm",
                        cookies={"admin_session": _make_admin_cookie()},
                    )

        assert resp.status_code == 200
        assert resp.json()["action"] == "updated"

    async def test_unauthenticated_returns_401(self):
        """Req 4.1: no admin session cookie → 401."""
        app_instance = _build_admin_app()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/admin/users/user@example.com/sync-crm",
            )

        assert resp.status_code == 401

    async def test_profile_passed_to_sync_when_exists(self):
        """Req 4.7: profile document is fetched and passed to sync_contact."""
        app_instance = _build_admin_app()
        db = _make_admin_db(
            waitlist_exists=True,
            profile_exists=True,
            profile_data={"display_name": "Jane Doe"},
        )

        mock_result = CrmSyncResult(email="user@example.com", action="updated")
        captured_args = {}

        async def _capture_sync(email, waitlist_data, profile_data):
            captured_args["profile_data"] = profile_data
            return mock_result

        with patch("app.db.get_firestore_db", return_value=db):
            with patch("app.services.espocrm_service.sync_contact", new=_capture_sync):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app_instance),
                    base_url="http://testserver",
                ) as client:
                    await client.post(
                        "/api/v1/admin/users/user@example.com/sync-crm",
                        cookies={"admin_session": _make_admin_cookie()},
                    )

        assert captured_args["profile_data"] == {"display_name": "Jane Doe"}

    async def test_profile_none_when_not_found(self):
        """Req 4.7: missing profile → None passed to sync_contact."""
        app_instance = _build_admin_app()
        db = _make_admin_db(waitlist_exists=True, profile_exists=False)

        mock_result = CrmSyncResult(email="user@example.com", action="created")
        captured_args = {}

        async def _capture_sync(email, waitlist_data, profile_data):
            captured_args["profile_data"] = profile_data
            return mock_result

        with patch("app.db.get_firestore_db", return_value=db):
            with patch("app.services.espocrm_service.sync_contact", new=_capture_sync):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app_instance),
                    base_url="http://testserver",
                ) as client:
                    await client.post(
                        "/api/v1/admin/users/user@example.com/sync-crm",
                        cookies={"admin_session": _make_admin_cookie()},
                    )

        assert captured_args["profile_data"] is None
