"""Property-based tests for SQLiteSessionClient session round-trip.

Feature: 155_test-coverage-hardening
Property 3: SQLite session round-trip — generate valid NegotiationStateModel
instances, create then retrieve, verify key fields match.

**Validates: Requirements 5.1, 5.2**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db.sqlite_client import SQLiteSessionClient
from app.models.negotiation import NegotiationStateModel

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=40,
)

_deal_statuses = st.sampled_from(
    ["Negotiating", "Agreed", "Blocked", "Failed", "Confirming"]
)

_json_value = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    _safe_text,
)

_simple_dict = st.dictionaries(keys=_safe_text, values=_json_value, max_size=3)

_history_entry = st.fixed_dictionaries(
    {"role": _safe_text, "content": _simple_dict},
)

_negotiation_state = st.builds(
    NegotiationStateModel,
    session_id=st.uuids().map(lambda u: u.hex),
    scenario_id=_safe_text,
    turn_count=st.integers(min_value=0, max_value=500),
    max_turns=st.integers(min_value=1, max_value=500),
    current_speaker=_safe_text,
    deal_status=_deal_statuses,
    current_offer=st.floats(
        min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False
    ),
    history=st.lists(_history_entry, max_size=3),
    warning_count=st.integers(min_value=0, max_value=50),
    hidden_context=_simple_dict,
    agreement_threshold=st.floats(
        min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False
    ),
    active_toggles=st.lists(_safe_text, max_size=3),
    turn_order=st.lists(_safe_text, max_size=4),
    turn_order_index=st.integers(min_value=0, max_value=50),
    agent_states=st.dictionaries(keys=_safe_text, values=_simple_dict, max_size=2),
)


# ---------------------------------------------------------------------------
# Feature: 155_test-coverage-hardening
# Property 3: SQLite session round-trip
# **Validates: Requirements 5.1, 5.2**
#
# For any valid NegotiationStateModel, creating a session via
# SQLiteSessionClient.create_session() and retrieving it via get_session()
# SHALL return a model with identical session_id, scenario_id, turn_count,
# max_turns, deal_status, and current_offer values.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=30, deadline=None)
@given(state=_negotiation_state)
@pytest.mark.asyncio
async def test_sqlite_session_round_trip_key_fields(state: NegotiationStateModel):
    """Create then retrieve a session — key fields must survive the round-trip."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "prop3.db")
        client = SQLiteSessionClient(db_path)

        await client.create_session(state)
        retrieved = await client.get_session(state.session_id)

        assert retrieved.session_id == state.session_id
        assert retrieved.scenario_id == state.scenario_id
        assert retrieved.turn_count == state.turn_count
        assert retrieved.max_turns == state.max_turns
        assert retrieved.deal_status == state.deal_status
        assert retrieved.current_offer == state.current_offer
