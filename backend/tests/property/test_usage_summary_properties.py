"""Property-based tests for LLM usage summary models.

Feature: 190_llm-usage-summary
Uses Hypothesis to verify universal invariants across generated inputs.
"""

from collections import defaultdict
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.usage_summary import ModelUsageStats, PersonaUsageStats, UsageSummary
from app.orchestrator.usage_summary import compute_usage_summary

# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs", "P")),
    min_size=1,
    max_size=50,
)

_agent_type = st.sampled_from(["negotiator", "regulator", "observer"])

_non_neg_int = st.integers(min_value=0, max_value=10_000_000)


@st.composite
def persona_usage_stats_strategy(draw):
    """Generate a random valid PersonaUsageStats instance."""
    total_input = draw(_non_neg_int)
    total_output = draw(_non_neg_int)
    return PersonaUsageStats(
        agent_role=draw(_safe_text),
        agent_type=draw(_agent_type),
        model_id=draw(_safe_text),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_input + total_output,
        call_count=draw(_non_neg_int),
        error_count=draw(_non_neg_int),
        avg_latency_ms=draw(_non_neg_int),
        tokens_per_message=draw(_non_neg_int),
    )


@st.composite
def model_usage_stats_strategy(draw):
    """Generate a random valid ModelUsageStats instance."""
    total_input = draw(_non_neg_int)
    total_output = draw(_non_neg_int)
    return ModelUsageStats(
        model_id=draw(_safe_text),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_input + total_output,
        call_count=draw(_non_neg_int),
        error_count=draw(_non_neg_int),
        avg_latency_ms=draw(_non_neg_int),
        tokens_per_message=draw(_non_neg_int),
    )


@st.composite
def usage_summary_strategy(draw):
    """Generate a random valid UsageSummary instance with nested models."""
    personas = draw(st.lists(persona_usage_stats_strategy(), min_size=0, max_size=5))
    models = draw(st.lists(model_usage_stats_strategy(), min_size=0, max_size=5))
    total_input = draw(_non_neg_int)
    total_output = draw(_non_neg_int)
    return UsageSummary(
        per_persona=personas,
        per_model=models,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_input + total_output,
        total_calls=draw(_non_neg_int),
        total_errors=draw(_non_neg_int),
        avg_latency_ms=draw(_non_neg_int),
        negotiation_duration_ms=draw(_non_neg_int),
    )


# ---------------------------------------------------------------------------
# Feature: 190_llm-usage-summary
# Property 2: UsageSummary JSON round-trip
# **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
#
# For any valid UsageSummary instance (including nested PersonaUsageStats
# and ModelUsageStats), serializing via model_dump_json() and deserializing
# via UsageSummary.model_validate_json() SHALL produce an equal object.
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(summary=usage_summary_strategy())
def test_usage_summary_round_trip(summary: UsageSummary):
    """Serializing and deserializing any valid UsageSummary must produce an equal object.

    Feature: 190_llm-usage-summary, Property 2: UsageSummary JSON round-trip
    """
    json_str = summary.model_dump_json()
    restored = UsageSummary.model_validate_json(json_str)
    assert restored == summary


# ---------------------------------------------------------------------------
# Strategy: AgentCallRecord dicts for aggregation tests
# ---------------------------------------------------------------------------

_agent_roles = st.sampled_from(["Buyer", "Seller", "Regulator"])
_model_ids = st.sampled_from(["gemini-3-flash-preview", "claude-3.5-sonnet", "gpt-4o"])


@st.composite
def agent_call_record_strategy(draw):
    """Generate a random AgentCallRecord dict with valid field ranges."""
    dt = draw(
        st.datetimes(
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2025, 12, 31),
            timezones=st.just(timezone.utc),
        )
    )
    return {
        "agent_role": draw(_agent_roles),
        "agent_type": draw(_agent_type),
        "model_id": draw(_model_ids),
        "latency_ms": draw(st.integers(min_value=0, max_value=10_000)),
        "input_tokens": draw(st.integers(min_value=0, max_value=100_000)),
        "output_tokens": draw(st.integers(min_value=0, max_value=100_000)),
        "error": draw(st.booleans()),
        "turn_number": draw(st.integers(min_value=1, max_value=50)),
        "timestamp": dt.isoformat(),
    }


# ---------------------------------------------------------------------------
# Feature: 190_llm-usage-summary
# Property 1: Aggregation correctness
# **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6**
#
# For any list of AgentCallRecord dicts, compute_usage_summary SHALL produce
# per-persona sums, per-model sums, session totals, and duration that match
# manual computation from the raw records.
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(records=st.lists(agent_call_record_strategy(), min_size=0, max_size=20))
def test_aggregation_correctness(records: list[dict]):
    """Per-persona sums, per-model sums, session totals, and duration must match manual computation.

    Feature: 190_llm-usage-summary, Property 1: Aggregation correctness
    """
    result = compute_usage_summary(records)

    # --- session-wide totals ---
    expected_input = sum(r["input_tokens"] for r in records)
    expected_output = sum(r["output_tokens"] for r in records)
    expected_tokens = expected_input + expected_output
    expected_calls = len(records)
    expected_errors = sum(1 for r in records if r["error"])

    assert result["total_input_tokens"] == expected_input
    assert result["total_output_tokens"] == expected_output
    assert result["total_tokens"] == expected_tokens
    assert result["total_calls"] == expected_calls
    assert result["total_errors"] == expected_errors

    if expected_calls > 0:
        expected_avg_latency = round(
            sum(r["latency_ms"] for r in records) / expected_calls
        )
        assert result["avg_latency_ms"] == expected_avg_latency

    # --- per-persona checks ---
    groups_by_role: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups_by_role[r["agent_role"]].append(r)

    persona_lookup = {p["agent_role"]: p for p in result["per_persona"]}
    assert set(persona_lookup.keys()) == set(groups_by_role.keys())

    for role, group in groups_by_role.items():
        p = persona_lookup[role]
        g_input = sum(r["input_tokens"] for r in group)
        g_output = sum(r["output_tokens"] for r in group)
        g_total = g_input + g_output
        g_calls = len(group)
        g_errors = sum(1 for r in group if r["error"])
        g_non_error = g_calls - g_errors
        g_tpm = round(g_total / g_non_error) if g_non_error > 0 else 0

        assert p["total_input_tokens"] == g_input
        assert p["total_output_tokens"] == g_output
        assert p["total_tokens"] == g_total
        assert p["call_count"] == g_calls
        assert p["error_count"] == g_errors
        assert p["tokens_per_message"] == g_tpm

    # --- per-model checks ---
    groups_by_model: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups_by_model[r["model_id"]].append(r)

    model_lookup = {m["model_id"]: m for m in result["per_model"]}
    assert set(model_lookup.keys()) == set(groups_by_model.keys())

    for model_id, group in groups_by_model.items():
        m = model_lookup[model_id]
        g_input = sum(r["input_tokens"] for r in group)
        g_output = sum(r["output_tokens"] for r in group)
        g_total = g_input + g_output
        g_calls = len(group)
        g_errors = sum(1 for r in group if r["error"])
        g_non_error = g_calls - g_errors
        g_tpm = round(g_total / g_non_error) if g_non_error > 0 else 0

        assert m["total_input_tokens"] == g_input
        assert m["total_output_tokens"] == g_output
        assert m["total_tokens"] == g_total
        assert m["call_count"] == g_calls
        assert m["error_count"] == g_errors
        assert m["tokens_per_message"] == g_tpm

    # --- negotiation_duration_ms ---
    if len(records) <= 1:
        assert result["negotiation_duration_ms"] == 0
    else:
        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in records]
        expected_duration = int(
            (max(timestamps) - min(timestamps)).total_seconds() * 1000
        )
        assert result["negotiation_duration_ms"] == expected_duration
