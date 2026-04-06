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


# ===========================================================================
# Helpers for multi-agent scenarios
# ===========================================================================


def _two_agent_scenario() -> dict[str, Any]:
    """Buyer + Seller salary negotiation scenario config."""
    return {
        "agents": [
            {
                "role": "Recruiter",
                "name": "Recruiter",
                "type": "negotiator",
                "model_id": "gemini-2.5-flash",
                "persona_prompt": "You are a corporate recruiter hiring for a senior role.",
                "goals": ["Hire at or below 130k", "Secure 3-year commitment"],
                "budget": {"min": 100000.0, "max": 150000.0, "target": 120000.0},
                "tone": "professional",
            },
            {
                "role": "Candidate",
                "name": "Candidate",
                "type": "negotiator",
                "model_id": "claude-sonnet-4-20250514",
                "persona_prompt": "You are a senior engineer negotiating your offer.",
                "goals": ["Get at least 140k", "Remote work flexibility"],
                "budget": {"min": 130000.0, "max": 180000.0, "target": 155000.0},
                "tone": "assertive",
            },
        ],
    }


def _four_agent_scenario() -> dict[str, Any]:
    """2 negotiators + regulator + observer M&A scenario config."""
    return {
        "agents": [
            {
                "role": "BuyerCEO",
                "name": "BuyerCEO",
                "type": "negotiator",
                "model_id": "gemini-2.5-flash",
                "persona_prompt": "You are the CEO of an acquiring corporation.",
                "goals": ["Acquire below 5M valuation", "Retain key talent"],
                "budget": {"min": 2000000.0, "max": 6000000.0, "target": 4000000.0},
                "tone": "strategic",
            },
            {
                "role": "Founder",
                "name": "Founder",
                "type": "negotiator",
                "model_id": "claude-sonnet-4-20250514",
                "persona_prompt": "You are the startup founder selling your company.",
                "goals": ["Sell above 5M", "Protect employee equity"],
                "budget": {"min": 4000000.0, "max": 8000000.0, "target": 6000000.0},
                "tone": "passionate",
            },
            {
                "role": "EURegulator",
                "name": "EURegulator",
                "type": "regulator",
                "model_id": "gemini-2.5-pro",
                "persona_prompt": "You are an EU competition regulator overseeing this M&A.",
                "goals": ["Ensure fair competition"],
                "budget": {},
                "tone": "formal",
            },
            {
                "role": "MarketObserver",
                "name": "MarketObserver",
                "type": "observer",
                "model_id": "gemini-2.5-flash",
                "persona_prompt": "You are a market analyst observing the deal.",
                "goals": ["Provide neutral commentary"],
                "budget": {},
                "tone": "neutral",
            },
        ],
    }


def _two_agent_history() -> list[dict[str, Any]]:
    """Multi-turn history for a 2-agent negotiation."""
    return [
        {"role": "Recruiter", "content": {"public_message": "We can offer 120k base with standard benefits."}},
        {"role": "Candidate", "content": {"public_message": "I need at least 140k given my experience."}},
        {"role": "Recruiter", "content": {"public_message": "How about 132k with a signing bonus?"}},
        {"role": "Candidate", "content": {"public_message": "135k with remote flexibility and I accept."}},
    ]


def _four_agent_history() -> list[dict[str, Any]]:
    """Multi-turn history for a 4-agent negotiation with regulator and observer."""
    return [
        {"role": "BuyerCEO", "content": {"public_message": "We propose 3.5M for full acquisition."}},
        {"role": "EURegulator", "content": {"reasoning": "Reviewing market concentration impact."}},
        {"role": "Founder", "content": {"public_message": "That undervalues us. We need at least 5.5M."}},
        {"role": "EURegulator", "content": {"reasoning": "No competition concerns at this stage."}},
        {"role": "MarketObserver", "content": {"observation": "Both parties far apart. Expect 2-3 more rounds."}},
        {"role": "BuyerCEO", "content": {"public_message": "4.2M with talent retention clauses."}},
        {"role": "Founder", "content": {"public_message": "4.8M and we have a deal."}},
    ]


# ===========================================================================
# Test: 2-agent scenario prompt construction
# ===========================================================================


class TestTwoAgentScenarioPrompts:
    """Prompt construction for a 2-agent (Recruiter + Candidate) scenario."""

    def test_interview_system_prompt_per_agent(self):
        """Each agent gets an interview system prompt with their own role and persona."""
        scenario = _two_agent_scenario()
        for agent in scenario["agents"]:
            prompt = build_interview_system_prompt(agent)
            assert agent["role"] in prompt
            assert agent["persona_prompt"] in prompt

    def test_interview_user_prompt_contains_both_roles_in_history(self):
        """Interview user prompt transcript includes messages from both agents."""
        agent = _two_agent_scenario()["agents"][0]  # Recruiter
        history = _two_agent_history()
        terminal_state = {"current_offer": 135000.0, "deal_status": "Agreed"}

        prompt = build_interview_user_prompt(agent, history, terminal_state)
        assert "[Recruiter]" in prompt
        assert "[Candidate]" in prompt
        assert "120k base" in prompt
        assert "135k with remote" in prompt

    def test_interview_user_prompt_contains_agent_goals(self):
        """Interview user prompt includes the specific agent's goals."""
        agent = _two_agent_scenario()["agents"][1]  # Candidate
        terminal_state = {"current_offer": 135000.0, "deal_status": "Agreed"}

        prompt = build_interview_user_prompt(agent, [], terminal_state)
        assert "Get at least 140k" in prompt
        assert "Remote work flexibility" in prompt

    def test_scoring_user_prompt_contains_both_budgets(self):
        """Scoring prompt includes budget data for both negotiators."""
        scenario = _two_agent_scenario()
        interviews = [
            {"role": "Recruiter", "satisfaction_rating": 7, "feels_served": True},
            {"role": "Candidate", "satisfaction_rating": 6, "feels_served": True},
        ]
        terminal_state = {"current_offer": 135000.0, "deal_status": "Agreed", "turn_count": 4}

        prompt = build_scoring_user_prompt(interviews, _two_agent_history(), terminal_state, scenario)
        # Recruiter budget
        assert "120000.0" in prompt  # target
        assert "100000.0" in prompt  # min
        assert "150000.0" in prompt  # max
        # Candidate budget
        assert "155000.0" in prompt  # target
        assert "130000.0" in prompt  # min
        assert "180000.0" in prompt  # max

    def test_scoring_user_prompt_contains_full_transcript(self):
        """Scoring prompt includes all history entries from both agents."""
        scenario = _two_agent_scenario()
        history = _two_agent_history()
        terminal_state = {"current_offer": 135000.0, "deal_status": "Agreed", "turn_count": 4}

        prompt = build_scoring_user_prompt([], history, terminal_state, scenario)
        for entry in history:
            role = entry["role"]
            msg = entry["content"]["public_message"]
            assert f"[{role}]" in prompt
            assert msg in prompt


# ===========================================================================
# Test: 4-agent scenario prompt construction
# ===========================================================================


class TestFourAgentScenarioPrompts:
    """Prompt construction for a 4-agent (2 negotiators + regulator + observer) scenario."""

    def test_interview_system_prompt_includes_regulator_role(self):
        """Regulator agent gets interview system prompt with its role."""
        regulator = _four_agent_scenario()["agents"][2]
        prompt = build_interview_system_prompt(regulator)
        assert "EURegulator" in prompt
        assert "EU competition regulator" in prompt

    def test_interview_system_prompt_includes_observer_role(self):
        """Observer agent gets interview system prompt with its role."""
        observer = _four_agent_scenario()["agents"][3]
        prompt = build_interview_system_prompt(observer)
        assert "MarketObserver" in prompt
        assert "market analyst" in prompt

    def test_interview_user_prompt_contains_all_four_roles_in_history(self):
        """Interview user prompt transcript includes messages from all 4 agent types."""
        agent = _four_agent_scenario()["agents"][0]  # BuyerCEO
        history = _four_agent_history()
        terminal_state = {"current_offer": 4800000.0, "deal_status": "Agreed"}

        prompt = build_interview_user_prompt(agent, history, terminal_state)
        assert "[BuyerCEO]" in prompt
        assert "[Founder]" in prompt
        assert "[EURegulator]" in prompt
        assert "[MarketObserver]" in prompt

    def test_interview_user_prompt_renders_reasoning_and_observation(self):
        """Regulator reasoning and observer observation appear in transcript."""
        agent = _four_agent_scenario()["agents"][1]  # Founder
        history = _four_agent_history()
        terminal_state = {"current_offer": 4800000.0, "deal_status": "Agreed"}

        prompt = build_interview_user_prompt(agent, history, terminal_state)
        assert "market concentration impact" in prompt
        assert "Both parties far apart" in prompt

    def test_scoring_user_prompt_only_includes_negotiator_budgets(self):
        """Scoring prompt includes budgets for negotiators only, not regulator/observer."""
        scenario = _four_agent_scenario()
        interviews = [
            {"role": "BuyerCEO", "satisfaction_rating": 6},
            {"role": "Founder", "satisfaction_rating": 7},
        ]
        terminal_state = {"current_offer": 4800000.0, "deal_status": "Agreed", "turn_count": 4}

        prompt = build_scoring_user_prompt(interviews, _four_agent_history(), terminal_state, scenario)
        # Negotiator budgets present
        assert "BuyerCEO" in prompt
        assert "4000000.0" in prompt  # BuyerCEO target
        assert "Founder" in prompt
        assert "6000000.0" in prompt  # Founder target
        # Regulator/observer should NOT appear in budget section
        # (they have type != "negotiator" so build_scoring_user_prompt filters them out)
        budget_section = prompt.split("Agent budget data:")[1].split("Participant interviews:")[0]
        assert "EURegulator" not in budget_section
        assert "MarketObserver" not in budget_section

    def test_scoring_user_prompt_transcript_includes_all_agent_types(self):
        """Scoring prompt transcript includes negotiator, regulator, and observer entries."""
        scenario = _four_agent_scenario()
        history = _four_agent_history()
        terminal_state = {"current_offer": 4800000.0, "deal_status": "Agreed", "turn_count": 4}

        prompt = build_scoring_user_prompt([], history, terminal_state, scenario)
        assert "[BuyerCEO]" in prompt
        assert "[Founder]" in prompt
        assert "[EURegulator]" in prompt
        assert "[MarketObserver]" in prompt


# ===========================================================================
# Test: Prompt contains scenario context, agent roles, and history
# ===========================================================================


class TestPromptContainsScenarioContext:
    """Verify prompts embed scenario context, all agent roles, and full history."""

    def test_interview_user_prompt_budget_constraints(self):
        """Interview user prompt includes the agent's budget constraints."""
        agent = _two_agent_scenario()["agents"][1]  # Candidate
        terminal_state = {"current_offer": 140000.0, "deal_status": "Agreed"}

        prompt = build_interview_user_prompt(agent, [], terminal_state)
        assert "130000.0" in prompt  # min
        assert "180000.0" in prompt  # max
        assert "155000.0" in prompt  # target

    def test_interview_user_prompt_final_offer_and_status(self):
        """Interview user prompt includes final offer and deal status."""
        agent = _make_agent_config()
        terminal_state = {"current_offer": 99999.0, "deal_status": "Failed"}

        prompt = build_interview_user_prompt(agent, [], terminal_state)
        assert "99999.0" in prompt
        assert "Failed" in prompt

    def test_scoring_user_prompt_deal_summary_line(self):
        """Scoring prompt opens with a deal summary line containing status, price, turns."""
        scenario = _two_agent_scenario()
        terminal_state = {"current_offer": 135000.0, "deal_status": "Agreed", "turn_count": 4}

        prompt = build_scoring_user_prompt([], [], terminal_state, scenario)
        assert "Agreed" in prompt
        assert "135000.0" in prompt
        assert "4" in prompt

    def test_interview_user_prompt_history_preserves_order(self):
        """History entries appear in the prompt in the same order they were provided."""
        agent = _make_agent_config(role="Recruiter")
        history = _two_agent_history()
        terminal_state = {"current_offer": 135000.0, "deal_status": "Agreed"}

        prompt = build_interview_user_prompt(agent, history, terminal_state)
        # Verify ordering: first message appears before last message
        first_pos = prompt.index("120k base")
        last_pos = prompt.index("135k with remote")
        assert first_pos < last_pos

    def test_scoring_user_prompt_history_preserves_order(self):
        """Scoring prompt history entries preserve chronological order."""
        scenario = _four_agent_scenario()
        history = _four_agent_history()
        terminal_state = {"current_offer": 4800000.0, "deal_status": "Agreed", "turn_count": 4}

        prompt = build_scoring_user_prompt([], history, terminal_state, scenario)
        pos_first = prompt.index("3.5M for full acquisition")
        pos_last = prompt.index("4.8M and we have a deal")
        assert pos_first < pos_last

    def test_interview_system_prompt_json_schema_present(self):
        """Interview system prompt includes the expected JSON response schema."""
        agent = _four_agent_scenario()["agents"][0]
        prompt = build_interview_system_prompt(agent)
        assert "feels_served" in prompt
        assert "felt_respected" in prompt
        assert "satisfaction_rating" in prompt

    def test_scoring_system_prompt_json_schema_present(self):
        """Scoring system prompt includes the expected JSON response schema."""
        prompt = build_scoring_system_prompt()
        assert "fairness" in prompt
        assert "mutual_respect" in prompt
        assert "value_creation" in prompt
        assert "overall_score" in prompt
        assert "verdict" in prompt
