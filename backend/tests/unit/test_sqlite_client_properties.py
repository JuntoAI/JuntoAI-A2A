"""Property-based tests for SQLiteSessionClient.

Feature: 080_a2a-local-battle-arena
Properties 1, 2, 3 — session round-trip, missing session error, update merge.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db.sqlite_client import SQLiteSessionClient
from app.exceptions import SessionNotFoundError
from app.models.negotiation import NegotiationStateModel

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Safe text strategy — printable strings, no surrogates or null bytes
_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=50,
)

_deal_statuses = st.sampled_from(["Negotiating", "Agreed", "Blocked", "Failed"])

# Simple JSON-safe dict values for nested fields
_json_value = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    _safe_text,
)

_simple_dict = st.dictionaries(
    keys=_safe_text,
    values=_json_value,
    max_size=5,
)

_history_entry = st.fixed_dictionaries(
    {"role": _safe_text, "content": _simple_dict},
)

_negotiation_state = st.builds(
    NegotiationStateModel,
    session_id=st.uuids().map(lambda u: u.hex),
    scenario_id=_safe_text,
    turn_count=st.integers(min_value=0, max_value=1000),
    max_turns=st.integers(min_value=1, max_value=1000),
    current_speaker=_safe_text,
    deal_status=_deal_statuses,
    current_offer=st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False),
    history=st.lists(_history_entry, max_size=5),
    warning_count=st.integers(min_value=0, max_value=100),
    hidden_context=_simple_dict,
    agreement_threshold=st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False),
    active_toggles=st.lists(_safe_text, max_size=5),
    turn_order=st.lists(_safe_text, max_size=5),
    turn_order_index=st.integers(min_value=0, max_value=100),
    agent_states=st.dictionaries(keys=_safe_text, values=_simple_dict, max_size=3),
    total_tokens_used=st.integers(min_value=0, max_value=10_000_000),
    custom_prompts=st.dictionaries(keys=_safe_text, values=_safe_text, max_size=3),
    model_overrides=st.dictionaries(keys=_safe_text, values=_safe_text, max_size=3),
)


# ---------------------------------------------------------------------------
# Feature: 080_a2a-local-battle-arena, Property 1: Session round-trip (create → read equivalence)
# **Validates: Requirements 2.4, 2.5, 2.7**
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(state=_negotiation_state)
@pytest.mark.asyncio
async def test_session_round_trip(state: NegotiationStateModel):
    """For any valid NegotiationStateModel, create then get returns an equivalent model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "roundtrip.db")
        client = SQLiteSessionClient(db_path=db_path)

        await client.create_session(state)
        retrieved = await client.get_session(state.session_id)

        assert retrieved == state, (
            f"Round-trip mismatch.\n"
            f"Original:  {state.model_dump_json()}\n"
            f"Retrieved: {retrieved.model_dump_json()}"
        )


# ---------------------------------------------------------------------------
# Feature: 080_a2a-local-battle-arena, Property 2: Missing session raises SessionNotFoundError
# **Validates: Requirements 1.6**
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(session_id=st.uuids().map(lambda u: u.hex))
@pytest.mark.asyncio
async def test_missing_session_raises_error(session_id: str):
    """For any session_id not inserted, get_session raises SessionNotFoundError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "missing.db")
        client = SQLiteSessionClient(db_path=db_path)

        with pytest.raises(SessionNotFoundError):
            await client.get_session(session_id)


# ---------------------------------------------------------------------------
# Feature: 080_a2a-local-battle-arena, Property 3: Update merge preserves unmodified fields
# **Validates: Requirements 2.6**
# ---------------------------------------------------------------------------

# Updatable scalar fields and their strategies
_UPDATABLE_FIELDS: dict[str, st.SearchStrategy[Any]] = {
    "turn_count": st.integers(min_value=0, max_value=1000),
    "max_turns": st.integers(min_value=1, max_value=1000),
    "current_speaker": _safe_text,
    "deal_status": _deal_statuses,
    "current_offer": st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False),
    "warning_count": st.integers(min_value=0, max_value=100),
    "turn_order_index": st.integers(min_value=0, max_value=100),
    "total_tokens_used": st.integers(min_value=0, max_value=10_000_000),
}


# Build a strategy that generates a dict where each key maps to a value
# valid for that specific field.
def _build_updates_strategy():
    """Generate a dict of field_name → valid_value for a random subset of updatable fields."""
    field_names = sorted(_UPDATABLE_FIELDS.keys())

    @st.composite
    def _inner(draw):
        # Pick which fields to update (at least 1)
        chosen = draw(
            st.lists(
                st.sampled_from(field_names),
                min_size=1,
                max_size=4,
                unique=True,
            )
        )
        result = {}
        for field in chosen:
            result[field] = draw(_UPDATABLE_FIELDS[field])
        return result

    return _inner()


@settings(max_examples=100)
@given(state=_negotiation_state, updates=_build_updates_strategy())
@pytest.mark.asyncio
async def test_update_merge_preserves_unmodified_fields(
    state: NegotiationStateModel,
    updates: dict,
):
    """Updated fields match new values; unmodified fields retain originals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "merge.db")
        client = SQLiteSessionClient(db_path=db_path)

        # Persist original
        await client.create_session(state)
        original_dump = state.model_dump()

        # Apply partial update
        await client.update_session(state.session_id, updates)

        # Read back
        updated = await client.get_session(state.session_id)
        updated_dump = updated.model_dump()

        # (a) Updated fields have new values
        for key, new_val in updates.items():
            assert updated_dump[key] == new_val, (
                f"Field '{key}' should be {new_val!r}, got {updated_dump[key]!r}"
            )

        # (b) Unmodified fields retain original values
        for key in original_dump:
            if key not in updates:
                assert updated_dump[key] == original_dump[key], (
                    f"Unmodified field '{key}' changed: "
                    f"{original_dump[key]!r} → {updated_dump[key]!r}"
                )
