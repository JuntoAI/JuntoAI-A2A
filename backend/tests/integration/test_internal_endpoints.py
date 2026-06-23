"""Integration tests for the internal transcript export API.

Validates: bearer token auth in cloud mode, no auth in local mode,
bulk export with filters, single transcript retrieval.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Auth: local mode — no token required
# ---------------------------------------------------------------------------


class TestInternalAuthLocal:
    """In local mode, internal endpoints require no auth."""

    @patch("app.routers.internal.settings")
    async def test_no_auth_in_local_mode(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "local"
        mock_settings.INTERNAL_API_KEY = ""
        mock_db.list_sessions = AsyncMock(return_value=[])

        resp = await test_client.get("/api/v1/internal/transcripts")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["sessions"] == []


# ---------------------------------------------------------------------------
# Auth: cloud mode — bearer token enforced
# ---------------------------------------------------------------------------


class TestInternalAuthCloud:
    """In cloud mode, internal endpoints require valid bearer token."""

    @patch("app.routers.internal.settings")
    async def test_missing_token_returns_401(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "cloud"
        mock_settings.INTERNAL_API_KEY = "secret-key-123"
        mock_db.list_sessions = AsyncMock(return_value=[])

        resp = await test_client.get("/api/v1/internal/transcripts")

        assert resp.status_code == 401
        assert "Missing Authorization" in resp.json()["detail"]

    @patch("app.routers.internal.settings")
    async def test_wrong_token_returns_403(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "cloud"
        mock_settings.INTERNAL_API_KEY = "secret-key-123"
        mock_db.list_sessions = AsyncMock(return_value=[])

        resp = await test_client.get(
            "/api/v1/internal/transcripts",
            headers={"Authorization": "Bearer wrong-key"},
        )

        assert resp.status_code == 403
        assert "Invalid API key" in resp.json()["detail"]

    @patch("app.routers.internal.settings")
    async def test_valid_token_passes(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "cloud"
        mock_settings.INTERNAL_API_KEY = "secret-key-123"
        mock_db.list_sessions = AsyncMock(return_value=[])

        resp = await test_client.get(
            "/api/v1/internal/transcripts",
            headers={"Authorization": "Bearer secret-key-123"},
        )

        assert resp.status_code == 200

    @patch("app.routers.internal.settings")
    async def test_no_key_configured_returns_503(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "cloud"
        mock_settings.INTERNAL_API_KEY = ""
        mock_db.list_sessions = AsyncMock(return_value=[])

        resp = await test_client.get("/api/v1/internal/transcripts")

        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /internal/transcripts — bulk export
# ---------------------------------------------------------------------------


class TestListTranscripts:
    """GET /api/v1/internal/transcripts — bulk export with filters."""

    @patch("app.routers.internal.settings")
    async def test_returns_all_sessions_unfiltered(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "local"
        mock_settings.INTERNAL_API_KEY = ""
        mock_db.list_sessions = AsyncMock(return_value=[
            {"session_id": "s1", "scenario_id": "talent-war", "deal_status": "Agreed"},
            {"session_id": "s2", "scenario_id": "mna-buyout", "deal_status": "Failed"},
        ])

        resp = await test_client.get("/api/v1/internal/transcripts")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert len(body["sessions"]) == 2

    @patch("app.routers.internal.settings")
    async def test_filter_by_scenario_id(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "local"
        mock_settings.INTERNAL_API_KEY = ""
        mock_db.list_sessions = AsyncMock(return_value=[
            {"session_id": "s1", "scenario_id": "talent-war", "deal_status": "Agreed"},
            {"session_id": "s2", "scenario_id": "mna-buyout", "deal_status": "Failed"},
            {"session_id": "s3", "scenario_id": "talent-war", "deal_status": "Blocked"},
        ])

        resp = await test_client.get(
            "/api/v1/internal/transcripts?scenario_id=talent-war"
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert all(s["scenario_id"] == "talent-war" for s in body["sessions"])

    @patch("app.routers.internal.settings")
    async def test_filter_by_deal_status(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "local"
        mock_settings.INTERNAL_API_KEY = ""
        mock_db.list_sessions = AsyncMock(return_value=[
            {"session_id": "s1", "scenario_id": "talent-war", "deal_status": "Agreed"},
            {"session_id": "s2", "scenario_id": "mna-buyout", "deal_status": "Failed"},
        ])

        resp = await test_client.get(
            "/api/v1/internal/transcripts?deal_status=Agreed"
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["sessions"][0]["deal_status"] == "Agreed"

    @patch("app.routers.internal.settings")
    async def test_limit_caps_results(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "local"
        mock_settings.INTERNAL_API_KEY = ""
        mock_db.list_sessions = AsyncMock(return_value=[
            {"session_id": f"s{i}", "scenario_id": "x", "deal_status": "Agreed"}
            for i in range(10)
        ])

        resp = await test_client.get("/api/v1/internal/transcripts?limit=3")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 3

    @patch("app.routers.internal.settings")
    async def test_response_includes_filter_metadata(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "local"
        mock_settings.INTERNAL_API_KEY = ""
        mock_db.list_sessions = AsyncMock(return_value=[])

        resp = await test_client.get(
            "/api/v1/internal/transcripts?scenario_id=test&deal_status=Failed&days=7&limit=10"
        )

        body = resp.json()
        assert body["filters"]["scenario_id"] == "test"
        assert body["filters"]["deal_status"] == "Failed"
        assert body["filters"]["days"] == 7
        assert body["filters"]["limit"] == 10


# ---------------------------------------------------------------------------
# GET /internal/transcripts/{session_id} — single transcript
# ---------------------------------------------------------------------------


class TestGetTranscript:
    """GET /api/v1/internal/transcripts/{session_id} — single full transcript."""

    @patch("app.routers.internal.settings")
    async def test_returns_full_session_document(
        self, mock_settings, test_client, mock_db
    ):
        mock_settings.RUN_MODE = "local"
        mock_settings.INTERNAL_API_KEY = ""
        mock_db.get_session_doc = AsyncMock(return_value={
            "session_id": "abc-123",
            "scenario_id": "talent-war",
            "deal_status": "Agreed",
            "history": [
                {"role": "Buyer", "content": {"inner_thought": "secret", "public_message": "Hi"}},
            ],
            "agent_calls": [{"model_id": "gemini", "input_tokens": 100}],
            "evaluation": {"overall_score": 8},
        })

        resp = await test_client.get("/api/v1/internal/transcripts/abc-123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "abc-123"
        assert body["history"][0]["content"]["inner_thought"] == "secret"
        assert body["evaluation"]["overall_score"] == 8

    @patch("app.routers.internal.settings")
    async def test_not_found_returns_404(
        self, mock_settings, test_client, mock_db
    ):
        from app.exceptions import SessionNotFoundError

        mock_settings.RUN_MODE = "local"
        mock_settings.INTERNAL_API_KEY = ""
        mock_db.get_session_doc = AsyncMock(
            side_effect=SessionNotFoundError("nonexistent")
        )

        resp = await test_client.get("/api/v1/internal/transcripts/nonexistent")

        assert resp.status_code == 404
