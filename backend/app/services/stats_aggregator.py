"""Stats aggregation service — computes platform metrics from session data."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.models.stats import (
    ModelPerformance,
    ModelTokenBreakdown,
    OutcomeBreakdown,
    ScenarioPopularity,
    StatsResponse,
)

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"Agreed", "Blocked", "Failed"}


def _parse_created_at(value) -> datetime | None:
    """Best-effort parse of created_at to a UTC datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None
    return None


def compute_stats(sessions: list[dict], now: datetime | None = None) -> StatsResponse:
    """Compute all stats metrics from a list of session dicts.

    Args:
        sessions: Raw session documents (dicts).
        now: Override for current UTC time (useful for testing).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)

    # Buckets
    users_today: set[str] = set()
    users_7d: set[str] = set()
    sims_today = 0
    sims_7d = 0
    active_sims = 0
    outcomes_today: dict[str, int] = defaultdict(int)
    outcomes_7d: dict[str, int] = defaultdict(int)
    tokens_today = 0
    tokens_7d = 0

    # Per-model token tracking: model_id -> {today: int, 7d: int}
    model_token_map: dict[str, dict[str, int]] = defaultdict(lambda: {"today": 0, "7d": 0})
    # Per-model response times: model_id -> {today: [float], 7d: [float]}
    model_rt_map: dict[str, dict[str, list]] = defaultdict(lambda: {"today": [], "7d": []})

    # Scenario counts: scenario_id -> {today: int, 7d: int}
    scenario_map: dict[str, dict[str, int]] = defaultdict(lambda: {"today": 0, "7d": 0})

    # Turns for terminal sessions
    turns_today: list[int] = []
    turns_7d: list[int] = []

    # Custom agent sessions
    custom_agent_today = 0
    custom_agent_7d = 0
    custom_agent_all = 0

    for s in sessions:
        created_at = _parse_created_at(s.get("created_at"))
        deal_status = s.get("deal_status", "")
        email = s.get("owner_email", "") or ""
        total_tokens = s.get("total_tokens_used", 0) or 0
        scenario_id = s.get("scenario_id", "unknown")
        turn_count = s.get("turn_count", 0) or 0
        endpoint_overrides = s.get("endpoint_overrides")

        is_active = deal_status == "Negotiating"
        is_terminal = deal_status in TERMINAL_STATUSES

        if is_active:
            active_sims += 1

        # Custom agent session detection
        has_custom_agent = bool(endpoint_overrides)
        if has_custom_agent:
            custom_agent_all += 1

        in_today = created_at is not None and created_at >= today_start
        in_7d = created_at is not None and created_at >= seven_days_ago

        if in_today:
            sims_today += 1
            tokens_today += total_tokens
            scenario_map[scenario_id]["today"] += 1
            if email:
                users_today.add(email)
            if is_terminal:
                outcomes_today[deal_status] += 1
                turns_today.append(turn_count)
            if has_custom_agent:
                custom_agent_today += 1

        if in_7d:
            sims_7d += 1
            tokens_7d += total_tokens
            scenario_map[scenario_id]["7d"] += 1
            if email:
                users_7d.add(email)
            if is_terminal:
                outcomes_7d[deal_status] += 1
                turns_7d.append(turn_count)
            if has_custom_agent:
                custom_agent_7d += 1

        # Per-model token and response time aggregation from agent_calls
        agent_calls = s.get("agent_calls") or []
        for call in agent_calls:
            mid = call.get("model_id", "unknown")
            call_tokens = (call.get("input_tokens", 0) or 0) + (call.get("output_tokens", 0) or 0)
            latency_ms = call.get("latency_ms", 0) or 0

            if in_today:
                model_token_map[mid]["today"] += call_tokens
                if latency_ms > 0:
                    model_rt_map[mid]["today"].append(latency_ms)
            if in_7d:
                model_token_map[mid]["7d"] += call_tokens
                if latency_ms > 0:
                    model_rt_map[mid]["7d"].append(latency_ms)

    # Build model token breakdown
    model_tokens = sorted(
        [
            ModelTokenBreakdown(model_id=mid, tokens_today=d["today"], tokens_7d=d["7d"])
            for mid, d in model_token_map.items()
        ],
        key=lambda m: m.tokens_7d,
        reverse=True,
    )

    # Build model performance
    model_performance: list[ModelPerformance] = []
    all_model_ids = set(model_rt_map.keys())
    for mid in sorted(all_model_ids):
        rt = model_rt_map[mid]
        avg_today = (sum(rt["today"]) / len(rt["today"])) if rt["today"] else None
        avg_7d = (sum(rt["7d"]) / len(rt["7d"])) if rt["7d"] else None
        model_performance.append(
            ModelPerformance(
                model_id=mid,
                avg_response_time_today=avg_today,
                avg_response_time_7d=avg_7d,
            )
        )

    # Build scenario popularity (sorted descending by 7d count)
    scenario_popularity = sorted(
        [
            ScenarioPopularity(
                scenario_id=sid,
                scenario_name=sid,  # Use scenario_id as name for now
                count_today=d["today"],
                count_7d=d["7d"],
            )
            for sid, d in scenario_map.items()
        ],
        key=lambda sp: sp.count_7d,
        reverse=True,
    )

    return StatsResponse(
        unique_users_today=len(users_today),
        unique_users_7d=len(users_7d),
        simulations_today=sims_today,
        simulations_7d=sims_7d,
        active_simulations=active_sims,
        outcomes_today=OutcomeBreakdown(
            agreed=outcomes_today.get("Agreed", 0),
            blocked=outcomes_today.get("Blocked", 0),
            failed=outcomes_today.get("Failed", 0),
        ),
        outcomes_7d=OutcomeBreakdown(
            agreed=outcomes_7d.get("Agreed", 0),
            blocked=outcomes_7d.get("Blocked", 0),
            failed=outcomes_7d.get("Failed", 0),
        ),
        total_tokens_today=tokens_today,
        total_tokens_7d=tokens_7d,
        model_tokens=model_tokens,
        model_performance=model_performance,
        scenario_popularity=scenario_popularity,
        avg_turns_today=(sum(turns_today) / len(turns_today)) if turns_today else None,
        avg_turns_7d=(sum(turns_7d) / len(turns_7d)) if turns_7d else None,
        custom_scenarios_today=0,  # Populated separately for cloud mode
        custom_scenarios_7d=0,
        custom_scenarios_all_time=0,
        custom_agent_sessions_today=custom_agent_today,
        custom_agent_sessions_7d=custom_agent_7d,
        custom_agent_sessions_all_time=custom_agent_all,
        generated_at=now.isoformat(),
    )
