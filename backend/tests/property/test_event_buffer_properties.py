"""Property-based tests for SSEEventBuffer replay correctness.

Feature: 155_test-coverage-hardening
Property 5: Event buffer replay correctness — generate random append sequences,
verify `replay_after` returns exactly the events after the given ID in order.

**Validates: Requirements 6.1**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.middleware.event_buffer import SSEEventBuffer

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_event_data = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=80,
)

_event_sequence = st.lists(_event_data, min_size=1, max_size=50)


# ---------------------------------------------------------------------------
# Feature: 155_test-coverage-hardening
# Property 5: Event buffer replay correctness
# **Validates: Requirements 6.1**
#
# For any sequence of append calls to SSEEventBuffer for a given session,
# replay_after(session, last_id) SHALL return exactly the events appended
# after last_id, in order, with correct event IDs.
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=50, deadline=None)
@given(events=_event_sequence, replay_point=st.integers(min_value=0, max_value=50))
@pytest.mark.asyncio
async def test_replay_after_returns_correct_suffix(
    events: list[str], replay_point: int
):
    """Replaying after any valid ID returns exactly the subsequent events in order."""
    buffer = SSEEventBuffer()
    session = "prop-test-session"

    # Append all events
    ids = []
    for evt in events:
        eid = await buffer.append(session, evt)
        ids.append(eid)

    # Clamp replay_point to valid range [0, len(events)]
    clamped = min(replay_point, len(events))

    result = await buffer.replay_after(session, clamped)

    # Expected: events after the replay point, with 1-based IDs
    expected = [(i + 1, evt) for i, evt in enumerate(events) if i + 1 > clamped]

    assert result == expected


@pytest.mark.property
@settings(max_examples=50, deadline=None)
@given(events=_event_sequence)
@pytest.mark.asyncio
async def test_replay_after_zero_returns_all(events: list[str]):
    """Replaying after ID 0 always returns every appended event."""
    buffer = SSEEventBuffer()
    session = "prop-zero-session"

    for evt in events:
        await buffer.append(session, evt)

    result = await buffer.replay_after(session, 0)

    assert len(result) == len(events)
    for idx, (eid, data) in enumerate(result):
        assert eid == idx + 1
        assert data == events[idx]


@pytest.mark.property
@settings(max_examples=50, deadline=None)
@given(events=_event_sequence)
@pytest.mark.asyncio
async def test_replay_after_last_returns_empty(events: list[str]):
    """Replaying after the last event ID returns an empty list."""
    buffer = SSEEventBuffer()
    session = "prop-last-session"

    last_id = 0
    for evt in events:
        last_id = await buffer.append(session, evt)

    result = await buffer.replay_after(session, last_id)
    assert result == []


@pytest.mark.property
@settings(max_examples=50, deadline=None)
@given(events=_event_sequence)
@pytest.mark.asyncio
async def test_append_ids_are_sequential(events: list[str]):
    """Append always returns strictly sequential 1-based IDs."""
    buffer = SSEEventBuffer()
    session = "prop-seq-session"

    ids = []
    for evt in events:
        ids.append(await buffer.append(session, evt))

    assert ids == list(range(1, len(events) + 1))
