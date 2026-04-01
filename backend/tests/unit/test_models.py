"""Tests for Pydantic models: defaults, validation, round-trip serialization."""

import pytest
from pydantic import ValidationError

from app.models.events import (
    AgentMessageEvent,
    AgentThoughtEvent,
    NegotiationCompleteEvent,
    StreamErrorEvent,
)
from app.models.negotiation import NegotiationStateModel


class TestNegotiationStateModelDefaults:
    def test_defaults(self):
        m = NegotiationStateModel(session_id="s1", scenario_id="sc1")
        assert m.turn_count == 0
        assert m.max_turns == 15
        assert m.current_speaker == "Buyer"
        assert m.deal_status == "Negotiating"
        assert m.current_offer == 0.0
        assert m.history == []
        assert m.warning_count == 0
        assert m.hidden_context == {}
        assert m.agreement_threshold == 1000000.0
        assert m.active_toggles == []
        assert m.turn_order == []
        assert m.turn_order_index == 0
        assert m.agent_states == {}

    def test_deal_status_rejects_invalid(self):
        with pytest.raises(ValidationError):
            NegotiationStateModel(
                session_id="s1", scenario_id="sc1", deal_status="InvalidStatus"
            )

    def test_deal_status_accepts_all_valid(self):
        for status in ("Negotiating", "Agreed", "Blocked", "Failed"):
            m = NegotiationStateModel(
                session_id="s1", scenario_id="sc1", deal_status=status
            )
            assert m.deal_status == status


class TestEventModelsInstantiate:
    def test_agent_thought_event(self):
        e = AgentThoughtEvent(
            event_type="agent_thought",
            agent_name="Buyer",
            inner_thought="thinking",
            turn_number=1,
        )
        assert e.event_type == "agent_thought"

    def test_agent_message_event(self):
        e = AgentMessageEvent(
            event_type="agent_message",
            agent_name="Seller",
            public_message="offer",
            turn_number=2,
        )
        assert e.event_type == "agent_message"
        assert e.proposed_price is None

    def test_negotiation_complete_event(self):
        e = NegotiationCompleteEvent(
            event_type="negotiation_complete",
            session_id="s1",
            deal_status="Agreed",
            final_summary={"price": 100},
        )
        assert e.event_type == "negotiation_complete"

    def test_stream_error_event(self):
        e = StreamErrorEvent(event_type="error", message="boom")
        assert e.event_type == "error"


class TestJsonRoundTrip:
    def test_negotiation_state_round_trip(self):
        original = NegotiationStateModel(session_id="s1", scenario_id="sc1")
        restored = NegotiationStateModel.model_validate_json(
            original.model_dump_json()
        )
        assert restored == original

    def test_agent_thought_round_trip(self):
        original = AgentThoughtEvent(
            event_type="agent_thought",
            agent_name="Buyer",
            inner_thought="hmm",
            turn_number=0,
        )
        restored = AgentThoughtEvent.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_agent_message_round_trip(self):
        original = AgentMessageEvent(
            event_type="agent_message",
            agent_name="Seller",
            public_message="deal",
            turn_number=3,
            proposed_price=50.0,
        )
        restored = AgentMessageEvent.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_negotiation_complete_round_trip(self):
        original = NegotiationCompleteEvent(
            event_type="negotiation_complete",
            session_id="s1",
            deal_status="Failed",
            final_summary={"reason": "timeout"},
        )
        restored = NegotiationCompleteEvent.model_validate_json(
            original.model_dump_json()
        )
        assert restored == original

    def test_stream_error_round_trip(self):
        original = StreamErrorEvent(event_type="error", message="oops")
        restored = StreamErrorEvent.model_validate_json(original.model_dump_json())
        assert restored == original
