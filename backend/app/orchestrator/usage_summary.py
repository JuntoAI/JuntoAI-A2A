"""Pure aggregation function for LLM usage summary statistics.

Consumes the agent_calls telemetry array (Spec 145) and produces
a UsageSummary dict with per-persona, per-model, and session-wide totals.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.models.usage_summary import (
    ModelUsageStats,
    PersonaUsageStats,
    UsageSummary,
)


def compute_usage_summary(agent_calls: list[dict]) -> dict:
    """Aggregate AgentCallRecord dicts into a UsageSummary dict.

    Pure function — no side effects, no DB queries, no LLM calls.

    Args:
        agent_calls: List of AgentCallRecord dicts from session telemetry.

    Returns:
        ``UsageSummary.model_dump()`` dict ready for JSON serialization.
    """
    if not agent_calls:
        return UsageSummary().model_dump()

    # --- group by agent_role (persona) ---
    persona_groups: dict[str, list[dict]] = defaultdict(list)
    model_groups: dict[str, list[dict]] = defaultdict(list)

    for record in agent_calls:
        persona_groups[record["agent_role"]].append(record)
        model_groups[record["model_id"]].append(record)

    per_persona = [
        _build_persona_stats(role, records)
        for role, records in persona_groups.items()
    ]

    per_model = [
        _build_model_stats(model_id, records)
        for model_id, records in model_groups.items()
    ]

    # --- session-wide totals ---
    total_input = sum(r["input_tokens"] for r in agent_calls)
    total_output = sum(r["output_tokens"] for r in agent_calls)
    total_tokens = total_input + total_output
    total_calls = len(agent_calls)
    total_errors = sum(1 for r in agent_calls if r.get("error"))
    avg_latency = (
        round(sum(r["latency_ms"] for r in agent_calls) / total_calls)
        if total_calls
        else 0
    )
    duration = _compute_duration_ms(agent_calls)

    summary = UsageSummary(
        per_persona=per_persona,
        per_model=per_model,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_tokens,
        total_calls=total_calls,
        total_errors=total_errors,
        avg_latency_ms=avg_latency,
        negotiation_duration_ms=duration,
    )
    return summary.model_dump()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_persona_stats(role: str, records: list[dict]) -> PersonaUsageStats:
    """Build PersonaUsageStats from a group of records sharing the same agent_role."""
    first = records[0]
    total_input = sum(r["input_tokens"] for r in records)
    total_output = sum(r["output_tokens"] for r in records)
    total_tokens = total_input + total_output
    call_count = len(records)
    error_count = sum(1 for r in records if r.get("error"))
    non_error = call_count - error_count
    avg_latency = round(sum(r["latency_ms"] for r in records) / call_count) if call_count else 0
    tokens_per_msg = round(total_tokens / non_error) if non_error > 0 else 0

    return PersonaUsageStats(
        agent_role=role,
        agent_type=first["agent_type"],
        model_id=first["model_id"],
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_tokens,
        call_count=call_count,
        error_count=error_count,
        avg_latency_ms=avg_latency,
        tokens_per_message=tokens_per_msg,
    )


def _build_model_stats(model_id: str, records: list[dict]) -> ModelUsageStats:
    """Build ModelUsageStats from a group of records sharing the same model_id."""
    total_input = sum(r["input_tokens"] for r in records)
    total_output = sum(r["output_tokens"] for r in records)
    total_tokens = total_input + total_output
    call_count = len(records)
    error_count = sum(1 for r in records if r.get("error"))
    non_error = call_count - error_count
    avg_latency = round(sum(r["latency_ms"] for r in records) / call_count) if call_count else 0
    tokens_per_msg = round(total_tokens / non_error) if non_error > 0 else 0

    return ModelUsageStats(
        model_id=model_id,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_tokens,
        call_count=call_count,
        error_count=error_count,
        avg_latency_ms=avg_latency,
        tokens_per_message=tokens_per_msg,
    )


def _compute_duration_ms(agent_calls: list[dict]) -> int:
    """Compute negotiation duration from timestamp range.

    Returns 0 if ≤1 record or if any timestamps are missing/malformed.
    """
    if len(agent_calls) <= 1:
        return 0

    timestamps: list[datetime] = []
    for record in agent_calls:
        ts_str = record.get("timestamp")
        if not ts_str or not isinstance(ts_str, str):
            return 0
        try:
            timestamps.append(datetime.fromisoformat(ts_str))
        except (ValueError, TypeError):
            return 0

    if len(timestamps) < 2:
        return 0

    earliest = min(timestamps)
    latest = max(timestamps)
    delta = latest - earliest
    return max(0, int(delta.total_seconds() * 1000))
