"""Property-based test for session data round-trip preserving stats-relevant fields.

Feature: 270_public-stats-dashboard
Property 10: Session data round-trip preserves stats-relevant fields.

**Validates: Requirements 14.3**
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
    alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00"),
    min_size=1,
    max_size=20,
)

_deal_statuses = st.sampled_from(["Negotiating", "Agreed", "Blocked", "Failed", "Confirming"])

_model_ids = st.sampled_from(["gemini-3-flash-preview", "claude-sonnet-4", "claude-3.5-sonnet"])

_agent_call = st.fixed_dictionaries({
    "model_id": _model_ids,
    "input_tokens": st.integers(min_value=0, max_value=5000),
    "output_tokens": st.integers(min_value=0, max_value=5000),
    "latency_ms": st.integers(min_value=0, max_value=10000),
})

_negotiation_state = st.builds(
    NegotiationStateModel,
    session_id=st.uuids().map(lambda u: u.hex),
    scenario_id=st.sampled_from(["talent-war", "mna-buyout", "b2b-sales"]),
    turn_count=st.integers(min_value=0, max_value=30),
    max_turns=st.integers(min_value=1, max_value=50),
    current_speaker=_safe_text,
    deal_status=_deal_statuses,
    current_offer=st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False),
    history=st.just([]),
    warning_count=st.integers(min_value=0, max_value=10),
    hidden_context=st.just({}),
    agreement_threshold=st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False),
    active_toggles=st.just([]),
    turn_order=st.just([]),
    turn_order_index=st.just(0),
    agent_states=st.just({}),
    total_tokens_used=st.integers(min_value=0, max_value=1000000),
    model_overrides=st.dictionaries(keys=_safe_text, values=_model_ids, max_size=3),
    agent_calls=st.lists(_agent_call, max_size=5),
)


# ---------------------------------------------------------------------------
# Feature: 270_public-stats-dashboard, Property 10: Session round-trip
# **Validates: Requirements 14.3**
# ---------------------------------------------------------------------------


@pytest.mark.property
@given(state=_negotiation_state)
@settings(max_examples=100)
async def test_session_roundtrip_preserves_stats_fields(state: NegotiationStateModel):
    """Property 10: Session data round-trip preserves stats-relevant fields.

    For any valid NegotiationStateModel, persisting to SQLite and reading
    back must preserve total_tokens_used, deal_status, scenario_id,
    turn_count, and agent model_id values exactly.
    """
    import tempfile, os
    db_path = os.path.join(tempfile.mkdtemp(), f"test_{state.session_id}.db")
    client = SQLiteSessionClient(db_path=db_path)

    await client.create_session(state)
    retrieved = await client.get_session(state.session_id)

    # Stats-relevant fields must be preserved exactly
    assert retrieved.total_tokens_used == state.total_tokens_used
    assert retrieved.deal_status == state.deal_status
    assert retrieved.scenario_id == state.scenario_id
    assert retrieved.turn_count == state.turn_count

    # Model overrides preserved
    assert retrieved.model_overrides == state.model_overrides

    # Agent calls preserved (model_id in each call)
    assert len(retrieved.agent_calls) == len(state.agent_calls)
    for orig, ret in zip(state.agent_calls, retrieved.agent_calls):
        assert ret["model_id"] == orig["model_id"]
        assert ret["input_tokens"] == orig["input_tokens"]
        assert ret["output_tokens"] == orig["output_tokens"]
        assert ret["latency_ms"] == orig["latency_ms"]
