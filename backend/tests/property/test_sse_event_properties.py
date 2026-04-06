"""Property-based tests for SSE event format compliance.

Uses Hypothesis to generate random valid snapshot dicts for each node type
and verifies every yielded event matches ``data: <valid JSON>\\n\\n``.
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.routers.negotiation import _snapshot_to_events
from app.utils.sse import format_sse_event


# ---------------------------------------------------------------------------
# Hypothesis strategies for valid snapshot dicts
# ---------------------------------------------------------------------------

# Reusable text strategy — printable strings, reasonable length
_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
)

_turn_number = st.integers(min_value=1, max_value=100)
_price = st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False)


@st.composite
def negotiator_snapshot(draw):
    """Generate a valid negotiator_node snapshot dict."""
    role = draw(_safe_text)
    inner_thought = draw(_safe_text)
    public_message = draw(_safe_text)
    proposed_price = draw(_price)
    turn = draw(_turn_number)

    entry = {
        "role": role,
        "agent_type": "negotiator",
        "turn_number": turn,
        "content": {
            "inner_thought": inner_thought,
            "public_message": public_message,
            "proposed_price": proposed_price,
        },
    }
    state = {
        "history": [entry],
        "turn_count": turn,
        "deal_status": "Negotiating",
    }
    return {"negotiator_node": state}


@st.composite
def regulator_snapshot(draw):
    """Generate a valid regulator_node snapshot dict."""
    status = draw(st.sampled_from(["CLEAR", "WARNING", "BLOCKED"]))
    reasoning = draw(_safe_text)
    public_message = draw(_safe_text)
    turn = draw(_turn_number)

    entry = {
        "role": draw(_safe_text),
        "agent_type": "regulator",
        "turn_number": turn,
        "content": {
            "reasoning": reasoning,
            "public_message": public_message,
            "status": status,
        },
    }
    state = {
        "history": [entry],
        "turn_count": turn,
        "deal_status": "Negotiating",
    }
    return {"regulator_node": state}


@st.composite
def observer_snapshot(draw):
    """Generate a valid observer_node snapshot dict."""
    observation = draw(_safe_text)
    public_message = draw(_safe_text)
    turn = draw(_turn_number)

    entry = {
        "role": draw(_safe_text),
        "agent_type": "observer",
        "turn_number": turn,
        "content": {
            "observation": observation,
            "public_message": public_message,
        },
    }
    state = {
        "history": [entry],
        "turn_count": turn,
        "deal_status": "Negotiating",
    }
    return {"observer_node": state}


@st.composite
def dispatcher_snapshot(draw):
    """Generate a valid dispatcher_node snapshot with terminal deal_status."""
    deal_status = draw(st.sampled_from(["Agreed", "Failed", "Blocked"]))
    current_offer = draw(_price)
    turn_count = draw(_turn_number)
    warning_count = draw(st.integers(min_value=0, max_value=10))
    max_turns = draw(st.integers(min_value=turn_count, max_value=100))

    state = {
        "history": [],
        "deal_status": deal_status,
        "current_offer": current_offer,
        "turn_count": turn_count,
        "warning_count": warning_count,
        "total_tokens_used": draw(st.integers(min_value=0, max_value=100000)),
        "max_turns": max_turns,
    }
    return {"dispatcher_node": state}


# Combine all node types into a single strategy
any_valid_snapshot = st.one_of(
    negotiator_snapshot(),
    regulator_snapshot(),
    observer_snapshot(),
    dispatcher_snapshot(),
)


# ---------------------------------------------------------------------------
# Feature: 155_test-coverage-hardening
# Property 1: SSE event format compliance
# **Validates: Requirements 2.2**
#
# For any valid negotiation snapshot dict, every event string yielded by
# _snapshot_to_events() SHALL match the pattern ``data: <valid_json>\n\n``
# where <valid_json> is parseable by json.loads().
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=50, deadline=None)
@given(snapshot=any_valid_snapshot)
def test_sse_event_format_compliance(snapshot):
    """Every event from _snapshot_to_events must produce valid SSE wire format."""
    session_id = "prop-test-session"
    events = _snapshot_to_events(snapshot, session_id)

    # Dispatcher with terminal status always yields at least one event;
    # non-terminal nodes with content also yield events.
    assert isinstance(events, list)

    for event in events:
        sse_str = format_sse_event(event)

        # Must start with "data: "
        assert sse_str.startswith("data: "), (
            f"SSE must start with 'data: ', got: {sse_str!r}"
        )

        # Must end with "\n\n"
        assert sse_str.endswith("\n\n"), (
            f"SSE must end with '\\n\\n', got: {sse_str!r}"
        )

        # The payload between "data: " and "\n\n" must be valid JSON
        json_part = sse_str[len("data: "):-2]
        parsed = json.loads(json_part)

        # Every event must carry an event_type discriminator
        assert "event_type" in parsed, (
            f"Parsed SSE JSON missing 'event_type': {parsed}"
        )
