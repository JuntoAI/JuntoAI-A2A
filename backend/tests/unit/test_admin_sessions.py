"""Unit tests for session metadata and user status checks in negotiation router.

Validates: Requirements 4.7, 4.10, 8.1, 8.2, 8.3
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.db import get_profile_client, get_session_store
from app.main import app
from app.scenarios.models import ArenaScenario
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry

# ---------------------------------------------------------------------------
# Shared scenario config
# ---------------------------------------------------------------------------

_VALID_SCENARIO_DICT = {
    "id": "test-scenario",
    "name": "Test Scenario",
    "description": "A test scenario",
    "agents": [
        {
            "role": "Buyer", "name": "Alice", "type": "negotiator",
            "persona_prompt": "You are a buyer.", "goals": ["Buy low"],
            "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
            "tone": "assertive", "output_fields": ["offer"],
            "model_id": "gemini-3-flash-preview",
        },
        {
            "role": "Seller", "name": "Bob", "type": "negotiator",
            "persona_prompt": "You are a seller.", "goals": ["Sell high"],
            "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
            "tone": "firm", "output_fields": ["offer"],
            "model_id": "gemini-3-flash-preview",
        },
    ],
    "toggles": [{
        "id": "toggle_1", "label": "Secret info",
        "target_agent_role": "Buyer",
        "hidden_context_payload": {"secret": "value"},
    }],
    "negotiation_params": {
        "max_turns": 10, "agreement_threshold": 1000.0,
        "turn_order": ["Buyer", "Seller"],
    },
    "outcome_receipt": {
        "equivalent_human_time": "~2 weeks",
        "process_label": "Acquisition",
    },
}

_SCENARIO = ArenaScenario(**_VALID_SCENARIO_DICT)


# ---------------------------------------------------------------------------
# Mock builders
# ---------------------------------------------------------------------------


def _build_mock_registry() -> MagicMock:
    registry = MagicMock(spec=ScenarioRegistry)
    registry.get_scenario.return_value = _SCENARIO
    registry._scenarios = {"test-scenario": _SCENARIO}
    return registry


def _build_mock_db():
    """Build a mock DB that captures persisted data via Firestore-style set()."""
    db = MagicMock()
    stored_data: dict = {}

    async def _capture_create(state):
        stored_data.update(state.model_dump())

    db.create_session = AsyncMock(side_effect=_capture_create)

    async def _capture_update(session_id, updates):
        stored_data.update(updates)

    db.update_session = AsyncMock(side_effect=_capture_update)

    # Cloud mode: doc_ref.set() captures persisted data
    doc_ref = MagicMock()
    doc_ref.set = AsyncMock(side_effect=lambda data: stored_data.update(data))
    db._collection = MagicMock()
    db._collection.document = MagicMock(return_value=doc_ref)

    return db, stored_data


def _build_mock_profile_client(user_status: str | None = "active"):
    """Build a mock ProfileClient with configurable user_status on waitlist doc.

    Args:
        user_status: The user_status value in the waitlist doc.
                     None means the field is absent (backward compat).
    """
    pc = MagicMock()
    pc.get_profile = AsyncMock(return_value=None)

    waitlist_data: dict = {"token_balance": 100}
    if user_status is not None:
        waitlist_data["user_status"] = user_status

    waitlist_doc = MagicMock()
    waitlist_doc.exists = True
    waitlist_doc.to_dict.return_value = waitlist_data

    waitlist_ref = MagicMock()
    waitlist_ref.get = AsyncMock(return_value=waitlist_doc)

    pc._db = MagicMock()
    pc._db.collection.return_value = MagicMock()
    pc._db.collection.return_value.document.return_value = waitlist_ref

    return pc


async def _post_start(
    payload: dict,
    user_status: str | None = "active",
) -> tuple[httpx.Response, dict]:
    """POST /negotiation/start with mocked deps in cloud mode."""
    mock_registry = _build_mock_registry()
    mock_db, stored_data = _build_mock_db()
    mock_pc = _build_mock_profile_client(user_status=user_status)

    app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
    app.dependency_overrides[get_session_store] = lambda: mock_db
    app.dependency_overrides[get_profile_client] = lambda: mock_pc

    try:
        with patch("app.routers.negotiation.settings") as mock_settings:
            mock_settings.RUN_MODE = "cloud"
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.post("/api/v1/negotiation/start", json=payload)
        return resp, stored_data
    finally:
        app.dependency_overrides.pop(get_scenario_registry, None)
        app.dependency_overrides.pop(get_session_store, None)
        app.dependency_overrides.pop(get_profile_client, None)


_DEFAULT_PAYLOAD = {
    "email": "test@example.com",
    "scenario_id": "test-scenario",
}


# ---------------------------------------------------------------------------
# Tests: created_at metadata (Req 8.1)
# ---------------------------------------------------------------------------


class TestCreatedAtMetadata:
    """Verify created_at is set on start_negotiation() in cloud mode."""

    @pytest.mark.asyncio
    async def test_created_at_set_on_start(self):
        """Session document should contain a created_at ISO 8601 UTC timestamp."""
        resp, stored = await _post_start(_DEFAULT_PAYLOAD)

        assert resp.status_code == 200
        assert "created_at" in stored

        # Validate it's a parseable ISO 8601 timestamp
        created_at = datetime.fromisoformat(stored["created_at"])
        assert created_at.tzinfo is not None  # timezone-aware
        # Should be very recent (within last 10 seconds)
        delta = (datetime.now(timezone.utc) - created_at).total_seconds()
        assert 0 <= delta < 10

    @pytest.mark.asyncio
    async def test_created_at_is_utc(self):
        """created_at timestamp should be in UTC."""
        resp, stored = await _post_start(_DEFAULT_PAYLOAD)

        assert resp.status_code == 200
        created_at = datetime.fromisoformat(stored["created_at"])
        assert created_at.utcoffset().total_seconds() == 0


# ---------------------------------------------------------------------------
# Tests: User status check (Req 4.7, 4.10)
# ---------------------------------------------------------------------------


class TestUserStatusCheck:
    """Verify user_status gating in start_negotiation() (cloud mode)."""

    @pytest.mark.asyncio
    async def test_suspended_user_returns_403(self):
        """user_status='suspended' → 403 with 'Account suspended'."""
        resp, _ = await _post_start(_DEFAULT_PAYLOAD, user_status="suspended")

        assert resp.status_code == 403
        assert resp.json()["detail"] == "Account suspended"

    @pytest.mark.asyncio
    async def test_banned_user_returns_403(self):
        """user_status='banned' → 403 with 'Account banned'."""
        resp, _ = await _post_start(_DEFAULT_PAYLOAD, user_status="banned")

        assert resp.status_code == 403
        assert resp.json()["detail"] == "Account banned"

    @pytest.mark.asyncio
    async def test_active_user_proceeds(self):
        """user_status='active' → negotiation proceeds (200)."""
        resp, stored = await _post_start(_DEFAULT_PAYLOAD, user_status="active")

        assert resp.status_code == 200
        assert "session_id" in resp.json()

    @pytest.mark.asyncio
    async def test_missing_user_status_proceeds(self):
        """Missing user_status field → treated as 'active', proceeds (200).

        Backward compatibility: existing waitlist docs without user_status
        should not be blocked.
        """
        resp, stored = await _post_start(_DEFAULT_PAYLOAD, user_status=None)

        assert resp.status_code == 200
        assert "session_id" in resp.json()
