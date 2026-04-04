"""Unit tests for NegotiationStateModel backward compatibility with milestone fields.

# Feature: 110_hybrid-agent-memory, Task 3.3
# Requirements: 2.8, 2.9, 9.5
"""

import pytest

from app.models.negotiation import NegotiationStateModel


class TestNegotiationStateModelBackwardCompat:
    """Test that old Firestore documents without milestone fields load cleanly."""

    def test_missing_milestone_fields_uses_defaults(self):
        """A dict without any milestone fields validates and uses defaults."""
        data = {
            "session_id": "sess-old",
            "scenario_id": "scenario-old",
            "turn_count": 5,
            "max_turns": 10,
        }
        model = NegotiationStateModel(**data)

        assert model.milestone_summaries_enabled is False
        assert model.milestone_summaries == {}
        assert model.sliding_window_size == 3
        assert model.milestone_interval == 4

    def test_missing_only_some_milestone_fields(self):
        """A dict with some milestone fields but not all still validates."""
        data = {
            "session_id": "sess-partial",
            "scenario_id": "scenario-partial",
            "milestone_summaries_enabled": True,
        }
        model = NegotiationStateModel(**data)

        assert model.milestone_summaries_enabled is True
        assert model.milestone_summaries == {}
        assert model.sliding_window_size == 3
        assert model.milestone_interval == 4

    def test_explicit_milestone_values_preserved(self):
        """Explicit milestone field values are preserved, not overwritten by defaults."""
        summaries = {
            "Buyer": [{"turn_number": 4, "summary": "Good progress"}],
        }
        data = {
            "session_id": "sess-explicit",
            "scenario_id": "scenario-explicit",
            "milestone_summaries_enabled": True,
            "milestone_summaries": summaries,
            "sliding_window_size": 5,
            "milestone_interval": 6,
        }
        model = NegotiationStateModel(**data)

        assert model.milestone_summaries_enabled is True
        assert model.milestone_summaries == summaries
        assert model.sliding_window_size == 5
        assert model.milestone_interval == 6

    def test_extra_unknown_fields_ignored(self):
        """Unknown fields from Firestore are silently ignored (extra='ignore')."""
        data = {
            "session_id": "sess-extra",
            "scenario_id": "scenario-extra",
            "some_future_field": "should be ignored",
        }
        model = NegotiationStateModel(**data)
        assert not hasattr(model, "some_future_field")

    def test_sliding_window_size_minimum_validation(self):
        """sliding_window_size must be >= 1."""
        with pytest.raises(Exception):
            NegotiationStateModel(
                session_id="sess-val",
                scenario_id="scenario-val",
                sliding_window_size=0,
            )

    def test_milestone_interval_minimum_validation(self):
        """milestone_interval must be >= 2."""
        with pytest.raises(Exception):
            NegotiationStateModel(
                session_id="sess-val",
                scenario_id="scenario-val",
                milestone_interval=1,
            )

    def test_full_legacy_document_without_any_new_fields(self):
        """Simulate a complete legacy Firestore document — no milestone or structured memory fields."""
        data = {
            "session_id": "sess-legacy",
            "scenario_id": "scenario-legacy",
            "turn_count": 3,
            "max_turns": 15,
            "current_speaker": "Seller",
            "deal_status": "Negotiating",
            "current_offer": 50000.0,
            "history": [{"role": "Buyer", "content": "I offer 50k"}],
            "warning_count": 0,
            "hidden_context": {},
            "agreement_threshold": 100000.0,
            "active_toggles": ["toggle_a"],
            "turn_order": ["Buyer", "Seller"],
            "turn_order_index": 1,
            "agent_states": {},
            "total_tokens_used": 1200,
        }
        model = NegotiationStateModel(**data)

        # All legacy fields preserved
        assert model.session_id == "sess-legacy"
        assert model.turn_count == 3
        assert model.current_speaker == "Seller"
        assert model.history == [{"role": "Buyer", "content": "I offer 50k"}]

        # New milestone fields default correctly
        assert model.milestone_summaries_enabled is False
        assert model.milestone_summaries == {}
        assert model.sliding_window_size == 3
        assert model.milestone_interval == 4

        # Structured memory fields also default
        assert model.structured_memory_enabled is False
        assert model.structured_memory_roles == []
        assert model.agent_memories == {}
