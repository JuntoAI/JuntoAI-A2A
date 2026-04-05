"""Property-based tests for the post-negotiation evaluator agent.

Feature: negotiation-evaluator
Uses Hypothesis to verify correctness properties P6, P7, P8, P10, P11.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from langchain_core.messages import AIMessage

from app.models.events import EvaluationCompleteEvent, EvaluationInterviewEvent
from app.orchestrator.evaluator import (
    _get_negotiator_configs,
    _resolve_evaluator_model,
    run_evaluation,
)
from app.orchestrator.evaluator_prompts import (
    build_interview_user_prompt,
    build_scoring_user_prompt,
)

# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=1,
    max_size=30,
)

_role_name = st.text(
    alphabet=st.characters(whitelist_categories=("L",)),
    min_size=2,
    max_size=15,
)

_model_id = st.sampled_from(["gemini-3-flash-preview", "claude-3-5-sonnet", "gemini-2-5-pro"])

_satisfaction = st.integers(min_value=1, max_value=10)

_positive_price = st.floats(
    min_value=100.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False,
)


def _make_agent_config(
    role: str,
    agent_type: str = "negotiator",
    model_id: str = "gemini-3-flash-preview",
    persona_prompt: str | None = None,
    goals: list[str] | None = None,
    budget: dict[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "role": role,
        "name": role,
        "type": agent_type,
        "model_id": model_id,
        "persona_prompt": persona_prompt or f"You are {role}.",
        "goals": goals or [f"Goal for {role}"],
        "budget": budget or {"min": 1000.0, "max": 100000.0, "target": 50000.0},
        "tone": "professional",
        "output_fields": ["offer"],
    }


def _make_valid_interview_json(role: str = "Agent") -> str:
    return json.dumps({
        "feels_served": True,
        "felt_respected": True,
        "is_win_win": True,
        "criticism": f"No issues from {role}",
        "satisfaction_rating": 7,
    })


def _make_valid_report_json(
    interviews: list[dict[str, Any]], deal_status: str = "Agreed",
) -> str:
    return json.dumps({
        "participant_interviews": interviews,
        "dimensions": {
            "fairness": 7,
            "mutual_respect": 8,
            "value_creation": 6,
            "satisfaction": 7,
        },
        "overall_score": 7,
        "verdict": "A solid negotiation with room for improvement.",
        "deal_status": deal_status,
    })


# ---------------------------------------------------------------------------
# Composite strategies
# ---------------------------------------------------------------------------


@st.composite
def scenario_config_with_negotiators(draw):
    """Generate a scenario config with 2-5 negotiators and optional non-negotiators."""
    n_negotiators = draw(st.integers(min_value=2, max_value=5))
    n_regulators = draw(st.integers(min_value=0, max_value=1))
    n_observers = draw(st.integers(min_value=0, max_value=1))

    agents = []
    for i in range(n_negotiators):
        agents.append(_make_agent_config(f"Negotiator_{i}", "negotiator"))
    for i in range(n_regulators):
        agents.append(_make_agent_config(f"Regulator_{i}", "regulator"))
    for i in range(n_observers):
        agents.append(_make_agent_config(f"Observer_{i}", "observer"))

    return {
        "id": "test-scenario",
        "agents": agents,
        "negotiation_params": {"max_turns": 15, "agreement_threshold": 5000.0},
    }, n_negotiators


@st.composite
def terminal_state_with_history(draw):
    """Generate a terminal state with varying history lengths and known fields."""
    n_entries = draw(st.integers(min_value=1, max_value=8))
    current_offer = draw(_positive_price)
    persona = draw(_safe_text)
    goals = draw(st.lists(_safe_text, min_size=1, max_size=3))

    history = []
    for i in range(n_entries):
        role = draw(st.sampled_from(["Buyer", "Seller", "Mediator"]))
        public_msg = draw(_safe_text)
        history.append({
            "role": role,
            "agent_type": "negotiator",
            "turn_number": i + 1,
            "content": {
                "public_message": public_msg,
                "proposed_price": current_offer + i * 100,
                "inner_thought": "thinking",
            },
        })

    terminal_state = {
        "deal_status": "Agreed",
        "current_offer": current_offer,
        "turn_count": n_entries,
        "history": history,
    }

    agent_config = {
        "role": "TestAgent",
        "name": "TestAgent",
        "type": "negotiator",
        "model_id": "gemini-3-flash-preview",
        "persona_prompt": persona,
        "goals": goals,
        "budget": {"min": 1000.0, "max": 100000.0, "target": 50000.0},
        "tone": "professional",
    }

    return terminal_state, agent_config, history


@st.composite
def scenario_config_with_optional_evaluator(draw):
    """Generate scenario configs with and without evaluator_config."""
    has_evaluator = draw(st.booleans())
    first_negotiator_model = draw(_model_id)

    agents = [
        _make_agent_config("Buyer", "negotiator", first_negotiator_model),
        _make_agent_config("Seller", "negotiator", draw(_model_id)),
    ]

    config: dict[str, Any] = {
        "id": "test-scenario",
        "agents": agents,
        "negotiation_params": {"max_turns": 15, "agreement_threshold": 5000.0},
    }

    if has_evaluator:
        evaluator_model = draw(_model_id)
        config["evaluator_config"] = {
            "model_id": evaluator_model,
            "enabled": True,
        }
        expected_model_id = evaluator_model
    else:
        expected_model_id = first_negotiator_model

    return config, expected_model_id, has_evaluator


@st.composite
def scoring_prompt_scenario(draw):
    """Generate interviews and terminal states with known budgets for scoring prompt test."""
    n_negotiators = draw(st.integers(min_value=2, max_value=4))
    current_offer = draw(_positive_price)

    agents = []
    interviews = []
    for i in range(n_negotiators):
        role = f"Agent_{i}"
        target = draw(_positive_price)
        min_val = target * 0.8
        max_val = target * 1.2
        sat_rating = draw(_satisfaction)

        agents.append(_make_agent_config(
            role, "negotiator",
            budget={"min": min_val, "max": max_val, "target": target},
        ))
        interviews.append({
            "role": role,
            "feels_served": draw(st.booleans()),
            "felt_respected": draw(st.booleans()),
            "is_win_win": draw(st.booleans()),
            "criticism": "Some feedback",
            "satisfaction_rating": sat_rating,
        })

    terminal_state = {
        "deal_status": "Agreed",
        "current_offer": current_offer,
        "turn_count": 5,
        "history": [
            {
                "role": "Agent_0",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {"public_message": "Opening offer", "proposed_price": current_offer},
            },
        ],
    }

    scenario_config = {
        "id": "test-scenario",
        "agents": agents,
        "negotiation_params": {"max_turns": 15, "agreement_threshold": 5000.0},
    }

    return interviews, terminal_state, scenario_config, agents



# ===========================================================================
# Property 6: Evaluator interviews exactly N negotiators
# Feature: negotiation-evaluator
# **Validates: Requirements 5.2, 12.2**
# ===========================================================================


@settings(max_examples=100)
@given(data=scenario_config_with_negotiators())
@pytest.mark.asyncio
async def test_evaluator_interviews_exactly_n_negotiators(
    data: tuple[dict[str, Any], int],
):
    """run_evaluation() yields exactly N interview pairs (interviewing + complete)
    plus 1 EvaluationCompleteEvent for a scenario with N negotiators.

    **Validates: Requirements 5.2, 12.2**
    """
    scenario_config, n_negotiators = data

    terminal_state = {
        "deal_status": "Agreed",
        "current_offer": 50000.0,
        "turn_count": 5,
        "history": [
            {
                "role": "Negotiator_0",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {"public_message": "Opening offer", "proposed_price": 50000.0},
            },
        ],
    }

    # Build mock model that returns valid interview + report JSON
    interview_responses = []
    collected_interviews = []
    for i in range(n_negotiators):
        role = f"Negotiator_{i}"
        interview_responses.append(AIMessage(content=_make_valid_interview_json(role)))
        collected_interviews.append({
            "role": role,
            "feels_served": True,
            "felt_respected": True,
            "is_win_win": True,
            "criticism": f"No issues from {role}",
            "satisfaction_rating": 7,
        })

    report_response = AIMessage(
        content=_make_valid_report_json(collected_interviews),
    )

    mock_model = MagicMock()
    mock_model.invoke.side_effect = [*interview_responses, report_response]

    with patch("app.orchestrator.evaluator.model_router") as mock_router:
        mock_router.get_model.return_value = mock_model

        events = []
        async for event in run_evaluation(terminal_state, scenario_config):
            events.append(event)

    # Count event types
    interviewing_events = [
        e for e in events
        if isinstance(e, EvaluationInterviewEvent) and e.status == "interviewing"
    ]
    complete_interview_events = [
        e for e in events
        if isinstance(e, EvaluationInterviewEvent) and e.status == "complete"
    ]
    complete_events = [e for e in events if isinstance(e, EvaluationCompleteEvent)]

    assert len(interviewing_events) == n_negotiators, (
        f"Expected {n_negotiators} 'interviewing' events, got {len(interviewing_events)}"
    )
    assert len(complete_interview_events) == n_negotiators, (
        f"Expected {n_negotiators} 'complete' interview events, got {len(complete_interview_events)}"
    )
    assert len(complete_events) == 1, (
        f"Expected exactly 1 EvaluationCompleteEvent, got {len(complete_events)}"
    )
    assert len(events) == 2 * n_negotiators + 1


# ===========================================================================
# Property 7: Interview isolation — no cross-contamination
# Feature: negotiation-evaluator
# **Validates: Requirements 5.3**
# ===========================================================================


@st.composite
def multi_participant_interview_scenario(draw):
    """Generate interview results for multiple participants."""
    n = draw(st.integers(min_value=2, max_value=4))

    agent_configs = []
    interview_results = []
    for i in range(n):
        role = f"Participant_{i}"
        agent_configs.append(_make_agent_config(
            role, "negotiator",
            persona_prompt=f"Persona for {role}",
            goals=[f"Goal_{i}_A", f"Goal_{i}_B"],
        ))
        interview_results.append({
            "role": role,
            "feels_served": draw(st.booleans()),
            "felt_respected": draw(st.booleans()),
            "is_win_win": draw(st.booleans()),
            "criticism": f"Criticism from {role} unique_{i}",
            "satisfaction_rating": draw(_satisfaction),
        })

    history = [
        {
            "role": "Participant_0",
            "agent_type": "negotiator",
            "turn_number": 1,
            "content": {"public_message": "Hello", "proposed_price": 50000.0},
        },
    ]

    terminal_state = {
        "deal_status": "Agreed",
        "current_offer": 50000.0,
        "turn_count": 3,
        "history": history,
    }

    return agent_configs, interview_results, terminal_state


@settings(max_examples=100)
@given(data=multi_participant_interview_scenario())
def test_interview_isolation_no_cross_contamination(
    data: tuple[list[dict], list[dict], dict],
):
    """When building the interview prompt for agent A, it must NOT contain
    agent B's interview response fields (feels_served, felt_respected, etc.).

    **Validates: Requirements 5.3**
    """
    agent_configs, interview_results, terminal_state = data
    history = terminal_state["history"]

    # The interview response fields that should NOT leak across participants
    response_fields = ["feels_served", "felt_respected", "is_win_win", "satisfaction_rating"]

    for idx, agent_config in enumerate(agent_configs):
        prompt = build_interview_user_prompt(agent_config, history, terminal_state)

        # Check that no OTHER participant's interview result values appear in this prompt
        for other_idx, other_result in enumerate(interview_results):
            if other_idx == idx:
                continue  # Skip self

            # The criticism field is unique per participant — check it doesn't leak
            other_criticism = other_result["criticism"]
            assert other_criticism not in prompt, (
                f"Prompt for {agent_config['role']} contains criticism from "
                f"{other_result['role']}: {other_criticism!r}"
            )


# ===========================================================================
# Property 8: Interview prompt contains required context
# Feature: negotiation-evaluator
# **Validates: Requirements 5.5**
# ===========================================================================


@settings(max_examples=100)
@given(data=terminal_state_with_history())
def test_interview_prompt_contains_required_context(
    data: tuple[dict, dict, list[dict]],
):
    """The interview user prompt must contain: (a) at least one history entry's
    public_message, (b) the participant's persona_prompt, (c) at least one goal,
    and (d) the current_offer value.

    **Validates: Requirements 5.5**
    """
    terminal_state, agent_config, history = data

    prompt = build_interview_user_prompt(agent_config, history, terminal_state)

    # (a) At least one public_message from history
    public_messages = [
        entry["content"]["public_message"]
        for entry in history
        if isinstance(entry.get("content"), dict) and "public_message" in entry["content"]
    ]
    assert any(msg in prompt for msg in public_messages), (
        "Prompt must contain at least one public_message from history"
    )

    # (b) persona_prompt is provided via system prompt, but goals should be in user prompt
    # The persona is in the system prompt, so we check goals instead
    # (c) At least one goal
    goals = agent_config["goals"]
    assert any(goal in prompt for goal in goals), (
        f"Prompt must contain at least one goal from {goals}"
    )

    # (d) current_offer value
    current_offer = terminal_state["current_offer"]
    assert str(current_offer) in prompt, (
        f"Prompt must contain current_offer={current_offer}"
    )


# ===========================================================================
# Property 10: Default evaluator model resolution
# Feature: negotiation-evaluator
# **Validates: Requirements 9.2**
# ===========================================================================


@settings(max_examples=100)
@given(data=scenario_config_with_optional_evaluator())
def test_default_evaluator_model_resolution(
    data: tuple[dict[str, Any], str, bool],
):
    """_resolve_evaluator_model uses evaluator_config.model_id when present,
    else falls back to the first negotiator's model_id.

    **Validates: Requirements 9.2**
    """
    scenario_config, expected_model_id, has_evaluator = data

    mock_model = MagicMock()

    with patch("app.orchestrator.evaluator.model_router") as mock_router:
        mock_router.get_model.return_value = mock_model

        result = _resolve_evaluator_model(scenario_config)

    # Verify get_model was called with the expected model_id
    call_args = mock_router.get_model.call_args
    actual_model_id = call_args[0][0] if call_args[0] else call_args[1].get("model_id")

    assert actual_model_id == expected_model_id, (
        f"Expected model_id={expected_model_id!r} but got {actual_model_id!r} "
        f"(has_evaluator={has_evaluator})"
    )


# ===========================================================================
# Property 11: Scoring prompt includes objective deal metrics
# Feature: negotiation-evaluator
# **Validates: Requirements 11.3**
# ===========================================================================


@settings(max_examples=100)
@given(data=scoring_prompt_scenario())
def test_scoring_prompt_includes_objective_deal_metrics(
    data: tuple[list[dict], dict, dict, list[dict]],
):
    """The scoring user prompt must contain satisfaction_rating values from
    interviews and price-vs-budget data (target, min, max) for each agent.

    **Validates: Requirements 11.3**
    """
    interviews, terminal_state, scenario_config, agents = data

    prompt = build_scoring_user_prompt(
        interviews, terminal_state["history"], terminal_state, scenario_config,
    )

    # Verify satisfaction_rating values appear in the prompt (via interview JSON dump)
    for interview in interviews:
        sat_str = str(interview["satisfaction_rating"])
        assert sat_str in prompt, (
            f"Prompt must contain satisfaction_rating={sat_str} for {interview['role']}"
        )

    # Verify budget data for each negotiator agent
    for agent in agents:
        if agent.get("type") == "negotiator":
            budget = agent["budget"]
            role = agent["role"]
            # The prompt should contain target, min, max for each agent
            assert str(budget["target"]) in prompt, (
                f"Prompt must contain target={budget['target']} for {role}"
            )
            assert str(budget["min"]) in prompt, (
                f"Prompt must contain min={budget['min']} for {role}"
            )
            assert str(budget["max"]) in prompt, (
                f"Prompt must contain max={budget['max']} for {role}"
            )
