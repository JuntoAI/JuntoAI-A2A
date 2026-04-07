"""Integration tests: verify usage_summary is present in NegotiationCompleteEvent.final_summary.

Tests that _snapshot_to_events correctly includes usage_summary alongside
ai_tokens_used in the final_summary dict for all terminal states.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.events import NegotiationCompleteEvent
from app.routers.negotiation import _snapshot_to_events


def _make_agent_call(
    agent_role: str,
    agent_type: str = "negotiator",
    model_id: str = "gemini-3-flash-preview",
    input_tokens: int = 80,
    output_tokens: int = 40,
    latency_ms: int = 200,
    error: bool = False,
    turn_number: int = 1,
    timestamp: str | None = None,
) -> dict:
    """Build a single AgentCallRecord dict."""
    return {
        "agent_role": agent_role,
        "agent_type": agent_type,
        "model_id": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "error": error,
        "turn_number": turn_number,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Test: usage_summary present when agent_calls has data (history-present path)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_usage_summary_in_final_summary_with_agent_calls():
    """_snapshot_to_events includes usage_summary in final_summary when
    the session has agent_calls data and reaches a terminal state via
    the history-present code path."""
    agent_calls = [
        _make_agent_call("Buyer", input_tokens=80, output_tokens=40, turn_number=1),
        _make_agent_call("Seller", input_tokens=90, output_tokens=45, turn_number=2),
    ]

    snapshot = {
        "agent_node": {
            "history": [
                {
                    "role": "Seller",
                    "agent_type": "negotiator",
                    "turn_number": 2,
                    "content": {
                        "inner_thought": "close enough",
                        "public_message": "I accept at $102k",
                        "proposed_price": 102000.0,
                    },
                }
            ],
            "deal_status": "Agreed",
            "current_offer": 102000.0,
            "turn_count": 2,
            "warning_count": 0,
            "total_tokens_used": 255,
            "agent_calls": agent_calls,
            "agent_states": {},
        }
    }

    events = _snapshot_to_events(snapshot, "test-session-001")

    # Find the NegotiationCompleteEvent
    complete_events = [e for e in events if isinstance(e, NegotiationCompleteEvent)]
    assert len(complete_events) == 1

    final_summary = complete_events[0].final_summary

    # usage_summary must be present
    assert "usage_summary" in final_summary
    usage = final_summary["usage_summary"]

    # Verify structure has expected top-level keys
    assert "per_persona" in usage
    assert "per_model" in usage
    assert "total_tokens" in usage
    assert "total_calls" in usage

    # Verify aggregation matches input
    assert usage["total_calls"] == 2
    assert usage["total_input_tokens"] == 80 + 90
    assert usage["total_output_tokens"] == 40 + 45
    assert usage["total_tokens"] == (80 + 90) + (40 + 45)

    # Per-persona: should have Buyer and Seller
    persona_roles = {p["agent_role"] for p in usage["per_persona"]}
    assert persona_roles == {"Buyer", "Seller"}


# ---------------------------------------------------------------------------
# Test: ai_tokens_used still populated alongside usage_summary
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ai_tokens_used_still_populated_alongside_usage_summary():
    """ai_tokens_used continues to be populated from total_tokens_used
    even when usage_summary is present (backward compatibility)."""
    agent_calls = [
        _make_agent_call("Buyer", input_tokens=100, output_tokens=50),
    ]

    snapshot = {
        "agent_node": {
            "history": [
                {
                    "role": "Buyer",
                    "agent_type": "negotiator",
                    "turn_number": 1,
                    "content": {
                        "inner_thought": "offering",
                        "public_message": "$100k",
                        "proposed_price": 100000.0,
                    },
                }
            ],
            "deal_status": "Failed",
            "current_offer": 100000.0,
            "turn_count": 10,
            "max_turns": 10,
            "warning_count": 0,
            "total_tokens_used": 999,
            "agent_calls": agent_calls,
            "agent_states": {},
        }
    }

    events = _snapshot_to_events(snapshot, "test-session-002")
    complete_events = [e for e in events if isinstance(e, NegotiationCompleteEvent)]
    assert len(complete_events) == 1

    final_summary = complete_events[0].final_summary

    # Both fields must coexist
    assert "ai_tokens_used" in final_summary
    assert "usage_summary" in final_summary

    # ai_tokens_used comes from total_tokens_used (the old field)
    assert final_summary["ai_tokens_used"] == 999

    # usage_summary is computed from agent_calls (the new field)
    assert final_summary["usage_summary"]["total_tokens"] == 150


# ---------------------------------------------------------------------------
# Test: usage_summary present with zero values when agent_calls is missing
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_usage_summary_zero_values_when_agent_calls_missing():
    """When agent_calls is absent from state (pre-Spec-145 sessions),
    usage_summary is still present with all-zero values."""
    snapshot = {
        "dispatcher": {
            "history": [],
            "deal_status": "Failed",
            "current_offer": 0,
            "turn_count": 10,
            "max_turns": 10,
            "warning_count": 0,
            "total_tokens_used": 500,
            # No agent_calls key at all
            "agent_states": {},
        }
    }

    events = _snapshot_to_events(snapshot, "test-session-003")
    complete_events = [e for e in events if isinstance(e, NegotiationCompleteEvent)]
    assert len(complete_events) == 1

    final_summary = complete_events[0].final_summary

    assert "usage_summary" in final_summary
    usage = final_summary["usage_summary"]

    # All numeric fields should be zero
    assert usage["total_tokens"] == 0
    assert usage["total_calls"] == 0
    assert usage["total_errors"] == 0
    assert usage["total_input_tokens"] == 0
    assert usage["total_output_tokens"] == 0
    assert usage["avg_latency_ms"] == 0
    assert usage["negotiation_duration_ms"] == 0

    # Empty breakdowns
    assert usage["per_persona"] == []
    assert usage["per_model"] == []

    # ai_tokens_used should still be populated from total_tokens_used
    assert final_summary["ai_tokens_used"] == 500


# ---------------------------------------------------------------------------
# Test: dispatcher empty-history path also includes usage_summary
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_usage_summary_in_dispatcher_empty_history_path():
    """The dispatcher early-exit path (empty history, terminal deal_status)
    also includes usage_summary in final_summary."""
    agent_calls = [
        _make_agent_call("Buyer", input_tokens=60, output_tokens=30, turn_number=1),
        _make_agent_call("Seller", input_tokens=70, output_tokens=35, turn_number=2),
    ]

    snapshot = {
        "dispatcher": {
            "history": [],  # Empty — dispatcher path
            "deal_status": "Agreed",
            "current_offer": 150000.0,
            "turn_count": 2,
            "warning_count": 0,
            "total_tokens_used": 195,
            "agent_calls": agent_calls,
            "agent_states": {},
        }
    }

    events = _snapshot_to_events(snapshot, "test-session-004")
    complete_events = [e for e in events if isinstance(e, NegotiationCompleteEvent)]
    assert len(complete_events) == 1

    final_summary = complete_events[0].final_summary

    assert "usage_summary" in final_summary
    assert "ai_tokens_used" in final_summary
    assert final_summary["usage_summary"]["total_calls"] == 2
    assert final_summary["ai_tokens_used"] == 195
