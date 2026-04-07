"""Unit tests for the usage summary aggregator edge cases.

Tests: empty input, all-error persona, single record, missing agent_calls field.
"""

import pytest

from app.orchestrator.usage_summary import compute_usage_summary


def _make_record(**overrides):
    """Build a minimal AgentCallRecord dict with sensible defaults."""
    defaults = {
        "agent_role": "Buyer",
        "agent_type": "negotiator",
        "model_id": "gemini-2.5-flash",
        "latency_ms": 200,
        "input_tokens": 100,
        "output_tokens": 50,
        "error": False,
        "turn_number": 1,
        "timestamp": "2025-01-15T10:00:00+00:00",
    }
    defaults.update(overrides)
    return defaults


@pytest.mark.unit
class TestEmptyInput:
    """Requirement 1.5 — empty agent_calls → zero-valued summary."""

    def test_empty_input(self):
        result = compute_usage_summary([])

        assert result["total_input_tokens"] == 0
        assert result["total_output_tokens"] == 0
        assert result["total_tokens"] == 0
        assert result["total_calls"] == 0
        assert result["total_errors"] == 0
        assert result["avg_latency_ms"] == 0
        assert result["negotiation_duration_ms"] == 0
        assert result["per_persona"] == []
        assert result["per_model"] == []


@pytest.mark.unit
class TestAllErrorPersona:
    """Requirement 1.6 — all-error persona → tokens_per_message = 0 (no div-by-zero)."""

    def test_all_error_persona(self):
        records = [
            _make_record(error=True, turn_number=1, timestamp="2025-01-15T10:00:00+00:00"),
            _make_record(error=True, turn_number=2, timestamp="2025-01-15T10:00:01+00:00"),
        ]
        result = compute_usage_summary(records)

        assert len(result["per_persona"]) == 1
        persona = result["per_persona"][0]
        assert persona["tokens_per_message"] == 0
        assert persona["error_count"] == 2
        assert persona["call_count"] == 2


@pytest.mark.unit
class TestSingleRecord:
    """Single AgentCallRecord → negotiation_duration_ms = 0."""

    def test_single_record(self):
        result = compute_usage_summary([_make_record()])

        assert result["negotiation_duration_ms"] == 0
        assert result["total_calls"] == 1
        assert len(result["per_persona"]) == 1
        assert len(result["per_model"]) == 1


@pytest.mark.unit
class TestMissingAgentCallsField:
    """Requirement 6.1 — missing agent_calls field treated as empty list."""

    def test_missing_agent_calls_field(self):
        state: dict = {}
        agent_calls = state.get("agent_calls", [])
        result = compute_usage_summary(agent_calls)

        assert result["total_calls"] == 0
        assert result["total_tokens"] == 0
        assert result["per_persona"] == []
        assert result["per_model"] == []
        assert result["negotiation_duration_ms"] == 0
