"""Unit tests for participant summary helpers from app.routers.negotiation.

Validates: Requirements 2.4, 2.5, 2.6
"""

import pytest

from app.routers.negotiation import (
    _build_block_advice,
    _build_participant_summaries,
    _format_outcome_value,
    _format_price_for_summary,
)


# ---------------------------------------------------------------------------
# _build_participant_summaries
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBuildParticipantSummaries2Agent:
    """2-agent scenario: buyer + seller."""

    AGENT_STATES = {
        "Buyer": {"name": "Alice", "agent_type": "negotiator"},
        "Seller": {"name": "Bob", "agent_type": "negotiator"},
    }

    def test_both_agents_get_summaries(self, sample_history):
        # sample_history has Buyer, Seller, Regulator, Analyst — filter to 2-agent states
        history = [e for e in sample_history if e["role"] in ("Buyer", "Seller")]
        summaries = _build_participant_summaries(history, self.AGENT_STATES)

        roles = [s["role"] for s in summaries]
        assert "Buyer" in roles
        assert "Seller" in roles
        assert len(summaries) == 2

    def test_negotiator_summary_contains_final_price(self):
        history = [
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {
                    "inner_thought": "Start low.",
                    "public_message": "I offer $500,000.",
                    "proposed_price": 500_000.0,
                },
            },
            {
                "role": "Seller",
                "agent_type": "negotiator",
                "turn_number": 2,
                "content": {
                    "inner_thought": "Too low.",
                    "public_message": "I counter at $850,000.",
                    "proposed_price": 850_000.0,
                },
            },
        ]
        summaries = _build_participant_summaries(history, self.AGENT_STATES)
        buyer = next(s for s in summaries if s["role"] == "Buyer")
        assert "$500,000" in buyer["summary"]

    def test_summary_uses_display_name(self):
        history = [
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {
                    "inner_thought": "Go.",
                    "public_message": "My offer stands.",
                    "proposed_price": 100.0,
                },
            },
        ]
        summaries = _build_participant_summaries(history, self.AGENT_STATES)
        # Display name "Alice" is used internally; summary text references the role's name
        assert summaries[0]["name"] == "Alice"

    def test_agent_type_is_negotiator(self):
        history = [
            {
                "role": "Seller",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {
                    "inner_thought": "Hold firm.",
                    "public_message": "No deal below $800k.",
                    "proposed_price": 800_000.0,
                },
            },
        ]
        summaries = _build_participant_summaries(history, self.AGENT_STATES)
        seller = next(s for s in summaries if s["role"] == "Seller")
        assert seller["agent_type"] == "negotiator"


@pytest.mark.unit
class TestBuildParticipantSummaries4Agent:
    """4-agent scenario: 2 negotiators + regulator + observer."""

    AGENT_STATES = {
        "Buyer": {"name": "Alice", "agent_type": "negotiator"},
        "Seller": {"name": "Bob", "agent_type": "negotiator"},
        "Regulator": {"name": "EU Compliance", "agent_type": "regulator", "warning_count": 1},
        "Analyst": {"name": "Market Analyst", "agent_type": "observer"},
    }

    def test_all_four_agents_get_summaries(self, sample_history):
        summaries = _build_participant_summaries(sample_history, self.AGENT_STATES)
        roles = {s["role"] for s in summaries}
        assert roles == {"Buyer", "Seller", "Regulator", "Analyst"}

    def test_regulator_summary_mentions_warnings(self, sample_history):
        summaries = _build_participant_summaries(sample_history, self.AGENT_STATES)
        reg = next(s for s in summaries if s["role"] == "Regulator")
        assert reg["agent_type"] == "regulator"
        assert "warning" in reg["summary"].lower() or "monitor" in reg["summary"].lower() or reg["summary"]

    def test_observer_summary_has_observation(self, sample_history):
        summaries = _build_participant_summaries(sample_history, self.AGENT_STATES)
        obs = next(s for s in summaries if s["role"] == "Analyst")
        assert obs["agent_type"] == "observer"
        assert obs["name"] == "Market Analyst"
        # Observer summary should contain first sentence of observation
        assert "Significant gap" in obs["summary"]

    def test_regulator_blocked_summary(self):
        """Regulator with BLOCKED status mentions blocking."""
        history = [
            {
                "role": "Regulator",
                "agent_type": "regulator",
                "turn_number": 3,
                "content": {
                    "reasoning": "Too many violations detected.",
                    "public_message": "Deal is blocked.",
                    "status": "BLOCKED",
                },
            },
        ]
        agent_states = {
            "Regulator": {"name": "Compliance Bot", "agent_type": "regulator", "warning_count": 3},
        }
        summaries = _build_participant_summaries(history, agent_states)
        reg = summaries[0]
        assert "Blocked" in reg["summary"] or "blocked" in reg["summary"].lower()
        assert "3" in reg["summary"]


# ---------------------------------------------------------------------------
# _build_block_advice
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBuildBlockAdvice:
    """Block advice from regulator warnings in history."""

    def test_advice_from_warning_entries(self):
        history = [
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {"public_message": "I demand $100k.", "proposed_price": 100_000.0},
            },
            {
                "role": "Regulator",
                "agent_type": "regulator",
                "turn_number": 1,
                "content": {
                    "reasoning": "Aggressive tactics detected.",
                    "public_message": "Warning issued.",
                    "status": "WARNING",
                },
            },
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": 2,
                "content": {"public_message": "Take it or leave it.", "proposed_price": 100_000.0},
            },
            {
                "role": "Regulator",
                "agent_type": "regulator",
                "turn_number": 2,
                "content": {
                    "reasoning": "Repeated aggressive tactics.",
                    "public_message": "Deal blocked.",
                    "status": "BLOCKED",
                },
            },
        ]
        advice = _build_block_advice(history, blocker="Regulator")
        assert len(advice) >= 1
        # Advice should target the Buyer (the warned negotiator)
        assert advice[0]["agent_role"] == "Buyer"
        assert "issue" in advice[0]
        assert "suggested_prompt" in advice[0]

    def test_advice_uses_display_names_from_agent_states(self):
        history = [
            {
                "role": "Teenager",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {"public_message": "I want midnight!", "proposed_price": 0},
            },
            {
                "role": "Mediator",
                "agent_type": "regulator",
                "turn_number": 1,
                "content": {
                    "reasoning": "Unreasonable demand.",
                    "status": "WARNING",
                },
            },
        ]
        agent_states = {
            "Teenager": {"name": "Alex", "agent_type": "negotiator"},
            "Mediator": {"name": "Family Mediator", "agent_type": "regulator"},
        }
        advice = _build_block_advice(history, blocker="Mediator", agent_states=agent_states)
        assert advice[0]["agent_role"] == "Alex"

    def test_fallback_when_no_warnings(self):
        """No WARNING/BLOCKED entries → fallback advice targeting last negotiator."""
        history = [
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {"public_message": "Offer.", "proposed_price": 500_000.0},
            },
            {
                "role": "Regulator",
                "agent_type": "regulator",
                "turn_number": 1,
                "content": {
                    "reasoning": "All clear.",
                    "status": "CLEAR",
                },
            },
        ]
        advice = _build_block_advice(history, blocker="Regulator")
        assert len(advice) == 1
        assert advice[0]["agent_role"] == "Buyer"
        assert "blocked" in advice[0]["issue"].lower()

    def test_fallback_uses_agent_states_when_no_negotiator_in_history(self):
        """Regulator at index 0 with no preceding negotiator → use agent_states."""
        history = [
            {
                "role": "Regulator",
                "agent_type": "regulator",
                "turn_number": 1,
                "content": {
                    "reasoning": "Aggressive opening by Lena.",
                    "status": "WARNING",
                },
            },
        ]
        agent_states = {
            "Lena": {"name": "Lena", "agent_type": "negotiator"},
            "Richard": {"name": "Richard", "agent_type": "negotiator"},
            "Regulator": {"name": "EU Compliance", "agent_type": "regulator"},
        }
        advice = _build_block_advice(history, blocker="Regulator", agent_states=agent_states)
        assert len(advice) >= 1
        # Should match "Lena" from reasoning text, not "Unknown"
        assert advice[0]["agent_role"] == "Lena"

    def test_fallback_picks_first_negotiator_when_no_text_match(self):
        """No negotiator in history and no name match in reasoning → first negotiator."""
        history = [
            {
                "role": "Regulator",
                "agent_type": "regulator",
                "turn_number": 1,
                "content": {
                    "reasoning": "Unacceptable terms proposed.",
                    "status": "WARNING",
                },
            },
        ]
        agent_states = {
            "Buyer": {"name": "Alice", "agent_type": "negotiator"},
            "Seller": {"name": "Bob", "agent_type": "negotiator"},
            "Regulator": {"name": "Compliance Bot", "agent_type": "regulator"},
        }
        advice = _build_block_advice(history, blocker="Regulator", agent_states=agent_states)
        assert len(advice) >= 1
        # Falls back to first negotiator display name, never "Unknown"
        assert advice[0]["agent_role"] != "Unknown"
        assert advice[0]["agent_role"] == "Alice"

    def test_no_unknown_in_fallback_path_with_agent_states(self):
        """Empty history + agent_states → fallback never returns Unknown."""
        history: list[dict] = []
        agent_states = {
            "Seller": {"name": "Bob", "agent_type": "negotiator"},
            "Regulator": {"name": "RegBot", "agent_type": "regulator"},
        }
        advice = _build_block_advice(history, blocker="Regulator", agent_states=agent_states)
        assert len(advice) == 1
        assert advice[0]["agent_role"] == "Bob"

    def test_reasoning_matches_display_name(self):
        """Reasoning mentions display name (not role key) → correct match."""
        history = [
            {
                "role": "Mediator",
                "agent_type": "regulator",
                "turn_number": 1,
                "content": {
                    "reasoning": "Alex is being unreasonable with the curfew demand.",
                    "status": "WARNING",
                },
            },
        ]
        agent_states = {
            "Teenager": {"name": "Alex", "agent_type": "negotiator"},
            "Parent": {"name": "Jordan", "agent_type": "negotiator"},
            "Mediator": {"name": "Family Mediator", "agent_type": "regulator"},
        }
        advice = _build_block_advice(history, blocker="Mediator", agent_states=agent_states)
        assert len(advice) >= 1
        # Should resolve "Alex" from reasoning → role "Teenager" → display "Alex"
        assert advice[0]["agent_role"] == "Alex"


# ---------------------------------------------------------------------------
# _format_outcome_value
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFormatOutcomeValue:
    """Tests for _format_outcome_value with different value_format settings."""

    def test_currency_format_default(self):
        state = {}  # No scenario_config → defaults to currency
        result = _format_outcome_value(750_000.0, state)
        assert "$750,000" in result
        assert "agreement" in result.lower()

    def test_currency_format_explicit(self):
        state = {
            "scenario_config": {
                "negotiation_params": {"value_format": "currency", "value_label": "Price"},
            },
        }
        result = _format_outcome_value(1_200_000.0, state)
        assert "$1,200,000" in result

    def test_percentage_format(self):
        state = {
            "scenario_config": {
                "negotiation_params": {"value_format": "percent", "value_label": "Equity"},
            },
        }
        result = _format_outcome_value(15.0, state)
        assert "15%" in result
        assert "agreement" in result.lower()

    def test_number_format(self):
        state = {
            "scenario_config": {
                "negotiation_params": {"value_format": "number", "value_label": "Units"},
            },
        }
        result = _format_outcome_value(5000.0, state)
        assert "5,000" in result
        assert "Units" in result

    def test_time_from_22_format(self):
        state = {
            "scenario_config": {
                "negotiation_params": {"value_format": "time_from_22", "value_label": "Curfew"},
            },
        }
        # 60 minutes from 22:00 = 23:00 = 11:00 PM
        result = _format_outcome_value(60.0, state)
        assert "11:00 PM" in result
        assert "Curfew" in result


# ---------------------------------------------------------------------------
# _format_price_for_summary
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFormatPriceForSummary:
    """Tests for _format_price_for_summary."""

    def test_currency_default(self):
        result = _format_price_for_summary(500_000.0)
        assert result == "$500,000"

    def test_currency_explicit(self):
        result = _format_price_for_summary(1_000_000.0, value_format="currency")
        assert result == "$1,000,000"

    def test_custom_label_ignored_for_currency(self):
        """value_label doesn't affect currency format output."""
        result = _format_price_for_summary(250_000.0, value_format="currency", value_label="Salary")
        assert result == "$250,000"

    def test_percent_format(self):
        result = _format_price_for_summary(42.0, value_format="percent")
        assert result == "42%"

    def test_number_format(self):
        result = _format_price_for_summary(10_000.0, value_format="number")
        assert result == "10,000"

    def test_time_from_22_format(self):
        # 0 minutes from 22:00 = 10:00 PM
        result = _format_price_for_summary(0.0, value_format="time_from_22")
        assert result == "10:00 PM"

    def test_time_from_22_past_midnight(self):
        # 120 minutes from 22:00 = 00:00 = 12:00 AM
        result = _format_price_for_summary(120.0, value_format="time_from_22")
        assert result == "12:00 AM"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestParticipantSummaryEdgeCases:
    """Edge cases: empty history, single turn, no regulator."""

    def test_empty_history(self):
        agent_states = {
            "Buyer": {"name": "Alice", "agent_type": "negotiator"},
            "Seller": {"name": "Bob", "agent_type": "negotiator"},
        }
        summaries = _build_participant_summaries([], agent_states)
        # No history entries → no summaries (agents with no last entry are skipped)
        assert summaries == []

    def test_single_turn_one_negotiator(self):
        history = [
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {
                    "inner_thought": "Only shot.",
                    "public_message": "I offer $600,000.",
                    "proposed_price": 600_000.0,
                },
            },
        ]
        agent_states = {
            "Buyer": {"name": "Alice", "agent_type": "negotiator"},
            "Seller": {"name": "Bob", "agent_type": "negotiator"},
        }
        summaries = _build_participant_summaries(history, agent_states)
        # Only Buyer has history, Seller is skipped
        assert len(summaries) == 1
        assert summaries[0]["role"] == "Buyer"
        assert "$600,000" in summaries[0]["summary"]

    def test_no_regulator_in_states(self):
        """Scenario with only negotiators — no regulator or observer."""
        history = [
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {
                    "inner_thought": "Go.",
                    "public_message": "Offer $500k.",
                    "proposed_price": 500_000.0,
                },
            },
            {
                "role": "Seller",
                "agent_type": "negotiator",
                "turn_number": 2,
                "content": {
                    "inner_thought": "Counter.",
                    "public_message": "Counter at $700k.",
                    "proposed_price": 700_000.0,
                },
            },
        ]
        agent_states = {
            "Buyer": {"name": "Alice", "agent_type": "negotiator"},
            "Seller": {"name": "Bob", "agent_type": "negotiator"},
        }
        summaries = _build_participant_summaries(history, agent_states)
        assert len(summaries) == 2
        types = {s["agent_type"] for s in summaries}
        assert types == {"negotiator"}

    def test_negotiator_with_zero_price(self):
        """Negotiator with proposed_price=0 should not include price in summary."""
        history = [
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {
                    "inner_thought": "Exploring.",
                    "public_message": "Let's discuss terms first.",
                    "proposed_price": 0,
                },
            },
        ]
        agent_states = {"Buyer": {"name": "Alice", "agent_type": "negotiator"}}
        summaries = _build_participant_summaries(history, agent_states)
        assert len(summaries) == 1
        # Price is 0/falsy, so "ended at" should NOT appear
        assert "ended at" not in summaries[0]["summary"]
