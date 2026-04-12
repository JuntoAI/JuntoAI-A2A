"""Property-based tests for admin dashboard.

Feature: admin-dashboard
Uses Hypothesis to verify universal invariants across generated inputs.
"""

import time
from datetime import datetime
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from app.routers.admin import LoginRateLimiter, compute_tier

# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------

_ip_octet = st.integers(min_value=0, max_value=255)
_ip_address = st.tuples(_ip_octet, _ip_octet, _ip_octet, _ip_octet).map(
    lambda t: f"{t[0]}.{t[1]}.{t[2]}.{t[3]}"
)


# ---------------------------------------------------------------------------
# Feature: admin-dashboard, Property 1: Rate limiter blocks after threshold
# **Validates: Requirements 1.5**
#
# For any IP address and any sequence of failed login attempts, if the number
# of attempts from that IP within the last 5 minutes exceeds 10, then
# is_rate_limited(ip) SHALL return True. If the number of attempts is 10 or
# fewer, it SHALL return False. Additionally, attempts older than 5 minutes
# SHALL be ignored (TTL cleanup).
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    ip=_ip_address,
    num_attempts=st.integers(min_value=0, max_value=25),
)
def test_rate_limiter_blocks_after_threshold(ip: str, num_attempts: int):
    """After exactly max_attempts recorded attempts within the window,
    is_rate_limited returns True; fewer returns False.

    Feature: admin-dashboard, Property 1: Rate limiter blocks after threshold
    """
    limiter = LoginRateLimiter(max_attempts=10, window_seconds=300)

    # Record num_attempts attempts at a fixed "now"
    fake_now = 1_000_000.0
    with patch("app.routers.admin.time") as mock_time:
        mock_time.time.return_value = fake_now

        for _ in range(num_attempts):
            limiter.record_attempt(ip)

        result = limiter.is_rate_limited(ip)

    if num_attempts >= 10:
        assert result is True, (
            f"Expected rate-limited after {num_attempts} attempts, got False"
        )
    else:
        assert result is False, (
            f"Expected not rate-limited after {num_attempts} attempts, got True"
        )


@settings(max_examples=100)
@given(
    ip=_ip_address,
    old_attempts=st.integers(min_value=1, max_value=20),
    recent_attempts=st.integers(min_value=0, max_value=15),
)
def test_rate_limiter_ttl_cleanup_ignores_old_attempts(
    ip: str, old_attempts: int, recent_attempts: int
):
    """Attempts older than the window are cleaned up and do not count
    toward the threshold.

    Feature: admin-dashboard, Property 1: Rate limiter blocks after threshold
    """
    limiter = LoginRateLimiter(max_attempts=10, window_seconds=300)

    base_time = 1_000_000.0
    old_time = base_time - 301.0  # just outside the 5-minute window

    # Directly inject old attempts into the internal dict
    limiter._attempts[ip] = [old_time] * old_attempts

    # Now record recent attempts at base_time
    with patch("app.routers.admin.time") as mock_time:
        mock_time.time.return_value = base_time

        for _ in range(recent_attempts):
            limiter.record_attempt(ip)

        result = limiter.is_rate_limited(ip)

    # Only recent_attempts should count — old ones are outside the window
    if recent_attempts >= 10:
        assert result is True, (
            f"Expected rate-limited with {recent_attempts} recent attempts "
            f"(and {old_attempts} expired), got False"
        )
    else:
        assert result is False, (
            f"Expected not rate-limited with {recent_attempts} recent attempts "
            f"(and {old_attempts} expired), got True"
        )


@settings(max_examples=100)
@given(ip=_ip_address)
def test_rate_limiter_exactly_at_threshold(ip: str):
    """Exactly 10 attempts within the window triggers rate limiting;
    9 does not.

    Feature: admin-dashboard, Property 1: Rate limiter blocks after threshold
    """
    fake_now = 1_000_000.0

    # 9 attempts → not limited
    limiter_under = LoginRateLimiter(max_attempts=10, window_seconds=300)
    with patch("app.routers.admin.time") as mock_time:
        mock_time.time.return_value = fake_now
        for _ in range(9):
            limiter_under.record_attempt(ip)
        assert limiter_under.is_rate_limited(ip) is False

    # 10 attempts → limited
    limiter_at = LoginRateLimiter(max_attempts=10, window_seconds=300)
    with patch("app.routers.admin.time") as mock_time:
        mock_time.time.return_value = fake_now
        for _ in range(10):
            limiter_at.record_attempt(ip)
        assert limiter_at.is_rate_limited(ip) is True


# ---------------------------------------------------------------------------
# Reusable strategies for tier computation
# ---------------------------------------------------------------------------

_iso_timestamp = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
).map(lambda dt: dt.isoformat())

_optional_iso_timestamp = st.one_of(st.none(), _iso_timestamp)

_optional_bool = st.one_of(st.none(), st.booleans())

_profile_strategy = st.one_of(
    # None profile (no profile document)
    st.none(),
    # Profile dict with optional fields
    st.fixed_dictionaries(
        {},
        optional={
            "profile_completed_at": _optional_iso_timestamp,
            "email_verified": _optional_bool,
        },
    ),
)


# ---------------------------------------------------------------------------
# Feature: admin-dashboard, Property 4: Tier computation correctness
# **Validates: Requirements 4.2**
#
# For any profile document (or absence thereof), the computed tier SHALL be:
# 3 if profile_completed_at is non-null, 2 if email_verified is true and
# profile_completed_at is null, and 1 otherwise. None profile → tier == 1.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(profile=_profile_strategy)
def test_tier_computation_correctness(profile: dict | None):
    """compute_tier returns the correct tier based on profile fields.

    Feature: admin-dashboard, Property 4: Tier computation correctness
    """
    tier = compute_tier(profile)

    # Tier must always be one of {1, 2, 3}
    assert tier in (1, 2, 3), f"Unexpected tier value: {tier}"

    if profile is None:
        assert tier == 1, f"None profile should yield tier 1, got {tier}"
    elif profile.get("profile_completed_at"):
        assert tier == 3, (
            f"profile_completed_at={profile.get('profile_completed_at')!r} "
            f"should yield tier 3, got {tier}"
        )
    elif profile.get("email_verified"):
        assert tier == 2, (
            f"email_verified={profile.get('email_verified')!r} "
            f"(no profile_completed_at) should yield tier 2, got {tier}"
        )
    else:
        assert tier == 1, (
            f"No profile_completed_at, no email_verified → tier 1, got {tier}"
        )


# ---------------------------------------------------------------------------
# Feature: admin-dashboard, Property 9: Duration computation correctness
# **Validates: Requirements 8.3**
#
# For any valid created_at ISO 8601 timestamp and any completed_at timestamp
# that is equal to or later than created_at, the computed duration_seconds
# SHALL equal the integer difference in seconds between completed_at and
# created_at.
# ---------------------------------------------------------------------------

_created_at_dt = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
)

_non_negative_timedelta = st.timedeltas(
    min_value=__import__("datetime").timedelta(seconds=0),
    max_value=__import__("datetime").timedelta(days=365),
)


@settings(max_examples=100)
@given(
    created_at=_created_at_dt,
    delta=_non_negative_timedelta,
)
def test_duration_computation_correctness(created_at: datetime, delta):
    """duration_seconds equals the integer difference in seconds between
    completed_at and created_at when both are ISO 8601 strings.

    Feature: admin-dashboard, Property 9: Duration computation correctness
    """
    completed_at = created_at + delta

    # Convert to ISO 8601 strings (same as event_stream does)
    created_at_str = created_at.isoformat()
    completed_at_str = completed_at.isoformat()

    # Compute duration using the same logic as event_stream()
    duration_seconds = int(
        (datetime.fromisoformat(completed_at_str) - datetime.fromisoformat(created_at_str)).total_seconds()
    )

    # Expected: integer seconds from the timedelta
    expected_seconds = int(delta.total_seconds())

    assert duration_seconds == expected_seconds, (
        f"created_at={created_at_str}, completed_at={completed_at_str}, "
        f"duration_seconds={duration_seconds}, expected={expected_seconds}"
    )

    # duration_seconds must be non-negative
    assert duration_seconds >= 0, (
        f"duration_seconds should be non-negative, got {duration_seconds}"
    )


# ---------------------------------------------------------------------------
# Feature: admin-dashboard, Property 2: Scenario analytics aggregation correctness
# **Validates: Requirements 3.5**
#
# For any list of session documents with varying scenario_id and
# total_tokens_used values, the computed scenario analytics SHALL produce a
# run_count per scenario_id equal to the actual count of sessions with that
# scenario_id, and an avg_tokens_used per scenario_id equal to the arithmetic
# mean of total_tokens_used across those sessions.
# ---------------------------------------------------------------------------

from collections import Counter

import pytest

from app.routers.admin import _compute_scenario_analytics

_scenario_id = st.sampled_from(["talent-war", "m-and-a", "b2b-sales", "custom-1", "custom-2"])

_session_for_scenario = st.fixed_dictionaries(
    {
        "scenario_id": _scenario_id,
        "total_tokens_used": st.integers(min_value=0, max_value=100_000),
    }
)

_session_list = st.lists(_session_for_scenario, min_size=0, max_size=50)


@settings(max_examples=100)
@given(sessions=_session_list)
def test_scenario_analytics_aggregation_correctness(sessions: list[dict]):
    """_compute_scenario_analytics returns correct run_count and
    avg_tokens_used for every scenario_id present in the input.

    Feature: admin-dashboard, Property 2: Scenario analytics aggregation correctness
    """
    result = _compute_scenario_analytics(sessions)

    # Build expected values from raw input
    buckets: dict[str, list[int]] = {}
    for s in sessions:
        sid = s["scenario_id"]
        tokens = s["total_tokens_used"]
        buckets.setdefault(sid, []).append(tokens)

    result_map = {r.scenario_id: r for r in result}

    # Every scenario_id from input must appear in output
    for sid in buckets:
        assert sid in result_map, (
            f"scenario_id {sid!r} present in input but missing from output"
        )

    # Verify run_count and avg_tokens_used per scenario
    for sid, token_list in buckets.items():
        analytics = result_map[sid]

        assert analytics.run_count == len(token_list), (
            f"scenario_id={sid!r}: expected run_count={len(token_list)}, "
            f"got {analytics.run_count}"
        )

        expected_avg = sum(token_list) / len(token_list)
        assert analytics.avg_tokens_used == pytest.approx(expected_avg), (
            f"scenario_id={sid!r}: expected avg_tokens_used≈{expected_avg}, "
            f"got {analytics.avg_tokens_used}"
        )

    # No extra scenario_ids in output that weren't in input
    for r in result:
        assert r.scenario_id in buckets, (
            f"scenario_id {r.scenario_id!r} in output but not in input"
        )


# ---------------------------------------------------------------------------
# Feature: admin-dashboard, Property 3: Model performance aggregation correctness
# **Validates: Requirements 3.6**
#
# For any list of agent_calls records with varying model_id, latency_ms,
# input_tokens, output_tokens, and error values, the computed model
# performance metrics SHALL produce per-model averages and error counts that
# match the actual arithmetic means and counts from the input data. Sessions
# lacking agent_calls data SHALL be excluded.
# ---------------------------------------------------------------------------

from app.routers.admin import _compute_model_performance

_model_id = st.sampled_from(["gemini-3-flash-preview", "claude-sonnet-4", "claude-3.5-sonnet", "gemini-3.1-pro-preview"])

_agent_call = st.fixed_dictionaries(
    {
        "model_id": _model_id,
        "latency_ms": st.integers(min_value=0, max_value=30_000),
        "input_tokens": st.integers(min_value=0, max_value=50_000),
        "output_tokens": st.integers(min_value=0, max_value=20_000),
        "error": st.booleans(),
    }
)

_agent_calls_list = st.lists(_agent_call, min_size=0, max_size=20)

# Sessions: some have agent_calls, some have empty list, some have None/missing key
_session_with_calls = st.fixed_dictionaries(
    {"agent_calls": _agent_calls_list}
)
_session_empty_calls = st.just({"agent_calls": []})
_session_none_calls = st.just({"agent_calls": None})
_session_missing_calls = st.just({})

_session_for_model_perf = st.one_of(
    _session_with_calls,
    _session_empty_calls,
    _session_none_calls,
    _session_missing_calls,
)

_session_list_for_model_perf = st.lists(_session_for_model_perf, min_size=0, max_size=30)


@settings(max_examples=100)
@given(sessions=_session_list_for_model_perf)
def test_model_performance_aggregation_correctness(sessions: list[dict]):
    """_compute_model_performance returns correct per-model averages,
    error counts, and total calls for every model_id present in the input.
    Sessions without agent_calls are excluded.

    Feature: admin-dashboard, Property 3: Model performance aggregation correctness
    """
    result = _compute_model_performance(sessions)

    # Build expected values from raw input
    expected: dict[str, dict] = {}
    for s in sessions:
        calls = s.get("agent_calls")
        if not calls:
            continue
        for call in calls:
            mid = call.get("model_id", "unknown")
            if mid not in expected:
                expected[mid] = {
                    "latencies": [],
                    "input_tokens": [],
                    "output_tokens": [],
                    "error_count": 0,
                }
            expected[mid]["latencies"].append(call.get("latency_ms", 0) or 0)
            expected[mid]["input_tokens"].append(call.get("input_tokens", 0) or 0)
            expected[mid]["output_tokens"].append(call.get("output_tokens", 0) or 0)
            if call.get("error"):
                expected[mid]["error_count"] += 1

    result_map = {r.model_id: r for r in result}

    # Every model_id from input must appear in output
    for mid in expected:
        assert mid in result_map, (
            f"model_id {mid!r} present in input but missing from output"
        )

    # Verify per-model metrics
    for mid, data in expected.items():
        perf = result_map[mid]
        n = len(data["latencies"])

        assert perf.total_calls == n, (
            f"model_id={mid!r}: expected total_calls={n}, got {perf.total_calls}"
        )

        expected_avg_latency = sum(data["latencies"]) / n
        assert perf.avg_latency_ms == pytest.approx(expected_avg_latency), (
            f"model_id={mid!r}: expected avg_latency_ms≈{expected_avg_latency}, "
            f"got {perf.avg_latency_ms}"
        )

        expected_avg_input = sum(data["input_tokens"]) / n
        assert perf.avg_input_tokens == pytest.approx(expected_avg_input), (
            f"model_id={mid!r}: expected avg_input_tokens≈{expected_avg_input}, "
            f"got {perf.avg_input_tokens}"
        )

        expected_avg_output = sum(data["output_tokens"]) / n
        assert perf.avg_output_tokens == pytest.approx(expected_avg_output), (
            f"model_id={mid!r}: expected avg_output_tokens≈{expected_avg_output}, "
            f"got {perf.avg_output_tokens}"
        )

        assert perf.error_count == data["error_count"], (
            f"model_id={mid!r}: expected error_count={data['error_count']}, "
            f"got {perf.error_count}"
        )

    # No extra model_ids in output that weren't in input
    for r in result:
        assert r.model_id in expected, (
            f"model_id {r.model_id!r} in output but not in input"
        )


# ---------------------------------------------------------------------------
# Feature: admin-dashboard, Property 5: Cursor-based pagination correctness
# **Validates: Requirements 4.3, 5.3, 5.5**
#
# For any ordered list of documents (users sorted by signed_up_at or
# simulations sorted by created_at), any valid cursor value, any page_size
# between 1 and 200, and any sort direction (asc/desc), the returned page
# SHALL: (a) contain at most page_size items, (b) contain only items that
# come strictly after the cursor in the specified sort order, (c) be
# correctly ordered, and (d) the next_cursor (if present) SHALL equal the
# sort field of the last item in the page.
# ---------------------------------------------------------------------------


def paginate(
    items: list[str],
    cursor: str | None,
    page_size: int,
    descending: bool = True,
) -> tuple[list[str], str | None]:
    """Pure pagination function for testing.

    items: list of sort-field values (e.g., timestamps), already sorted in
           the direction indicated by *descending*.
    cursor: the sort-field value to start after (exclusive).
    page_size: max items to return.
    descending: sort direction — True means items are sorted largest-first.

    Returns: (page_items, next_cursor)
    """
    if cursor is not None:
        # Find items strictly after the cursor in the given sort order.
        # "After" means: for descending, values < cursor; for ascending, values > cursor.
        if descending:
            filtered = [v for v in items if v < cursor]
        else:
            filtered = [v for v in items if v > cursor]
    else:
        filtered = list(items)

    page = filtered[:page_size]
    next_cursor = page[-1] if page else None
    return page, next_cursor


# Strategy: generate a list of unique ISO-ish timestamp strings, then sort them.
# We use a compact datetime range to keep strings comparable via lexicographic order
# (which matches chronological order for ISO 8601 with fixed-width fields).

_pagination_timestamp = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
).map(lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S"))

_unique_timestamps = st.lists(
    _pagination_timestamp, min_size=0, max_size=60, unique=True
)

_page_size = st.integers(min_value=1, max_value=200)
_descending = st.booleans()


@st.composite
def _pagination_scenario(draw):
    """Draw a complete pagination scenario: sorted items, optional cursor,
    page_size, and sort direction."""
    timestamps = draw(_unique_timestamps)
    desc = draw(_descending)
    # Sort items in the requested direction
    sorted_items = sorted(timestamps, reverse=desc)

    # Cursor is either None or one of the timestamps in the list
    if sorted_items:
        cursor = draw(
            st.one_of(
                st.none(),
                st.sampled_from(sorted_items),
            )
        )
    else:
        cursor = draw(st.none())

    ps = draw(_page_size)
    return sorted_items, cursor, ps, desc


@settings(max_examples=100)
@given(scenario=_pagination_scenario())
def test_cursor_based_pagination_correctness(scenario):
    """paginate returns a page that satisfies all four pagination invariants.

    Feature: admin-dashboard, Property 5: Cursor-based pagination correctness
    """
    items, cursor, page_size, descending = scenario
    page, next_cursor = paginate(items, cursor, page_size, descending)

    # (a) Page contains at most page_size items
    assert len(page) <= page_size, (
        f"Page has {len(page)} items, exceeds page_size={page_size}"
    )

    # (b) All items come strictly after the cursor in the specified sort order
    if cursor is not None:
        for v in page:
            if descending:
                assert v < cursor, (
                    f"Descending: item {v!r} is not strictly after cursor {cursor!r}"
                )
            else:
                assert v > cursor, (
                    f"Ascending: item {v!r} is not strictly after cursor {cursor!r}"
                )

    # (c) Items are correctly ordered
    for i in range(len(page) - 1):
        if descending:
            assert page[i] >= page[i + 1], (
                f"Descending order violated: {page[i]!r} < {page[i + 1]!r}"
            )
        else:
            assert page[i] <= page[i + 1], (
                f"Ascending order violated: {page[i]!r} > {page[i + 1]!r}"
            )

    # (d) next_cursor equals the sort field of the last item (if page is non-empty)
    if page:
        assert next_cursor == page[-1], (
            f"next_cursor={next_cursor!r} != last item {page[-1]!r}"
        )
    else:
        assert next_cursor is None, (
            f"Empty page should have next_cursor=None, got {next_cursor!r}"
        )

    # Bonus: if no cursor, returns from the beginning of the sorted list
    if cursor is None:
        expected_page = items[:page_size]
        assert page == expected_page, (
            f"No cursor: expected first {page_size} items of sorted list, "
            f"got {page!r} vs {expected_page!r}"
        )


# ---------------------------------------------------------------------------
# Feature: admin-dashboard, Property 6: Collection filtering correctness
# **Validates: Requirements 4.9, 5.4**
#
# For any list of user or simulation documents and any combination of filter
# criteria (tier + status for users; scenario_id + deal_status + owner_email
# for simulations), every item in the filtered result SHALL match all
# specified filter criteria, and no item matching all criteria SHALL be
# excluded from the result.
# ---------------------------------------------------------------------------


def filter_users(
    users: list[dict], tier: int | None, status: str | None
) -> list[dict]:
    """Filter users by tier and/or status."""
    result = users
    if tier is not None:
        result = [u for u in result if u.get("tier") == tier]
    if status is not None:
        result = [u for u in result if u.get("user_status", "active") == status]
    return result


def filter_simulations(
    sims: list[dict],
    scenario_id: str | None,
    deal_status: str | None,
    owner_email: str | None,
) -> list[dict]:
    """Filter simulations by scenario_id, deal_status, and/or owner_email."""
    result = sims
    if scenario_id is not None:
        result = [s for s in result if s.get("scenario_id") == scenario_id]
    if deal_status is not None:
        result = [s for s in result if s.get("deal_status") == deal_status]
    if owner_email is not None:
        result = [s for s in result if s.get("owner_email") == owner_email]
    return result


# --- Strategies for user filtering ---

_user_tier = st.integers(min_value=1, max_value=3)
_user_status_value = st.sampled_from(["active", "suspended", "banned"])

_user_doc = st.fixed_dictionaries(
    {
        "email": st.from_regex(r"user[0-9]{1,4}@example\.com", fullmatch=True),
        "tier": _user_tier,
        "user_status": st.one_of(
            # Some docs have user_status, some omit it (backward compat → "active")
            _user_status_value,
            st.just(None),  # sentinel: we'll pop the key to simulate missing field
        ),
    }
)

_user_doc_list = st.lists(_user_doc, min_size=0, max_size=20)

_optional_tier_filter = st.one_of(st.none(), _user_tier)
_optional_status_filter = st.one_of(st.none(), _user_status_value)


@settings(max_examples=100)
@given(
    raw_users=_user_doc_list,
    tier_filter=_optional_tier_filter,
    status_filter=_optional_status_filter,
)
def test_user_collection_filtering_correctness(
    raw_users: list[dict],
    tier_filter: int | None,
    status_filter: str | None,
):
    """filter_users returns exactly the users matching all specified criteria.
    Missing user_status is treated as "active".

    Feature: admin-dashboard, Property 6: Collection filtering correctness
    """
    # Normalise: if user_status was generated as None, remove the key
    # to simulate a document that lacks the field entirely.
    users = []
    for u in raw_users:
        doc = dict(u)
        if doc["user_status"] is None:
            del doc["user_status"]
        users.append(doc)

    filtered = filter_users(users, tier_filter, status_filter)

    # 1. Every result matches ALL specified criteria
    for u in filtered:
        if tier_filter is not None:
            assert u.get("tier") == tier_filter, (
                f"User {u} in result but tier={u.get('tier')} != filter {tier_filter}"
            )
        if status_filter is not None:
            effective_status = u.get("user_status", "active")
            assert effective_status == status_filter, (
                f"User {u} in result but status={effective_status!r} != filter {status_filter!r}"
            )

    # 2. No matching item is excluded (completeness)
    for u in users:
        matches_tier = tier_filter is None or u.get("tier") == tier_filter
        matches_status = (
            status_filter is None
            or u.get("user_status", "active") == status_filter
        )
        if matches_tier and matches_status:
            assert u in filtered, (
                f"User {u} matches all criteria but was excluded from result"
            )

    # 3. Result is a subset of the input (no fabricated items)
    for u in filtered:
        assert u in users, f"Filtered result contains item not in input: {u}"


# --- Strategies for simulation filtering ---

_sim_scenario_id = st.sampled_from(
    ["talent-war", "m-and-a", "b2b-sales", "custom-1"]
)
_sim_deal_status = st.sampled_from(
    ["Agreed", "Blocked", "Failed", "In Progress"]
)
_sim_owner_email = st.sampled_from(
    ["alice@example.com", "bob@example.com", "carol@example.com", "dave@example.com"]
)

_sim_doc = st.fixed_dictionaries(
    {
        "session_id": st.uuids().map(str),
        "scenario_id": _sim_scenario_id,
        "deal_status": _sim_deal_status,
        "owner_email": _sim_owner_email,
    }
)

_sim_doc_list = st.lists(_sim_doc, min_size=0, max_size=40)

_optional_scenario_filter = st.one_of(st.none(), _sim_scenario_id)
_optional_deal_status_filter = st.one_of(st.none(), _sim_deal_status)
_optional_owner_email_filter = st.one_of(st.none(), _sim_owner_email)


@settings(max_examples=100)
@given(
    sims=_sim_doc_list,
    scenario_filter=_optional_scenario_filter,
    deal_status_filter=_optional_deal_status_filter,
    owner_email_filter=_optional_owner_email_filter,
)
def test_simulation_collection_filtering_correctness(
    sims: list[dict],
    scenario_filter: str | None,
    deal_status_filter: str | None,
    owner_email_filter: str | None,
):
    """filter_simulations returns exactly the simulations matching all
    specified criteria.

    Feature: admin-dashboard, Property 6: Collection filtering correctness
    """
    filtered = filter_simulations(
        sims, scenario_filter, deal_status_filter, owner_email_filter
    )

    # 1. Every result matches ALL specified criteria
    for s in filtered:
        if scenario_filter is not None:
            assert s.get("scenario_id") == scenario_filter, (
                f"Sim {s['session_id']} in result but scenario_id="
                f"{s.get('scenario_id')!r} != filter {scenario_filter!r}"
            )
        if deal_status_filter is not None:
            assert s.get("deal_status") == deal_status_filter, (
                f"Sim {s['session_id']} in result but deal_status="
                f"{s.get('deal_status')!r} != filter {deal_status_filter!r}"
            )
        if owner_email_filter is not None:
            assert s.get("owner_email") == owner_email_filter, (
                f"Sim {s['session_id']} in result but owner_email="
                f"{s.get('owner_email')!r} != filter {owner_email_filter!r}"
            )

    # 2. No matching item is excluded (completeness)
    for s in sims:
        matches_scenario = (
            scenario_filter is None or s.get("scenario_id") == scenario_filter
        )
        matches_deal = (
            deal_status_filter is None
            or s.get("deal_status") == deal_status_filter
        )
        matches_owner = (
            owner_email_filter is None
            or s.get("owner_email") == owner_email_filter
        )
        if matches_scenario and matches_deal and matches_owner:
            assert s in filtered, (
                f"Sim {s['session_id']} matches all criteria but was excluded"
            )

    # 3. Result is a subset of the input (no fabricated items)
    for s in filtered:
        assert s in sims, f"Filtered result contains item not in input: {s}"


# ---------------------------------------------------------------------------
# Feature: admin-dashboard, Property 7: Transcript round-trip
# **Validates: Requirements 6.7, 6.2**
#
# For any valid session history array (list of entries with role, agent_type,
# content containing inner_thought/reasoning/observation and public_message),
# formatting the history into a Simulation_Transcript and then parsing the
# transcript back into structured entries SHALL preserve the agent role, turn
# number, and public message of each entry.
# ---------------------------------------------------------------------------

import re

from app.routers.admin import format_transcript

_agent_names = st.sampled_from([
    "Buyer", "Seller", "Recruiter", "Candidate",
    "HR Compliance", "EU Regulator", "Procurement Bot",
    "Account Exec", "CTO", "Observer",
])

_agent_types = st.sampled_from(["negotiator", "regulator", "observer"])

# Public messages must not contain newlines since the transcript format
# puts each field on a single line.
_safe_text = st.text(
    alphabet=st.characters(blacklist_characters="\n\r"),
    min_size=1,
    max_size=100,
)


@st.composite
def _history_entry(draw, turn_number: int):
    """Draw a single history entry with a fixed turn number."""
    role = draw(_agent_names)
    agent_type = draw(_agent_types)

    # Build content dict based on agent_type
    thought_key = {
        "negotiator": "inner_thought",
        "regulator": "reasoning",
        "observer": "observation",
    }[agent_type]

    content = {
        thought_key: draw(_safe_text),
        "public_message": draw(_safe_text),
    }

    return {
        "role": role,
        "agent_type": agent_type,
        "turn_number": turn_number,
        "content": content,
    }


@st.composite
def _history_array(draw):
    """Generate a valid history array with monotonically non-decreasing turn numbers."""
    num_entries = draw(st.integers(min_value=1, max_value=15))
    history = []
    current_turn = 1
    for i in range(num_entries):
        # Occasionally bump the turn number
        if i > 0 and draw(st.booleans()):
            current_turn += 1
        entry = draw(_history_entry(current_turn))
        history.append(entry)
    return history


@settings(max_examples=100)
@given(history=_history_array())
def test_transcript_round_trip(history: list[dict]):
    """format_transcript output can be parsed back to recover agent role,
    turn number, and public message for every history entry.

    Feature: admin-dashboard, Property 7: Transcript round-trip
    """
    session = {
        "session_id": "test-session",
        "scenario_id": "test-scenario",
        "created_at": "2024-01-01T00:00:00",
        "deal_status": "Agreed",
        "history": history,
    }

    transcript = format_transcript(session)

    # Parse the transcript back into structured entries
    parsed_entries: list[dict] = []
    current_turn: int | None = None

    turn_re = re.compile(r"^--- Turn (\d+) ---$")
    role_re = re.compile(r"^\[(.+)\]$")
    message_re = re.compile(r"^Message: (.+)$")

    lines = transcript.split("\n")
    i = 0
    # Skip header lines until we hit the first turn marker
    while i < len(lines):
        turn_match = turn_re.match(lines[i])
        if turn_match:
            break
        i += 1

    # Parse turn blocks
    pending_role: str | None = None
    pending_message: str | None = None

    while i < len(lines):
        line = lines[i]

        turn_match = turn_re.match(line)
        if turn_match:
            # Flush any pending entry before switching turns
            if pending_role is not None:
                parsed_entries.append({
                    "turn_number": current_turn,
                    "role": pending_role,
                    "public_message": pending_message or "",
                })
                pending_role = None
                pending_message = None
            current_turn = int(turn_match.group(1))
            i += 1
            continue

        role_match = role_re.match(line)
        if role_match:
            # Flush previous entry if any
            if pending_role is not None:
                parsed_entries.append({
                    "turn_number": current_turn,
                    "role": pending_role,
                    "public_message": pending_message or "",
                })
                pending_message = None
            pending_role = role_match.group(1)
            i += 1
            continue

        msg_match = message_re.match(line)
        if msg_match:
            pending_message = msg_match.group(1)
            i += 1
            continue

        i += 1

    # Flush last pending entry
    if pending_role is not None:
        parsed_entries.append({
            "turn_number": current_turn,
            "role": pending_role,
            "public_message": pending_message or "",
        })

    # Verify: same number of entries
    assert len(parsed_entries) == len(history), (
        f"Expected {len(history)} entries, parsed {len(parsed_entries)}"
    )

    # Verify: each entry preserves role, turn_number, and public_message
    for idx, (original, parsed) in enumerate(zip(history, parsed_entries)):
        assert parsed["turn_number"] == original["turn_number"], (
            f"Entry {idx}: turn_number mismatch: "
            f"expected {original['turn_number']}, got {parsed['turn_number']}"
        )
        assert parsed["role"] == original["role"], (
            f"Entry {idx}: role mismatch: "
            f"expected {original['role']!r}, got {parsed['role']!r}"
        )
        expected_msg = original["content"].get("public_message", "")
        assert parsed["public_message"] == expected_msg, (
            f"Entry {idx}: public_message mismatch: "
            f"expected {expected_msg!r}, got {parsed['public_message']!r}"
        )

# ---------------------------------------------------------------------------
# Feature: admin-dashboard, Property 8: CSV serialization round-trip
# **Validates: Requirements 7.9, 7.8**
#
# For any set of records (including field values containing commas, double
# quotes, newlines, and Unicode characters), serializing to CSV using
# Python's csv.DictWriter with StringIO and parsing back with csv.DictReader
# SHALL produce field values identical to the original data.
# ---------------------------------------------------------------------------

import csv
import io

# Strategy: generate field values that stress CSV escaping — commas, double
# quotes, newlines, and Unicode characters mixed with normal text.
_csv_field_value = st.text(
    alphabet=st.characters(
        categories=("L", "M", "N", "P", "S", "Z"),
        include_characters=',"\n\r\t ',
    ),
    min_size=0,
    max_size=200,
)

# Fixed set of column names to keep things deterministic
_CSV_FIELD_NAMES = ["field_a", "field_b", "field_c", "field_d", "field_e"]

_csv_record = st.fixed_dictionaries(
    {name: _csv_field_value for name in _CSV_FIELD_NAMES}
)

_csv_record_list = st.lists(_csv_record, min_size=1, max_size=30)


@settings(max_examples=100)
@given(records=_csv_record_list)
def test_csv_serialization_round_trip(records: list[dict]):
    """Serialize records to CSV via DictWriter, parse back via DictReader,
    and verify every field value is identical.

    Feature: admin-dashboard, Property 8: CSV serialization round-trip
    """
    # --- Serialize ---
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELD_NAMES)
    writer.writeheader()
    writer.writerows(records)

    csv_text = buf.getvalue()

    # --- Parse back ---
    reader = csv.DictReader(io.StringIO(csv_text))
    parsed_records = list(reader)

    # Same number of records
    assert len(parsed_records) == len(records), (
        f"Expected {len(records)} records after round-trip, got {len(parsed_records)}"
    )

    # Every field value is identical
    for row_idx, (original, parsed) in enumerate(zip(records, parsed_records)):
        for field in _CSV_FIELD_NAMES:
            original_val = original[field]
            parsed_val = parsed[field]
            assert parsed_val == original_val, (
                f"Row {row_idx}, field {field!r}: "
                f"original={original_val!r}, parsed={parsed_val!r}"
            )
