"""Integration tests for POST /api/v1/negotiation/start.

Validates: Requirements 3.1, 3.2
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.scenarios.exceptions import ScenarioNotFoundError


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _force_local_mode():
    """Force RUN_MODE=local so tests use the SessionStore protocol path."""
    with patch("app.routers.negotiation.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        yield mock_settings


class TestStartNegotiationSuccess:
    """POST /api/v1/negotiation/start — happy path."""

    async def test_valid_payload_returns_200_with_session_id(
        self, test_client, negotiation_start_payload
    ):
        """Valid payload returns 200 with session_id and tokens_remaining."""
        resp = await test_client.post(
            "/api/v1/negotiation/start",
            json=negotiation_start_payload,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "session_id" in body
        assert isinstance(body["session_id"], str)
        assert len(body["session_id"]) > 0
        assert "tokens_remaining" in body
        assert isinstance(body["tokens_remaining"], int)
        assert "max_turns" in body

    async def test_tokens_remaining_is_999_in_local_mode(
        self, test_client, negotiation_start_payload
    ):
        """Local mode returns 999 tokens (unlimited)."""
        resp = await test_client.post(
            "/api/v1/negotiation/start",
            json=negotiation_start_payload,
        )

        assert resp.status_code == 200
        assert resp.json()["tokens_remaining"] == 999


class TestStartNegotiationErrors:
    """POST /api/v1/negotiation/start — error paths."""

    async def test_invalid_scenario_id_returns_404(
        self, test_client, mock_registry
    ):
        """Unknown scenario_id returns 404."""
        mock_registry.get_scenario.side_effect = ScenarioNotFoundError(
            "nonexistent-scenario"
        )

        resp = await test_client.post(
            "/api/v1/negotiation/start",
            json={
                "email": "test@example.com",
                "scenario_id": "nonexistent-scenario",
                "active_toggles": [],
            },
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_missing_email_returns_422(self, test_client):
        """Missing required email field returns 422."""
        resp = await test_client.post(
            "/api/v1/negotiation/start",
            json={
                "scenario_id": "test-scenario",
                "active_toggles": [],
            },
        )

        assert resp.status_code == 422

    async def test_empty_email_returns_422(self, test_client):
        """Empty email string returns 422 (min_length=1)."""
        resp = await test_client.post(
            "/api/v1/negotiation/start",
            json={
                "email": "",
                "scenario_id": "test-scenario",
                "active_toggles": [],
            },
        )

        assert resp.status_code == 422

    async def test_missing_scenario_id_returns_422(self, test_client):
        """Missing required scenario_id field returns 422."""
        resp = await test_client.post(
            "/api/v1/negotiation/start",
            json={
                "email": "test@example.com",
                "active_toggles": [],
            },
        )

        assert resp.status_code == 422


class TestStartNegotiationCreatedAt:
    """POST /api/v1/negotiation/start — session metadata."""

    async def test_created_at_is_set_on_session(
        self, test_client, mock_db, negotiation_start_payload
    ):
        """created_at is set on the session document after start."""
        resp = await test_client.post(
            "/api/v1/negotiation/start",
            json=negotiation_start_payload,
        )

        assert resp.status_code == 200

        # In local mode, created_at is set via update_session
        mock_db.update_session.assert_awaited_once()
        call_args = mock_db.update_session.call_args
        session_id = call_args[0][0]
        updates = call_args[0][1]

        assert session_id == resp.json()["session_id"]
        assert "created_at" in updates
        assert isinstance(updates["created_at"], str)
        # ISO 8601 format check
        assert "T" in updates["created_at"]
