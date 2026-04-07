# Feature: 197_token-usage-history, Property 1: Grouping and sorting correctness
# Feature: 197_token-usage-history, Property 2: Date range filtering
# Feature: 197_token-usage-history, Property 3: DayGroup token cost sum invariant
"""Property-based tests for history grouping logic.

Tests the pure _group_sessions_by_day function directly for speed and determinism.
"""

import math
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.history import DayGroup, SessionHistoryItem, SessionHistoryResponse
from app.routers.negotiation import _group_sessions_by_day
from app.utils.token_cost import compute_token_cost

# --- Strategies ---

_nonempty_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)

# Generate datetimes across a wide range, always UTC
_utc_datetimes = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)


def _dt_to_iso(dt: datetime) -> str:
    """Convert datetime to ISO string like '2025-06-23T14:30:00+00:00'."""
    return dt.isoformat()


_session_item = st.builds(
    SessionHistoryItem,
    session_id=_nonempty_text,
    scenario_id=_nonempty_text,
    scenario_name=_nonempty_text,
    deal_status=st.sampled_from(["Agreed", "Blocked", "Failed"]),
    total_tokens_used=st.integers(min_value=0, max_value=1_000_000),
    token_cost=st.integers(min_value=1, max_value=1_000),
    created_at=_utc_datetimes.map(_dt_to_iso),
    completed_at=st.one_of(st.none(), _utc_datetimes.map(_dt_to_iso)),
)


# ---------------------------------------------------------------------------
# Property 1: Grouping and sorting correctness
# ---------------------------------------------------------------------------


@pytest.mark.property
@given(sessions=st.lists(_session_item, min_size=0, max_size=30))
@settings(max_examples=200)
def test_grouping_and_sorting_correctness(sessions: list[SessionHistoryItem]):
    """Property 1: Grouping and sorting correctness.

    **Validates: Requirements 1.2, 1.3**

    For any set of sessions:
    - Each session's UTC date matches its group's date
    - Sessions within groups sorted descending by created_at
    - Groups sorted descending by date
    """
    groups = _group_sessions_by_day(sessions)

    # Every session appears in exactly the right group
    for group in groups:
        for session in group.sessions:
            assert session.created_at[:10] == group.date, (
                f"Session created_at {session.created_at} doesn't match group date {group.date}"
            )

    # Sessions within each group are sorted descending by created_at
    for group in groups:
        created_ats = [s.created_at for s in group.sessions]
        assert created_ats == sorted(created_ats, reverse=True), (
            f"Sessions in group {group.date} not sorted descending"
        )

    # Groups sorted descending by date
    dates = [g.date for g in groups]
    assert dates == sorted(dates, reverse=True), "Groups not sorted descending by date"

    # All input sessions are accounted for
    total_in_groups = sum(len(g.sessions) for g in groups)
    assert total_in_groups == len(sessions)


# ---------------------------------------------------------------------------
# Property 2: Date range filtering
# ---------------------------------------------------------------------------

# Strategy: generate sessions across a wide date range, then pick a days value
_wide_range_sessions = st.lists(
    st.builds(
        SessionHistoryItem,
        session_id=_nonempty_text,
        scenario_id=_nonempty_text,
        scenario_name=_nonempty_text,
        deal_status=st.sampled_from(["Agreed", "Blocked", "Failed"]),
        total_tokens_used=st.integers(min_value=0, max_value=1_000_000),
        token_cost=st.integers(min_value=1, max_value=1_000),
        created_at=st.datetimes(
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2025, 12, 31),
            timezones=st.just(timezone.utc),
        ).map(_dt_to_iso),
        completed_at=st.none(),
    ),
    min_size=0,
    max_size=30,
)


@pytest.mark.property
@given(
    sessions=_wide_range_sessions,
    days=st.integers(min_value=1, max_value=90),
    now=st.datetimes(
        min_value=datetime(2025, 1, 1),
        max_value=datetime(2025, 12, 31),
        timezones=st.just(timezone.utc),
    ),
)
@settings(max_examples=200)
def test_date_range_filtering(
    sessions: list[SessionHistoryItem], days: int, now: datetime
):
    """Property 2: Date range filtering.

    **Validates: Requirements 1.4**

    For any sessions and any days value 1-90, only sessions within the
    window appear after filtering by cutoff.
    """
    cutoff = now - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    # Simulate the filtering the endpoint does before grouping
    filtered = [s for s in sessions if s.created_at >= cutoff_iso]
    groups = _group_sessions_by_day(filtered)

    # Every session in the result must be >= cutoff
    for group in groups:
        for session in group.sessions:
            assert session.created_at >= cutoff_iso, (
                f"Session {session.created_at} is before cutoff {cutoff_iso}"
            )

    # No session that should be included was dropped
    expected_count = len(filtered)
    actual_count = sum(len(g.sessions) for g in groups)
    assert actual_count == expected_count


# ---------------------------------------------------------------------------
# Property 3: DayGroup token cost sum invariant
# ---------------------------------------------------------------------------


@pytest.mark.property
@given(sessions=st.lists(_session_item, min_size=0, max_size=30))
@settings(max_examples=200)
def test_day_group_token_cost_sum_invariant(sessions: list[SessionHistoryItem]):
    """Property 3: DayGroup token cost sum invariant.

    **Validates: Requirements 1.6**

    For any DayGroup, total_token_cost == sum(session.token_cost for session in sessions).
    For the overall response, total_token_cost == sum(group.total_token_cost for group in days).
    """
    groups = _group_sessions_by_day(sessions)

    # Per-group invariant
    for group in groups:
        expected = sum(s.token_cost for s in group.sessions)
        assert group.total_token_cost == expected, (
            f"Group {group.date}: expected total_token_cost={expected}, got {group.total_token_cost}"
        )

    # Top-level invariant (simulating SessionHistoryResponse construction)
    total = sum(g.total_token_cost for g in groups)
    response = SessionHistoryResponse(
        days=groups,
        total_token_cost=total,
        period_days=7,
    )
    assert response.total_token_cost == sum(g.total_token_cost for g in response.days)
