"""Property-based tests for the stats aggregator.

Feature: 270_public-stats-dashboard
Properties 1–7, 11: Stats aggregation correctness.

Each property generates random session data and verifies that
compute_stats() produces results matching a manual reference computation.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.stats_aggregator import compute_stats

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00"),
    min_size=1,
    max_size=20,
)

_emails = st.from_regex(r"[a-z]{3,8}@[a-z]{3,6}\.(com|org|net)", fullmatch=True)

_deal_statuses = st.sampled_from(["Negotiating", "Agreed", "Blocked", "Failed", "Confirming"])

_terminal_statuses = {"Agreed", "Blocked", "Failed"}

# Fixed "now" for deterministic time-window computation
_NOW = datetime(2026, 4, 11, 14, 0, 0, tzinfo=timezone.utc)
_TODAY_START = _NOW.replace(hour=0, minute=0, second=0, microsecond=0)
_SEVEN_DAYS_AGO = _NOW - timedelta(days=7)


def _created_at_strategy():
    """Generate created_at timestamps spread across today, last-7d, and older."""
    return st.one_of(
        # Today
        st.floats(min_value=0, max_value=50400).map(
            lambda s: (_TODAY_START + timedelta(seconds=s)).isoformat()
        ),
        # Last 7 days (but not today)
        st.floats(min_value=86400, max_value=604800).map(
            lambda s: (_NOW - timedelta(seconds=s)).isoformat()
        ),
        # Older than 7 days
        st.floats(min_value=700000, max_value=2000000).map(
            lambda s: (_NOW - timedelta(seconds=s)).isoformat()
        ),
    )


_model_ids = st.sampled_from(["gemini-2.5-flash", "claude-sonnet-4", "claude-3.5-sonnet", "llama-3.1"])

_agent_call = st.fixed_dictionaries({
    "model_id": _model_ids,
    "input_tokens": st.integers(min_value=0, max_value=5000),
    "output_tokens": st.integers(min_value=0, max_value=5000),
    "latency_ms": st.integers(min_value=0, max_value=10000),
})

_session = st.fixed_dictionaries({
    "session_id": st.uuids().map(str),
    "scenario_id": st.sampled_from(["talent-war", "mna-buyout", "b2b-sales", "custom-1"]),
    "owner_email": st.one_of(st.none(), _emails),
    "deal_status": _deal_statuses,
    "turn_count": st.integers(min_value=0, max_value=30),
    "total_tokens_used": st.integers(min_value=0, max_value=100000),
    "created_at": _created_at_strategy(),
    "agent_calls": st.lists(_agent_call, max_size=6),
    "endpoint_overrides": st.one_of(
        st.none(),
        st.just({}),
        st.dictionaries(keys=_safe_text, values=st.just("http://example.com/agent"), min_size=1, max_size=2),
    ),
})

_sessions_list = st.lists(_session, min_size=0, max_size=30)


# ---------------------------------------------------------------------------
# Helper: manual reference computation
# ---------------------------------------------------------------------------

def _parse_dt(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _manual_compute(sessions: list[dict]):
    """Reference implementation for verifying compute_stats."""
    users_today: set[str] = set()
    users_7d: set[str] = set()
    sims_today = sims_7d = active = 0
    outcomes_today: dict[str, int] = defaultdict(int)
    outcomes_7d: dict[str, int] = defaultdict(int)
    tokens_today = tokens_7d = 0
    turns_today: list[int] = []
    turns_7d: list[int] = []
    custom_agent_today = custom_agent_7d = custom_agent_all = 0
    scenario_today: dict[str, int] = defaultdict(int)
    scenario_7d: dict[str, int] = defaultdict(int)
    model_tokens_today: dict[str, int] = defaultdict(int)
    model_tokens_7d: dict[str, int] = defaultdict(int)
    model_rt_today: dict[str, list] = defaultdict(list)
    model_rt_7d: dict[str, list] = defaultdict(list)

    for s in sessions:
        dt = _parse_dt(s["created_at"])
        status = s["deal_status"]
        email = s.get("owner_email") or ""
        is_terminal = status in _terminal_statuses
        in_today = dt is not None and dt >= _TODAY_START
        in_7d = dt is not None and dt >= _SEVEN_DAYS_AGO

        if status == "Negotiating":
            active += 1

        ep = s.get("endpoint_overrides")
        has_custom = bool(ep)
        if has_custom:
            custom_agent_all += 1

        if in_today:
            sims_today += 1
            tokens_today += s["total_tokens_used"]
            scenario_today[s["scenario_id"]] += 1
            if email:
                users_today.add(email)
            if is_terminal:
                outcomes_today[status] += 1
                turns_today.append(s["turn_count"])
            if has_custom:
                custom_agent_today += 1

        if in_7d:
            sims_7d += 1
            tokens_7d += s["total_tokens_used"]
            scenario_7d[s["scenario_id"]] += 1
            if email:
                users_7d.add(email)
            if is_terminal:
                outcomes_7d[status] += 1
                turns_7d.append(s["turn_count"])
            if has_custom:
                custom_agent_7d += 1

        for call in s.get("agent_calls", []):
            mid = call.get("model_id", "unknown")
            ct = (call.get("input_tokens", 0) or 0) + (call.get("output_tokens", 0) or 0)
            lat = call.get("latency_ms", 0) or 0
            if in_today:
                model_tokens_today[mid] += ct
                if lat > 0:
                    model_rt_today[mid].append(lat)
            if in_7d:
                model_tokens_7d[mid] += ct
                if lat > 0:
                    model_rt_7d[mid].append(lat)

    return {
        "users_today": users_today,
        "users_7d": users_7d,
        "sims_today": sims_today,
        "sims_7d": sims_7d,
        "active": active,
        "outcomes_today": dict(outcomes_today),
        "outcomes_7d": dict(outcomes_7d),
        "tokens_today": tokens_today,
        "tokens_7d": tokens_7d,
        "turns_today": turns_today,
        "turns_7d": turns_7d,
        "custom_agent_today": custom_agent_today,
        "custom_agent_7d": custom_agent_7d,
        "custom_agent_all": custom_agent_all,
        "scenario_today": dict(scenario_today),
        "scenario_7d": dict(scenario_7d),
        "model_tokens_today": dict(model_tokens_today),
        "model_tokens_7d": dict(model_tokens_7d),
        "model_rt_today": dict(model_rt_today),
        "model_rt_7d": dict(model_rt_7d),
    }


# ---------------------------------------------------------------------------
# Feature: 270_public-stats-dashboard, Property 1: Unique user count
# **Validates: Requirements 3.1, 3.2, 3.3**
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(sessions=_sessions_list)
@settings(max_examples=100)
def test_unique_user_count_equals_distinct_emails(sessions: list[dict]):
    """Property 1: Unique user count equals distinct emails in time window."""
    result = compute_stats(sessions, now=_NOW)
    ref = _manual_compute(sessions)

    assert result.unique_users_today == len(ref["users_today"])
    assert result.unique_users_7d == len(ref["users_7d"])


# ---------------------------------------------------------------------------
# Feature: 270_public-stats-dashboard, Property 2: Simulation counts
# **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(sessions=_sessions_list)
@settings(max_examples=100)
def test_simulation_counts_and_outcomes(sessions: list[dict]):
    """Property 2: Simulation counts and outcome breakdown match manual computation."""
    result = compute_stats(sessions, now=_NOW)
    ref = _manual_compute(sessions)

    assert result.simulations_today == ref["sims_today"]
    assert result.simulations_7d == ref["sims_7d"]
    assert result.active_simulations == ref["active"]

    assert result.outcomes_today.agreed == ref["outcomes_today"].get("Agreed", 0)
    assert result.outcomes_today.blocked == ref["outcomes_today"].get("Blocked", 0)
    assert result.outcomes_today.failed == ref["outcomes_today"].get("Failed", 0)

    assert result.outcomes_7d.agreed == ref["outcomes_7d"].get("Agreed", 0)
    assert result.outcomes_7d.blocked == ref["outcomes_7d"].get("Blocked", 0)
    assert result.outcomes_7d.failed == ref["outcomes_7d"].get("Failed", 0)


# ---------------------------------------------------------------------------
# Feature: 270_public-stats-dashboard, Property 3: Total token sum
# **Validates: Requirements 5.1, 5.2, 5.3**
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(sessions=_sessions_list)
@settings(max_examples=100)
def test_total_token_sum(sessions: list[dict]):
    """Property 3: Total token sum equals aggregate of session tokens in time window."""
    result = compute_stats(sessions, now=_NOW)
    ref = _manual_compute(sessions)

    assert result.total_tokens_today == ref["tokens_today"]
    assert result.total_tokens_7d == ref["tokens_7d"]


# ---------------------------------------------------------------------------
# Feature: 270_public-stats-dashboard, Property 4: Per-model token breakdown
# **Validates: Requirements 6.1, 6.2, 6.3**
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(sessions=_sessions_list)
@settings(max_examples=100)
def test_per_model_token_breakdown(sessions: list[dict]):
    """Property 4: Per-model token breakdown matches grouped aggregation."""
    result = compute_stats(sessions, now=_NOW)
    ref = _manual_compute(sessions)

    result_map = {m.model_id: m for m in result.model_tokens}
    all_models = set(ref["model_tokens_today"].keys()) | set(ref["model_tokens_7d"].keys())

    for mid in all_models:
        assert mid in result_map, f"Model {mid} missing from result"
        assert result_map[mid].tokens_today == ref["model_tokens_today"].get(mid, 0)
        assert result_map[mid].tokens_7d == ref["model_tokens_7d"].get(mid, 0)


# ---------------------------------------------------------------------------
# Feature: 270_public-stats-dashboard, Property 5: Per-model avg response time
# **Validates: Requirements 7.1, 7.2, 7.3**
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(sessions=_sessions_list)
@settings(max_examples=100)
def test_per_model_avg_response_time(sessions: list[dict]):
    """Property 5: Per-model average response time matches manual mean computation."""
    result = compute_stats(sessions, now=_NOW)
    ref = _manual_compute(sessions)

    result_map = {m.model_id: m for m in result.model_performance}
    all_models = set(ref["model_rt_today"].keys()) | set(ref["model_rt_7d"].keys())

    for mid in all_models:
        assert mid in result_map, f"Model {mid} missing from performance result"
        m = result_map[mid]

        rt_today = ref["model_rt_today"].get(mid, [])
        rt_7d = ref["model_rt_7d"].get(mid, [])

        if rt_today:
            expected = sum(rt_today) / len(rt_today)
            assert m.avg_response_time_today is not None
            assert abs(m.avg_response_time_today - expected) < 1e-6
        else:
            assert m.avg_response_time_today is None

        if rt_7d:
            expected = sum(rt_7d) / len(rt_7d)
            assert m.avg_response_time_7d is not None
            assert abs(m.avg_response_time_7d - expected) < 1e-6
        else:
            assert m.avg_response_time_7d is None


# ---------------------------------------------------------------------------
# Feature: 270_public-stats-dashboard, Property 6: Scenario popularity ranking
# **Validates: Requirements 8.1, 8.3**
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(sessions=_sessions_list)
@settings(max_examples=100)
def test_scenario_popularity_ranking(sessions: list[dict]):
    """Property 6: Scenario popularity is ranked descending by simulation count."""
    result = compute_stats(sessions, now=_NOW)
    ref = _manual_compute(sessions)

    # Verify descending order by 7d count
    counts_7d = [sp.count_7d for sp in result.scenario_popularity]
    assert counts_7d == sorted(counts_7d, reverse=True)

    # Verify counts match reference
    result_map = {sp.scenario_id: sp for sp in result.scenario_popularity}
    all_scenarios = set(ref["scenario_today"].keys()) | set(ref["scenario_7d"].keys())

    for sid in all_scenarios:
        assert sid in result_map, f"Scenario {sid} missing from result"
        assert result_map[sid].count_today == ref["scenario_today"].get(sid, 0)
        assert result_map[sid].count_7d == ref["scenario_7d"].get(sid, 0)


# ---------------------------------------------------------------------------
# Feature: 270_public-stats-dashboard, Property 7: Average turns
# **Validates: Requirements 9.1, 9.2, 9.3**
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(sessions=_sessions_list)
@settings(max_examples=100)
def test_average_turns(sessions: list[dict]):
    """Property 7: Average turns equals mean of turn_count for terminal sessions."""
    result = compute_stats(sessions, now=_NOW)
    ref = _manual_compute(sessions)

    if ref["turns_today"]:
        expected = sum(ref["turns_today"]) / len(ref["turns_today"])
        assert result.avg_turns_today is not None
        assert abs(result.avg_turns_today - expected) < 1e-6
    else:
        assert result.avg_turns_today is None

    if ref["turns_7d"]:
        expected = sum(ref["turns_7d"]) / len(ref["turns_7d"])
        assert result.avg_turns_7d is not None
        assert abs(result.avg_turns_7d - expected) < 1e-6
    else:
        assert result.avg_turns_7d is None


# ---------------------------------------------------------------------------
# Feature: 270_public-stats-dashboard, Property 11: Custom agent session classification
# **Validates: Requirements 16.1, 16.2, 16.3, 16.4**
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(sessions=_sessions_list)
@settings(max_examples=100)
def test_custom_agent_session_classification(sessions: list[dict]):
    """Property 11: Custom agent session classification matches endpoint_overrides presence."""
    result = compute_stats(sessions, now=_NOW)
    ref = _manual_compute(sessions)

    assert result.custom_agent_sessions_today == ref["custom_agent_today"]
    assert result.custom_agent_sessions_7d == ref["custom_agent_7d"]
    assert result.custom_agent_sessions_all_time == ref["custom_agent_all"]
