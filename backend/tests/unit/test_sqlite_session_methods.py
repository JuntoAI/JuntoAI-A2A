"""Unit tests for SQLiteSessionClient.list_sessions_by_scenario and delete_session.

Requirements: 6.1, 6.2, 6.4, 6.5
"""

from __future__ import annotations

import json

import pytest

from app.db.sqlite_client import SQLiteSessionClient
from app.exceptions import SessionNotFoundError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_raw(
    client: SQLiteSessionClient,
    session_id: str,
    scenario_id: str,
    owner_email: str,
) -> None:
    """Insert a minimal session row with scenario_id and owner_email in JSON data."""
    data = {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "owner_email": owner_email,
        "turn_count": 0,
        "max_turns": 10,
        "current_speaker": "Buyer",
        "deal_status": "Negotiating",
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
        ts = "2025-01-01T00:00:00+00:00"
        await conn.execute(
            "INSERT INTO negotiation_sessions (session_id, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, json.dumps(data), ts, ts),
        )
        await conn.commit()
    finally:
        await conn.close()


@pytest.fixture()
def sqlite_client(tmp_path):
    """SQLiteSessionClient backed by a temp file."""
    return SQLiteSessionClient(str(tmp_path / "test.db"))


# ---------------------------------------------------------------------------
# list_sessions_by_scenario
# ---------------------------------------------------------------------------


class TestListSessionsByScenario:
    """Tests for list_sessions_by_scenario (Requirements 6.1, 6.4)."""

    async def test_zero_matching_sessions(self, sqlite_client):
        """Returns empty list when no sessions exist at all."""
        results = await sqlite_client.list_sessions_by_scenario("sc-1", "alice@test.com")
        assert results == []

    async def test_zero_matching_among_existing(self, sqlite_client):
        """Returns empty list when sessions exist but none match the query."""
        await _insert_raw(sqlite_client, "s1", "sc-other", "bob@test.com")
        results = await sqlite_client.list_sessions_by_scenario("sc-1", "alice@test.com")
        assert results == []

    async def test_one_matching_session(self, sqlite_client):
        """Returns exactly one session when only one matches."""
        await _insert_raw(sqlite_client, "s1", "sc-1", "alice@test.com")
        results = await sqlite_client.list_sessions_by_scenario("sc-1", "alice@test.com")
        assert len(results) == 1
        assert results[0]["session_id"] == "s1"
        assert results[0]["scenario_id"] == "sc-1"
        assert results[0]["owner_email"] == "alice@test.com"

    async def test_n_matching_with_mixed_data(self, sqlite_client):
        """Returns only sessions matching both scenario_id AND owner_email."""
        # Matching: same scenario + same email
        await _insert_raw(sqlite_client, "match-1", "sc-1", "alice@test.com")
        await _insert_raw(sqlite_client, "match-2", "sc-1", "alice@test.com")
        # Same scenario, different email
        await _insert_raw(sqlite_client, "diff-email", "sc-1", "bob@test.com")
        # Different scenario, same email
        await _insert_raw(sqlite_client, "diff-scenario", "sc-2", "alice@test.com")
        # Different both
        await _insert_raw(sqlite_client, "diff-both", "sc-2", "bob@test.com")

        results = await sqlite_client.list_sessions_by_scenario("sc-1", "alice@test.com")
        result_ids = {r["session_id"] for r in results}

        assert result_ids == {"match-1", "match-2"}

    async def test_all_returned_docs_have_correct_fields(self, sqlite_client):
        """Every returned doc has the queried scenario_id and owner_email."""
        await _insert_raw(sqlite_client, "s1", "sc-x", "user@test.com")
        await _insert_raw(sqlite_client, "s2", "sc-x", "user@test.com")

        results = await sqlite_client.list_sessions_by_scenario("sc-x", "user@test.com")
        for doc in results:
            assert doc["scenario_id"] == "sc-x"
            assert doc["owner_email"] == "user@test.com"


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------


class TestDeleteSession:
    """Tests for delete_session (Requirements 6.2, 6.5)."""

    async def test_delete_existing_session(self, sqlite_client):
        """Deleting an existing session removes it — get_session raises SessionNotFoundError."""
        await _insert_raw(sqlite_client, "del-1", "sc-1", "alice@test.com")

        # Confirm it exists
        session = await sqlite_client.get_session("del-1")
        assert session.session_id == "del-1"

        # Delete
        await sqlite_client.delete_session("del-1")

        # Confirm it's gone
        with pytest.raises(SessionNotFoundError):
            await sqlite_client.get_session("del-1")

    async def test_delete_nonexistent_session_is_noop(self, sqlite_client):
        """Deleting a session_id that doesn't exist should not raise."""
        # Should complete without error
        await sqlite_client.delete_session("does-not-exist")

    async def test_delete_does_not_affect_other_sessions(self, sqlite_client):
        """Deleting one session leaves other sessions intact."""
        await _insert_raw(sqlite_client, "keep-1", "sc-1", "alice@test.com")
        await _insert_raw(sqlite_client, "remove-1", "sc-1", "alice@test.com")
        await _insert_raw(sqlite_client, "keep-2", "sc-2", "bob@test.com")

        await sqlite_client.delete_session("remove-1")

        # Remaining sessions still accessible
        s1 = await sqlite_client.get_session("keep-1")
        assert s1.session_id == "keep-1"
        s2 = await sqlite_client.get_session("keep-2")
        assert s2.session_id == "keep-2"

        # Deleted one is gone
        with pytest.raises(SessionNotFoundError):
            await sqlite_client.get_session("remove-1")
