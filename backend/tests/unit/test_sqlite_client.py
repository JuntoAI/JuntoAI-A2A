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
