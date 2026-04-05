"""Unit tests for AgentCallRecord validation and agent_calls state plumbing.

Validates: Requirements 1.1, 2.1, 2.2, 2.3, 2.4, 4.3
"""

import pytest
from pydantic import ValidationError

from app.models.negotiation import NegotiationStateModel
from app.orchestrator.converters import from_pydantic, to_pydantic
from app.orchestrator.outputs import AgentCallRecord
from app.orchestrator.state import NegotiationState, create_initial_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_record(**overrides) -> dict:
    defaults = {
        "agent_role": "Buyer",
        "agent_type": "negotiator",
        "model_id": "gemini-3-flash-preview",
        "latency_ms": 120,
        "input_tokens": 50,
        "output_tokens": 30,
        "error": False,
        "turn_number": 1,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }
    defaults.update(overrides)
    return defaults


def _make_config() -> dict:
    return {
        "id": "scenario-001",
        "agents": [
            {"role": "Buyer", "name": "Alice", "type": "negotiator", "model_id": "gemini-3-flash-preview"},
            {"role": "Seller", "name": "Bob", "type": "negotiator", "model_id": "gemini-3-flash-preview"},
        ],
        "negotiation_params": {"max_turns": 10, "turn_order": ["Buyer", "Seller"]},
    }


def _full_state(**overrides) -> dict:
    """Minimal NegotiationState dict with all required fields."""
    defaults: dict = {
        "session_id": "sess-1",
        "scenario_id": "scen-1",
        "turn_count": 0,
        "max_turns": 10,
        "current_speaker": "Buyer",
        "deal_status": "Negotiating",
        "current_offer": 0.0,
        "history": [],
        "hidden_context": {},
        "warning_count": 0,
        "agreement_threshold": 5000.0,
        "scenario_config": {},
        "turn_order": ["Buyer"],
        "turn_order_index": 0,
        "agent_states": {},
        "active_toggles": [],
        "total_tokens_used": 0,
        "stall_diagnosis": None,
        "custom_prompts": {},
        "model_overrides": {},
        "structured_memory_enabled": False,
        "structured_memory_roles": [],
        "agent_memories": {},
        "milestone_summaries_enabled": False,
        "milestone_summaries": {},
        "sliding_window_size": 3,
        "milestone_interval": 4,
        "no_memory_roles": [],
        "agent_calls": [],
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# AgentCallRecord validation — Req 1.1
# ---------------------------------------------------------------------------


class TestAgentCallRecordValidation:
    """AgentCallRecord rejects invalid field values."""

    def test_rejects_negative_latency_ms(self):
        with pytest.raises(ValidationError):
            AgentCallRecord(**_valid_record(latency_ms=-1))

    def test_rejects_negative_input_tokens(self):
        with pytest.raises(ValidationError):
            AgentCallRecord(**_valid_record(input_tokens=-1))

    def test_rejects_negative_output_tokens(self):
        with pytest.raises(ValidationError):
            AgentCallRecord(**_valid_record(output_tokens=-1))

    def test_accepts_zero_values(self):
        record = AgentCallRecord(**_valid_record(latency_ms=0, input_tokens=0, output_tokens=0))
        assert record.latency_ms == 0
        assert record.input_tokens == 0
        assert record.output_tokens == 0

    def test_rejects_negative_turn_number(self):
        with pytest.raises(ValidationError):
            AgentCallRecord(**_valid_record(turn_number=-1))


# ---------------------------------------------------------------------------
# NegotiationStateModel defaults — Req 2.3
# ---------------------------------------------------------------------------


class TestNegotiationStateModelDefaults:
    """NegotiationStateModel defaults agent_calls to []."""

    def test_agent_calls_defaults_to_empty_list(self):
        model = NegotiationStateModel(
            session_id="s",
            scenario_id="sc",
            turn_order=["Buyer"],
            turn_order_index=0,
            agent_states={},
        )
        assert model.agent_calls == []

    def test_agent_calls_accepts_records(self):
        records = [_valid_record()]
        model = NegotiationStateModel(
            session_id="s",
            scenario_id="sc",
            turn_order=["Buyer"],
            turn_order_index=0,
            agent_states={},
            agent_calls=records,
        )
        assert model.agent_calls == records


# ---------------------------------------------------------------------------
# create_initial_state — Req 2.2
# ---------------------------------------------------------------------------


class TestCreateInitialStateAgentCalls:
    """create_initial_state() includes agent_calls=[]."""

    def test_agent_calls_initialized_empty(self):
        state = create_initial_state("sess-1", _make_config())
        assert state["agent_calls"] == []

    def test_agent_calls_is_list_type(self):
        state = create_initial_state("sess-2", _make_config())
        assert isinstance(state["agent_calls"], list)


# ---------------------------------------------------------------------------
# Converters — Req 2.4, 4.3
# ---------------------------------------------------------------------------


class TestConverterAgentCalls:
    """Converters map agent_calls correctly; missing field defaults to []."""

    def test_to_pydantic_maps_agent_calls(self):
        records = [_valid_record(), _valid_record(agent_role="Seller")]
        state = _full_state(agent_calls=records)
        model = to_pydantic(state)  # type: ignore[arg-type]
        assert model.agent_calls == records

    def test_from_pydantic_maps_agent_calls(self):
        records = [_valid_record()]
        pydantic_model = NegotiationStateModel(
            session_id="s",
            scenario_id="sc",
            turn_order=["Buyer"],
            turn_order_index=0,
            agent_states={},
            agent_calls=records,
        )
        state = from_pydantic(pydantic_model)
        assert state["agent_calls"] == records

    def test_round_trip_preserves_agent_calls(self):
        records = [_valid_record(), _valid_record(latency_ms=999, error=True)]
        state = _full_state(agent_calls=records)
        model = to_pydantic(state)  # type: ignore[arg-type]
        restored = from_pydantic(model)
        assert restored["agent_calls"] == records

    def test_to_pydantic_defaults_missing_agent_calls(self):
        """Backward compat: state dict without agent_calls key defaults to []."""
        legacy_state = _full_state()
        del legacy_state["agent_calls"]
        model = to_pydantic(legacy_state)  # type: ignore[arg-type]
        assert model.agent_calls == []

    def test_empty_agent_calls_round_trip(self):
        state = _full_state(agent_calls=[])
        model = to_pydantic(state)  # type: ignore[arg-type]
        restored = from_pydantic(model)
        assert restored["agent_calls"] == []
