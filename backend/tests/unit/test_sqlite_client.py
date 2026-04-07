"""Unit tests for SQLiteSessionClient — in-memory SQLite session persistence."""

import pytest

from app.db.sqlite_client import SQLiteSessionClient
from app.exceptions import SessionNotFoundError
from app.models.negotiation import NegotiationStateModel

pytestmark = pytest.mark.unit


def _make_state(**overrides) -> NegotiationStateModel:
    """Build a minimal valid NegotiationStateModel with sensible defaults."""
    defaults = {
        "session_id": "sess-001",
        "scenario_id": "test-scenario",
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
    defaults.update(overrides)
    return NegotiationStateModel(**defaults)


@pytest.fixture()
def sqlite_client(tmp_path):
    """Provide a SQLiteSessionClient backed by a temp file (not :memory:)
    so the table persists across the open/close cycles the client performs."""
    db_path = str(tmp_path / "test.db")
    return SQLiteSessionClient(db_path)


# --- create_session → get_session round-trip ---


async def test_create_get_round_trip_preserves_key_fields(sqlite_client):
    state = _make_state(
        session_id="rt-001",
        scenario_id="m-and-a",
        turn_count=3,
        max_turns=15,
        deal_status="Negotiating",
        current_offer=500_000.0,
        current_speaker="Seller",
    )

    await sqlite_client.create_session(state)
    retrieved = await sqlite_client.get_session("rt-001")

    assert retrieved.session_id == state.session_id
    assert retrieved.scenario_id == state.scenario_id
    assert retrieved.turn_count == state.turn_count
    assert retrieved.max_turns == state.max_turns
    assert retrieved.deal_status == state.deal_status
    assert retrieved.current_offer == state.current_offer
    assert retrieved.current_speaker == state.current_speaker
    assert retrieved.turn_order == state.turn_order
    assert retrieved.history == state.history


# --- get_session_doc returns dict with expected keys ---


async def test_get_session_doc_returns_dict_with_expected_keys(sqlite_client):
    state = _make_state(session_id="doc-001", turn_count=5, current_offer=750.0)

    await sqlite_client.create_session(state)
    doc = await sqlite_client.get_session_doc("doc-001")

    assert isinstance(doc, dict)
    for key in ("session_id", "scenario_id", "turn_count", "max_turns",
                "deal_status", "current_offer", "history", "warning_count"):
        assert key in doc, f"Missing key: {key}"
    assert doc["session_id"] == "doc-001"
    assert doc["turn_count"] == 5
    assert doc["current_offer"] == 750.0


# --- update_session modifies fields correctly ---


async def test_update_session_modifies_fields(sqlite_client):
    state = _make_state(session_id="upd-001", turn_count=0, deal_status="Negotiating")

    await sqlite_client.create_session(state)
    await sqlite_client.update_session("upd-001", {"turn_count": 4, "deal_status": "Agreed"})

    updated = await sqlite_client.get_session("upd-001")
    assert updated.turn_count == 4
    assert updated.deal_status == "Agreed"
    # Unmodified fields stay the same
    assert updated.scenario_id == state.scenario_id
    assert updated.max_turns == state.max_turns


# --- get_session for non-existent ID raises SessionNotFoundError ---


async def test_get_session_nonexistent_raises_session_not_found(sqlite_client):
    with pytest.raises(SessionNotFoundError):
        await sqlite_client.get_session("does-not-exist")


# --- concurrent session creation (two different session_ids) ---


async def test_concurrent_session_creation(sqlite_client):
    state_a = _make_state(session_id="concurrent-a", scenario_id="scenario-1")
    state_b = _make_state(session_id="concurrent-b", scenario_id="scenario-2")

    await sqlite_client.create_session(state_a)
    await sqlite_client.create_session(state_b)

    retrieved_a = await sqlite_client.get_session("concurrent-a")
    retrieved_b = await sqlite_client.get_session("concurrent-b")

    assert retrieved_a.session_id == "concurrent-a"
    assert retrieved_a.scenario_id == "scenario-1"
    assert retrieved_b.session_id == "concurrent-b"
    assert retrieved_b.scenario_id == "scenario-2"


# --- list_sessions_by_owner ---

import json
from datetime import datetime, timezone, timedelta


async def _insert_raw_session(
    client: SQLiteSessionClient,
    session_id: str,
    owner_email: str,
    created_at: str,
    deal_status: str = "Agreed",
    total_tokens_used: int = 1000,
) -> None:
    """Insert a raw session row with explicit created_at and owner_email in JSON data."""
    data = {
        "session_id": session_id,
        "scenario_id": "test-scenario",
        "owner_email": owner_email,
        "deal_status": deal_status,
        "total_tokens_used": total_tokens_used,
        "created_at": created_at,
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


async def test_list_sessions_by_owner_filters_by_owner(sqlite_client):
    """Only sessions belonging to the requested owner are returned."""
    now = datetime.now(timezone.utc)
    ts = now.isoformat()

    await _insert_raw_session(sqlite_client, "s1", "alice@test.com", ts)
    await _insert_raw_session(sqlite_client, "s2", "bob@test.com", ts)
    await _insert_raw_session(sqlite_client, "s3", "alice@test.com", ts)

    results = await sqlite_client.list_sessions_by_owner("alice@test.com", since=ts)
    ids = [r["session_id"] for r in results]

    assert len(results) == 2
    assert "s1" in ids
    assert "s3" in ids
    assert "s2" not in ids


async def test_list_sessions_by_owner_filters_by_date(sqlite_client):
    """Only sessions at or after the 'since' cutoff are returned."""
    old = "2024-01-01T00:00:00+00:00"
    recent = "2025-06-01T00:00:00+00:00"
    cutoff = "2025-01-01T00:00:00+00:00"

    await _insert_raw_session(sqlite_client, "old-1", "alice@test.com", old)
    await _insert_raw_session(sqlite_client, "new-1", "alice@test.com", recent)

    results = await sqlite_client.list_sessions_by_owner("alice@test.com", since=cutoff)
    ids = [r["session_id"] for r in results]

    assert ids == ["new-1"]


async def test_list_sessions_by_owner_returns_descending_order(sqlite_client):
    """Sessions are returned in descending created_at order."""
    t1 = "2025-06-01T10:00:00+00:00"
    t2 = "2025-06-01T12:00:00+00:00"
    t3 = "2025-06-01T14:00:00+00:00"

    await _insert_raw_session(sqlite_client, "s-early", "alice@test.com", t1)
    await _insert_raw_session(sqlite_client, "s-mid", "alice@test.com", t2)
    await _insert_raw_session(sqlite_client, "s-late", "alice@test.com", t3)

    results = await sqlite_client.list_sessions_by_owner(
        "alice@test.com", since="2025-01-01T00:00:00+00:00"
    )
    ids = [r["session_id"] for r in results]

    assert ids == ["s-late", "s-mid", "s-early"]


async def test_list_sessions_by_owner_empty_results(sqlite_client):
    """Returns empty list when no sessions match."""
    results = await sqlite_client.list_sessions_by_owner(
        "nobody@test.com", since="2020-01-01T00:00:00+00:00"
    )
    assert results == []


async def test_list_sessions_by_owner_combined_owner_and_date_filter(sqlite_client):
    """Both owner and date filters are applied together."""
    old = "2024-01-01T00:00:00+00:00"
    recent = "2025-06-01T00:00:00+00:00"
    cutoff = "2025-01-01T00:00:00+00:00"

    await _insert_raw_session(sqlite_client, "alice-old", "alice@test.com", old)
    await _insert_raw_session(sqlite_client, "alice-new", "alice@test.com", recent)
    await _insert_raw_session(sqlite_client, "bob-new", "bob@test.com", recent)

    results = await sqlite_client.list_sessions_by_owner("alice@test.com", since=cutoff)
    ids = [r["session_id"] for r in results]

    assert ids == ["alice-new"]
