"""Integration tests for GET /api/v1/negotiation/stream/{session_id}."""

import pytest
from unittest.mock import AsyncMock, patch

from app.exceptions import SessionNotFoundError


class TestStreamNotFound:
    async def test_404_unknown_session(self, test_client, mock_db):
        mock_db.get_session_doc.side_effect = SessionNotFoundError("unknown-id")
        resp = await test_client.get(
            "/api/v1/negotiation/stream/unknown-id",
            params={"email": "user@test.com"},
        )
        assert resp.status_code == 404
        assert "unknown-id" in resp.json()["detail"]


class TestStreamRateLimited:
    async def test_429_limit_exceeded(self, test_client, mock_db, mock_tracker):
        mock_db.get_session_doc.return_value = {
            "session_id": "s1",
            "scenario_id": "sc1",
            "owner_email": "user@test.com",
        }
        mock_tracker.acquire = AsyncMock(return_value=False)
        resp = await test_client.get(
            "/api/v1/negotiation/stream/s1",
            params={"email": "user@test.com"},
        )
        assert resp.status_code == 429
        assert "limit" in resp.json()["detail"].lower()


class TestStreamForbidden:
    async def test_403_email_mismatch(self, test_client, mock_db):
        mock_db.get_session_doc.return_value = {
            "session_id": "s1",
            "scenario_id": "sc1",
            "owner_email": "owner@test.com",
        }
        with patch("app.routers.negotiation.settings") as mock_settings:
            mock_settings.RUN_MODE = "cloud"
            resp = await test_client.get(
                "/api/v1/negotiation/stream/s1",
                params={"email": "intruder@test.com"},
            )
        assert resp.status_code == 403


class TestStreamSuccess:
    async def test_successful_stream_returns_event_stream(
        self, test_client, mock_db, mock_tracker
    ):
        mock_db.get_session_doc.return_value = {
            "session_id": "s1",
            "scenario_id": "sc1",
            "owner_email": "user@test.com",
        }
        mock_tracker.acquire = AsyncMock(return_value=True)
        resp = await test_client.get(
            "/api/v1/negotiation/stream/s1",
            params={"email": "user@test.com"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        # Body should contain SSE-formatted events
        body = resp.text
        assert "data: " in body
        assert "\n\n" in body
