"""Integration tests for GET /api/v1/negotiation/history.

Uses a real SQLiteSessionClient (tmp file) instead of mocks to validate
the full request → DB → grouping → response pipeline.

Requirements: 1.1, 1.7, 1.8
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx
import pytest

from app.db import get_session_store
from app.db.sqlite_client import SQLiteSessionClient
from app.main import app
from app.scenarios.models import ArenaScenario
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
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


def _build_mock_registry() -> MagicMock:
    scenario = ArenaScenario(**_VALID_SCENARIO_DICT)
    registry = MagicMock(spec=ScenarioRegistry)
    registry.get_scenario.return_value = scenario
    return registry


async def _insert_raw_session(
    client: SQLiteSessionClient,
    session_id: str,
    owner_email: str,
    created_at: str,
    deal_status: str = "Agreed",
    total_tokens_used: int = 1000,
    scenario_id: str = "test-scenario",
    completed_at: str | None = None,
) -> None:
    """Insert a raw session row with explicit created_at and owner_email in JSON data."""
    data = {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "owner_email": owner_email,
        "deal_status": deal_status,
        "total_tokens_used": total_tokens_used,
        "created_at": created_at,
        "completed_at": completed_at,
        "turn_count": 0,
        "max_turns": 10,
        "current_speaker": "Buyer",
        "current_offer": 0.0,
        "history": [],
        "warning_count": 0,
        "hidden_context": {},
        "agreement_threshold": 1000.0,
        "active_toggles": [],
        "turn_order": ["Buyer", "Seller"],
        "turn_order_index": 0,
        "agent_states": {},
    }
    conn = await client._get_connection()
    try:
        await conn.execute(
            "INSERT INTO negotiation_sessions (session_id, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, json.dumps(data), created_at, created_at),
        )
        await conn.commit()
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_client(tmp_path):
    """Real SQLiteSessionClient backed by a temp file."""
    return SQLiteSessionClient(str(tmp_path / "integration_test.db"))


@pytest.fixture()
def mock_registry():
    return _build_mock_registry()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHistoryEndpointHappyPath:
    """GET /api/v1/negotiation/history — happy path with real SQLite."""

    async def test_returns_grouped_sessions(self, sqlite_client, mock_registry):
        """Sessions are returned grouped by UTC day with correct structure."""
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        await _insert_raw_session(sqlite_client, "s1", "user@test.com", today_str, total_tokens_used=3000)
        await _insert_raw_session(sqlite_client, "s2", "user@test.com", today_str, total_tokens_used=1500)
        await _insert_raw_session(sqlite_client, "s3", "user@test.com", yesterday_str, total_tokens_used=7000)

        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": "user@test.com", "days": 7},
                )

            assert resp.status_code == 200
            body = resp.json()

            # Structure checks
            assert body["period_days"] == 7
            assert len(body["days"]) == 2

            # Groups sorted descending by date
            assert body["days"][0]["date"] > body["days"][1]["date"]

            # Today group has 2 sessions, yesterday has 1
            today_group = body["days"][0]
            yesterday_group = body["days"][1]
            assert len(today_group["sessions"]) == 2
            assert len(yesterday_group["sessions"]) == 1

            # Token costs computed correctly (3000 → 3, 1500 → 2)
            assert today_group["total_token_cost"] == 3 + 2
            assert yesterday_group["total_token_cost"] == 7

            # Top-level total
            assert body["total_token_cost"] == 5 + 7

            # Session fields present and correct
            s = today_group["sessions"][0]
            assert s["scenario_name"] == "Test Scenario"
            assert s["deal_status"] == "Agreed"
            assert "session_id" in s
            assert "token_cost" in s
            assert "created_at" in s
        finally:
            app.dependency_overrides.clear()

    async def test_filters_non_terminal_sessions(self, sqlite_client, mock_registry):
        """Only terminal sessions (Agreed, Blocked, Failed) appear in results."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        await _insert_raw_session(sqlite_client, "s-agreed", "user@test.com", now, deal_status="Agreed")
        await _insert_raw_session(sqlite_client, "s-blocked", "user@test.com", now, deal_status="Blocked")
        await _insert_raw_session(sqlite_client, "s-failed", "user@test.com", now, deal_status="Failed")
        await _insert_raw_session(sqlite_client, "s-negotiating", "user@test.com", now, deal_status="Negotiating")
        await _insert_raw_session(sqlite_client, "s-confirming", "user@test.com", now, deal_status="Confirming")

        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": "user@test.com", "days": 7},
                )

            assert resp.status_code == 200
            all_sessions = [s for g in resp.json()["days"] for s in g["sessions"]]
            session_ids = {s["session_id"] for s in all_sessions}
            assert session_ids == {"s-agreed", "s-blocked", "s-failed"}
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Validation errors (422)
# ---------------------------------------------------------------------------


class TestHistoryEndpointValidation:
    """GET /api/v1/negotiation/history — validation errors."""

    async def test_missing_email_returns_422(self, sqlite_client, mock_registry):
        """Missing email parameter returns 422."""
        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get("/api/v1/negotiation/history")
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_empty_email_returns_422(self, sqlite_client, mock_registry):
        """Empty email string returns 422."""
        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": ""},
                )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_whitespace_email_returns_422(self, sqlite_client, mock_registry):
        """Whitespace-only email returns 422."""
        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": "   "},
                )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Empty response
# ---------------------------------------------------------------------------


class TestHistoryEndpointEmptyResponse:
    """GET /api/v1/negotiation/history — empty results."""

    async def test_no_sessions_returns_empty_days(self, sqlite_client, mock_registry):
        """No sessions returns empty days list with zero total."""
        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": "nobody@test.com", "days": 7},
                )

            assert resp.status_code == 200
            body = resp.json()
            assert body["days"] == []
            assert body["total_token_cost"] == 0
            assert body["period_days"] == 7
        finally:
            app.dependency_overrides.clear()

    async def test_only_non_terminal_sessions_returns_empty(self, sqlite_client, mock_registry):
        """Sessions with non-terminal status are filtered out → empty response."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        await _insert_raw_session(sqlite_client, "s1", "user@test.com", now, deal_status="Negotiating")
        await _insert_raw_session(sqlite_client, "s2", "user@test.com", now, deal_status="Confirming")

        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": "user@test.com"},
                )

            assert resp.status_code == 200
            assert resp.json()["days"] == []
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------


class TestHistoryEndpointDateFiltering:
    """GET /api/v1/negotiation/history — date filtering with real SQLite."""

    async def test_old_sessions_excluded_by_days_param(self, sqlite_client, mock_registry):
        """Sessions older than the days window are excluded by the SQLite query."""
        now = datetime.now(timezone.utc)
        recent = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        old = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        await _insert_raw_session(sqlite_client, "s-recent", "user@test.com", recent)
        await _insert_raw_session(sqlite_client, "s-old", "user@test.com", old)

        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": "user@test.com", "days": 7},
                )

            assert resp.status_code == 200
            all_ids = [s["session_id"] for g in resp.json()["days"] for s in g["sessions"]]
            assert "s-recent" in all_ids
            assert "s-old" not in all_ids
        finally:
            app.dependency_overrides.clear()

    async def test_days_defaults_to_7(self, sqlite_client, mock_registry):
        """When days is omitted, defaults to 7."""
        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": "user@test.com"},
                )

            assert resp.status_code == 200
            assert resp.json()["period_days"] == 7
        finally:
            app.dependency_overrides.clear()

    async def test_wider_window_includes_more_sessions(self, sqlite_client, mock_registry):
        """Increasing days param includes sessions that were previously excluded."""
        now = datetime.now(timezone.utc)
        recent = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        two_weeks_ago = (now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        await _insert_raw_session(sqlite_client, "s-recent", "user@test.com", recent)
        await _insert_raw_session(sqlite_client, "s-2wk", "user@test.com", two_weeks_ago)

        app.dependency_overrides[get_session_store] = lambda: sqlite_client
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                # 7 days — should only get recent
                resp7 = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": "user@test.com", "days": 7},
                )
                ids_7 = [s["session_id"] for g in resp7.json()["days"] for s in g["sessions"]]

                # 30 days — should get both
                resp30 = await client.get(
                    "/api/v1/negotiation/history",
                    params={"email": "user@test.com", "days": 30},
                )
                ids_30 = [s["session_id"] for g in resp30.json()["days"] for s in g["sessions"]]

            assert ids_7 == ["s-recent"]
            assert set(ids_30) == {"s-recent", "s-2wk"}
        finally:
            app.dependency_overrides.clear()
