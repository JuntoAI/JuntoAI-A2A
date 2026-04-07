# Feature: 197_token-usage-history, Property 4: SessionHistoryResponse round-trip serialization
"""Property-based tests for history model round-trip serialization.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

For any valid SessionHistoryResponse instance, .model_dump_json() followed by
SessionHistoryResponse.model_validate_json() produces an equal object.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import builds

from app.models.history import DayGroup, SessionHistoryItem, SessionHistoryResponse

# --- Strategies ---

_nonempty_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=50,
)

_date_str = st.dates(
    min_value=__import__("datetime").date(2020, 1, 1),
    max_value=__import__("datetime").date(2030, 12, 31),
).map(lambda d: d.isoformat())

_iso_datetime = st.datetimes(
    min_value=__import__("datetime").datetime(2020, 1, 1),
    max_value=__import__("datetime").datetime(2030, 12, 31),
).map(lambda dt: dt.isoformat() + "Z")

session_history_item_strategy = builds(
    SessionHistoryItem,
    session_id=_nonempty_text,
    scenario_id=_nonempty_text,
    scenario_name=_nonempty_text,
    deal_status=st.sampled_from(["Agreed", "Blocked", "Failed"]),
    total_tokens_used=st.integers(min_value=0, max_value=10_000_000),
    token_cost=st.integers(min_value=1, max_value=10_000),
    created_at=_iso_datetime,
    completed_at=st.one_of(st.none(), _iso_datetime),
)

day_group_strategy = builds(
    DayGroup,
    date=_date_str,
    total_token_cost=st.integers(min_value=0, max_value=100_000),
    sessions=st.lists(session_history_item_strategy, min_size=0, max_size=5),
)

session_history_response_strategy = builds(
    SessionHistoryResponse,
    days=st.lists(day_group_strategy, min_size=0, max_size=5),
    total_token_cost=st.integers(min_value=0, max_value=1_000_000),
    period_days=st.integers(min_value=1, max_value=90),
)


@pytest.mark.property
@given(response=session_history_response_strategy)
@settings(max_examples=200)
def test_session_history_response_round_trip(response: SessionHistoryResponse):
    """Property 4: SessionHistoryResponse round-trip serialization.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    """
    json_str = response.model_dump_json()
    restored = SessionHistoryResponse.model_validate_json(json_str)
    assert restored == response
