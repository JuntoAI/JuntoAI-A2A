"""Property-based tests for SQLiteSessionClient.delete_session.

# Feature: 320_scenario-management, Property 5: Session deletion removes the session

For any session stored in the SessionStore, after calling
``delete_session(session_id)``, calling ``get_session(session_id)`` should
raise ``SessionNotFoundError``.

**Validates: Requirements 6.2, 6.5**
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db.sqlite_client import SQLiteSessionClient
from app.exceptions import SessionNotFoundError

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_scenario_ids = st.sampled_from(["scenario-a", "scenario-b", "scenario-c"])
_owner_emails = st.sampled_from(["alice@test.com", "bob@test.com", "carol@test.com"])


@st.composite
def session_records(draw):
    """Generate a non-empty list of session dicts."""
    n = draw(st.integers(min_value=1, max_value=10))
    records = []
    for i in range(n):
        records.append(
            {
                "session_id": f"sess-{i}-{draw(st.uuids().map(lambda u: u.hex[:8]))}",
                "scenario_id": draw(_scenario_ids),
                "owner_email": draw(_owner_emails),
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
        )
    return records


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_raw(client: SQLiteSessionClient, record: dict) -> None:
    """Insert a session record directly into SQLite."""
    conn = await client._get_connection()
    try:
        ts = "2025-01-01T00:00:00+00:00"
        await conn.execute(
            "INSERT INTO negotiation_sessions (session_id, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (record["session_id"], json.dumps(record), ts, ts),
        )
        await conn.commit()
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Feature: 320_scenario-management
# Property 5: Session deletion removes the session
# **Validates: Requirements 6.2, 6.5**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(records=session_records())
async def test_session_deletion_removes_session(records: list[dict]):
    """After delete_session(session_id), get_session(session_id) raises
    SessionNotFoundError for every deleted session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "prop5.db")
        client = SQLiteSessionClient(db_path)

        # Insert all generated sessions
        for rec in records:
            await _insert_raw(client, rec)

        # Pick a random session to delete (use the first one — Hypothesis
        # already varies the list contents across examples)
        target = records[0]
        target_id = target["session_id"]

        # Verify it exists before deletion
        session = await client.get_session(target_id)
        assert session.session_id == target_id

        # Delete
        await client.delete_session(target_id)

        # get_session must now raise SessionNotFoundError
        with pytest.raises(SessionNotFoundError):
            await client.get_session(target_id)
