"""Unit tests for evaluator prompt templates.

Covers task 5.8:
- Anti-rubber-stamp instructions in scoring system prompt
- Honest-answer instructions in interview system prompt
- Multi-party fairness mention for 3+ negotiators in scoring system prompt
"""

from __future__ import annotations

from typing import Any

from app.orchestrator.evaluator_prompts import (
    build_interview_system_prompt,
    build_interview_user_prompt,
    build_scoring_system_prompt,
    build_scoring_user_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(
    role: str = "Buyer",
    persona_prompt: str = "You are a buyer.",
    goals: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "role": role,
        "name": role,
        "type": "negotiator",
        "model_id": "gemini-3-flash-preview",
        "persona_prompt": persona_prompt,
        "goals": goals or ["Buy low"],
        "budget": {"min": 1000.0, "max": 100000.0, "target": 50000.0},
        "tone": "professional",
    }


# ===========================================================================
# Test: Anti-rubber-stamp instructions in scoring prompt
# ===========================================================================


class TestScoringSystemPromptAntiRubberStamp:
    """Verify the scoring system prompt contains anti-rubber-stamp instructions."""

    def test_default_to_five(self):
        """Scoring prompt must instruct to default to 5."""
        prompt = build_scoring_system_prompt()
        assert "5" in prompt
        assert "default" in prompt.lower() or "Default" in prompt

    def test_cap_at_six_for_dissatisfaction(self):
        """Scoring prompt must cap at 6 when dissatisfaction detected."""
        prompt = build_scoring_system_prompt()
        assert "6" in prompt
        assert "cap" in prompt.lower() or "dissatisfaction" in prompt.lower()

    def test_penalize_simple_splits(self):
        """Scoring prompt must penalize simple price splits by at least 2 points."""
        prompt = build_scoring_system_prompt()
        assert "split" in prompt.lower()
        assert "2" in prompt

    def test_reserve_nine_ten_for_genuine_enthusiasm(self):
        """Scoring prompt must reserve 9-10 for genuine enthusiasm + novel value."""
        prompt = build_scoring_system_prompt()
        assert "9" in prompt or "10" in prompt
        assert "enthusiasm" in prompt.lower() or "novel" in prompt.lower()

    def test_multi_party_fairness_mention(self):
        """Scoring prompt must mention multi-party fairness for 3+ negotiators."""
        prompt = build_scoring_system_prompt()
        assert "3" in prompt or "multi-party" in prompt.lower() or "three" in prompt.lower()
        assert "fairness" in prompt.lower() or "sidelined" in prompt.lower()


# ===========================================================================
# Test: Honest-answer instructions in interview prompt
# ===========================================================================


class TestInterviewSystemPromptHonesty:
    """Verify the interview system prompt instructs honest answers."""

    def test_unhappy_say_so(self):
        """Interview prompt must contain 'If you are unhappy, say so.'"""
        agent_config = _make_agent_config()
        prompt = build_interview_system_prompt(agent_config)
        assert "unhappy" in prompt.lower()
        assert "say so" in prompt.lower()

    def test_feel_you_lost_say_so(self):
        """Interview prompt must contain 'If you feel you lost, say so.'"""
        agent_config = _make_agent_config()
        prompt = build_interview_system_prompt(agent_config)
        assert "lost" in prompt.lower()

    def test_honest_truthful_instruction(self):
        """Interview prompt must instruct honest/truthful answers."""
        agent_config = _make_agent_config()
        prompt = build_interview_system_prompt(agent_config)
        assert "honest" in prompt.lower() or "truthful" in prompt.lower()

    def test_includes_role(self):
        """Interview system prompt must include the agent's role."""
        agent_config = _make_agent_config(role="SpecialAgent")
        prompt = build_interview_system_prompt(agent_config)
        assert "SpecialAgent" in prompt

    def test_includes_persona(self):
        """Interview system prompt must include persona when provided."""
        agent_config = _make_agent_config(persona_prompt="A shrewd negotiator")
        prompt = build_interview_system_prompt(agent_config)
        assert "shrewd negotiator" in prompt


# ===========================================================================
# Test: Interview user prompt content
# ===========================================================================


class TestInterviewUserPromptContent:
    """Verify the interview user prompt contains required context."""

    def test_contains_goals(self):
        """Interview user prompt must contain the agent's goals."""
        agent_config = _make_agent_config(goals=["Maximize profit", "Retain talent"])
        history = [
            {
                "role": "Buyer",
                "content": {"public_message": "I offer 50k"},
            },
        ]
        terminal_state = {
            "current_offer": 50000.0,
            "deal_status": "Agreed",
        }
        prompt = build_interview_user_prompt(agent_config, history, terminal_state)
        assert "Maximize profit" in prompt
        assert "Retain talent" in prompt

    def test_contains_current_offer(self):
        """Interview user prompt must contain the current offer."""
        agent_config = _make_agent_config()
        terminal_state = {"current_offer": 75000.0, "deal_status": "Agreed"}
        prompt = build_interview_user_prompt(agent_config, [], terminal_state)
        assert "75000.0" in prompt

    def test_contains_deal_status(self):
        """Interview user prompt must contain the deal status."""
        agent_config = _make_agent_config()
        terminal_state = {"current_offer": 50000.0, "deal_status": "Agreed"}
        prompt = build_interview_user_prompt(agent_config, [], terminal_state)
        assert "Agreed" in prompt

    def test_contains_history_messages(self):
        """Interview user prompt must contain public messages from history."""
        agent_config = _make_agent_config()
        history = [
            {"role": "Buyer", "content": {"public_message": "UniqueMessage123"}},
            {"role": "Seller", "content": {"public_message": "ResponseXYZ"}},
        ]
        terminal_state = {"current_offer": 50000.0, "deal_status": "Agreed"}
        prompt = build_interview_user_prompt(agent_config, history, terminal_state)
        assert "UniqueMessage123" in prompt
        assert "ResponseXYZ" in prompt


# ===========================================================================
# Test: Scoring user prompt includes budget data
# ===========================================================================


class TestScoringUserPromptContent:
    """Verify the scoring user prompt includes objective deal metrics."""

    def test_contains_budget_data(self):
        """Scoring prompt must contain per-agent budget data."""
        interviews = [
            {"role": "Buyer", "satisfaction_rating": 7},
        ]
        history = [
            {"role": "Buyer", "content": {"public_message": "Offer"}},
        ]
        terminal_state = {
            "current_offer": 75000.0,
            "deal_status": "Agreed",
            "turn_count": 5,
        }
        scenario_config = {
            "agents": [
                {
                    "role": "Buyer",
                    "type": "negotiator",
                    "budget": {"min": 50000.0, "max": 100000.0, "target": 75000.0},
                },
                {
                    "role": "Seller",
                    "type": "negotiator",
                    "budget": {"min": 60000.0, "max": 120000.0, "target": 90000.0},
                },
            ],
        }
        prompt = build_scoring_user_prompt(
            interviews, history, terminal_state, scenario_config,
        )
        assert "75000.0" in prompt  # Buyer target
        assert "90000.0" in prompt  # Seller target
        assert "50000.0" in prompt  # Buyer min
        assert "120000.0" in prompt  # Seller max

    def test_contains_interview_satisfaction_ratings(self):
        """Scoring prompt must contain satisfaction_rating values."""
        interviews = [
            {"role": "Buyer", "satisfaction_rating": 3, "feels_served": False},
            {"role": "Seller", "satisfaction_rating": 9, "feels_served": True},
        ]
        terminal_state = {
            "current_offer": 75000.0,
            "deal_status": "Agreed",
            "turn_count": 5,
        }
        scenario_config = {
            "agents": [
                {"role": "Buyer", "type": "negotiator", "budget": {"min": 50000.0, "max": 100000.0, "target": 75000.0}},
            ],
        }
        prompt = build_scoring_user_prompt(
            interviews, [], terminal_state, scenario_config,
        )
        # The interviews are JSON-dumped into the prompt
        assert "3" in prompt
        assert "9" in prompt

    def test_contains_deal_metrics(self):
        """Scoring prompt must contain final deal status, price, and turn count."""
        interviews = []
        terminal_state = {
            "current_offer": 42000.0,
            "deal_status": "Failed",
            "turn_count": 12,
        }
        scenario_config = {"agents": []}
        prompt = build_scoring_user_prompt(
            interviews, [], terminal_state, scenario_config,
        )
        assert "42000.0" in prompt
        assert "Failed" in prompt
        assert "12" in prompt
