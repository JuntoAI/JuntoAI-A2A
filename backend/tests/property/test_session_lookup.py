"""Property-based tests for SQLiteSessionClient.list_sessions_by_scenario.

# Feature: 320_scenario-management, Property 1: Session lookup returns exactly the matching sessions

For any set of sessions with varying ``scenario_id`` and ``owner_email``
values stored in the SessionStore, calling
``list_sessions_by_scenario(target_scenario_id, target_email)`` should return
exactly those sessions where both ``scenario_id == target_scenario_id`` and
``owner_email == target_email``, and no others.

**Validates: Requirements 1.1, 6.1, 6.3, 6.4**
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db.sqlite_client import SQLiteSessionClient

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Small pool of scenario_ids and emails to ensure overlaps in generated data
_scenario_ids = st.sampled_from(["scenario-a", "scenario-b", "scenario-c"])
_owner_emails = st.sampled_from(["alice@test.com", "bob@test.com", "carol@test.com"])


@st.composite
def session_records(draw):
    """Generate a list of session dicts with varying scenario_id and owner_email."""
    n = draw(st.integers(min_value=0, max_value=15))
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
    """Insert a session record directly into SQLite with owner_email in JSON data."""
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
# Property 1: Session lookup returns exactly the matching sessions
# **Validates: Requirements 1.1, 6.1, 6.3, 6.4**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    records=session_records(),
    target_scenario=_scenario_ids,
    target_email=_owner_emails,
)
async def test_session_lookup_returns_exact_matches(
    records: list[dict],
    target_scenario: str,
    target_email: str,
):
    """list_sessions_by_scenario returns exactly the sessions matching both
    scenario_id and owner_email, and no others."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "prop1.db")
        client = SQLiteSessionClient(db_path)

        # Insert all generated sessions
        for rec in records:
            await _insert_raw(client, rec)

        # Query
        results = await client.list_sessions_by_scenario(target_scenario, target_email)

        # Compute expected set
        expected_ids = {
            r["session_id"]
            for r in records
            if r["scenario_id"] == target_scenario and r["owner_email"] == target_email
        }
        actual_ids = {r["session_id"] for r in results}

        # Exact match — no missing, no extra
        assert actual_ids == expected_ids, (
            f"Mismatch for scenario={target_scenario!r}, email={target_email!r}.\n"
            f"  Expected: {expected_ids}\n"
            f"  Actual:   {actual_ids}"
        )

        # Every returned doc has correct fields
        for doc in results:
            assert doc["scenario_id"] == target_scenario
            assert doc["owner_email"] == target_email
