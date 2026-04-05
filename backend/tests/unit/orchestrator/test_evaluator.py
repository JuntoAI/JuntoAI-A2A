"""Unit tests for the post-negotiation evaluator agent.

Covers task 5.8:
- Interview parse retry + fallback (invalid JSON → retry → neutral fallback with satisfaction_rating=5)
- Scoring parse retry + fallback (invalid JSON → retry → all 5s report)
- Evaluator disabled (enabled=False) yields no events
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.models.events import EvaluationCompleteEvent, EvaluationInterviewEvent
from app.orchestrator.evaluator import (
    _interview_participant,
    _score_negotiation,
    run_evaluation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(
    role: str = "Buyer",
    model_id: str = "gemini-3-flash-preview",
) -> dict[str, Any]:
    return {
        "role": role,
        "name": role,
        "type": "negotiator",
        "model_id": model_id,
        "persona_prompt": f"You are {role}.",
        "goals": [f"Goal for {role}"],
        "budget": {"min": 1000.0, "max": 100000.0, "target": 50000.0},
        "tone": "professional",
        "output_fields": ["offer"],
    }


def _make_terminal_state() -> dict[str, Any]:
    return {
        "deal_status": "Agreed",
        "current_offer": 75000.0,
        "turn_count": 5,
        "history": [
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {
                    "public_message": "I offer 70k",
                    "proposed_price": 70000.0,
                    "inner_thought": "thinking",
                },
            },
        ],
    }


def _make_scenario_config(
    agents: list[dict[str, Any]] | None = None,
    evaluator_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if agents is None:
        agents = [
            _make_agent_config("Buyer"),
            _make_agent_config("Seller"),
        ]
    config: dict[str, Any] = {
        "id": "test-scenario",
        "agents": agents,
        "negotiation_params": {"max_turns": 15, "agreement_threshold": 5000.0},
    }
    if evaluator_config is not None:
        config["evaluator_config"] = evaluator_config
    return config


def _valid_interview_json() -> str:
    return json.dumps({
        "feels_served": True,
        "felt_respected": True,
        "is_win_win": True,
        "criticism": "No issues",
        "satisfaction_rating": 8,
    })


def _valid_report_json(interviews: list[dict[str, Any]] | None = None) -> str:
    return json.dumps({
        "participant_interviews": interviews or [],
        "dimensions": {
            "fairness": 7,
            "mutual_respect": 8,
            "value_creation": 6,
            "satisfaction": 7,
        },
        "overall_score": 7,
        "verdict": "A solid negotiation.",
        "deal_status": "Agreed",
    })


# ===========================================================================
# Test: Interview parse retry + fallback
# ===========================================================================


class TestInterviewParseRetryAndFallback:
    """Test interview LLM response parsing with retry and fallback."""

    @pytest.mark.asyncio
    async def test_first_parse_fails_retry_succeeds(self):
        """First LLM response is invalid JSON, retry returns valid JSON."""
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content="not valid json at all"),
            AIMessage(content=_valid_interview_json()),
        ]

        result = await _interview_participant(
            mock_model,
            _make_agent_config("Buyer"),
            _make_terminal_state()["history"],
            _make_terminal_state(),
        )

        assert mock_model.invoke.call_count == 2
        assert result.satisfaction_rating == 8
        assert result.feels_served is True

    @pytest.mark.asyncio
    async def test_double_parse_failure_uses_neutral_fallback(self):
        """Both LLM calls return garbage → neutral fallback with satisfaction_rating=5."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content="still garbage")

        result = await _interview_participant(
            mock_model,
            _make_agent_config("Buyer"),
            _make_terminal_state()["history"],
            _make_terminal_state(),
        )

        assert mock_model.invoke.call_count == 2
        assert result.satisfaction_rating == 5
        assert result.feels_served is True
        assert result.felt_respected is True
        assert result.is_win_win is True
        assert result.criticism == "Unable to assess"

    @pytest.mark.asyncio
    async def test_valid_first_response_no_retry(self):
        """Valid first response should not trigger retry."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=_valid_interview_json())

        result = await _interview_participant(
            mock_model,
            _make_agent_config("Buyer"),
            _make_terminal_state()["history"],
            _make_terminal_state(),
        )

        assert mock_model.invoke.call_count == 1
        assert result.satisfaction_rating == 8


# ===========================================================================
# Test: Scoring parse retry + fallback
# ===========================================================================


class TestScoringParseRetryAndFallback:
    """Test scoring LLM response parsing with retry and fallback."""

    @pytest.mark.asyncio
    async def test_first_parse_fails_retry_succeeds(self):
        """First scoring response is invalid, retry returns valid JSON."""
        interviews = [{"role": "Buyer", "satisfaction_rating": 7}]
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content="not json"),
            AIMessage(content=_valid_report_json(interviews)),
        ]

        result = await _score_negotiation(
            mock_model,
            interviews,
            _make_terminal_state()["history"],
            _make_terminal_state(),
            _make_scenario_config(),
        )

        assert mock_model.invoke.call_count == 2
        assert result.overall_score == 7

    @pytest.mark.asyncio
    async def test_double_parse_failure_uses_all_fives_fallback(self):
        """Both scoring calls return garbage → fallback report with all 5s."""
        interviews = [{"role": "Buyer", "satisfaction_rating": 7}]
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content="garbage")

        result = await _score_negotiation(
            mock_model,
            interviews,
            _make_terminal_state()["history"],
            _make_terminal_state(),
            _make_scenario_config(),
        )

        assert mock_model.invoke.call_count == 2
        assert result.overall_score == 5
        assert result.dimensions["fairness"] == 5
        assert result.dimensions["mutual_respect"] == 5
        assert result.dimensions["value_creation"] == 5
        assert result.dimensions["satisfaction"] == 5
        assert "could not be completed" in result.verdict

    @pytest.mark.asyncio
    async def test_valid_first_response_no_retry(self):
        """Valid first scoring response should not trigger retry."""
        interviews = [{"role": "Buyer", "satisfaction_rating": 7}]
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(
            content=_valid_report_json(interviews),
        )

        result = await _score_negotiation(
            mock_model,
            interviews,
            _make_terminal_state()["history"],
            _make_terminal_state(),
            _make_scenario_config(),
        )

        assert mock_model.invoke.call_count == 1
        assert result.overall_score == 7


# ===========================================================================
# Test: Evaluator disabled (enabled=False) yields no events
# ===========================================================================


class TestEvaluatorDisabled:
    """Test that evaluator_config.enabled=False skips evaluation entirely."""

    @pytest.mark.asyncio
    async def test_enabled_false_yields_no_events(self):
        """When evaluator_config.enabled is False, run_evaluation yields nothing."""
        scenario_config = _make_scenario_config(
            evaluator_config={"model_id": "gemini-3-flash-preview", "enabled": False},
        )

        events = []
        async for event in run_evaluation(_make_terminal_state(), scenario_config):
            events.append(event)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_enabled_true_yields_events(self):
        """When evaluator_config.enabled is True, run_evaluation yields events."""
        scenario_config = _make_scenario_config(
            evaluator_config={"model_id": "gemini-3-flash-preview", "enabled": True},
        )

        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_report_json()),
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(
                _make_terminal_state(), scenario_config,
            ):
                events.append(event)

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_no_evaluator_config_still_runs(self):
        """When evaluator_config is None, evaluation still runs (default behavior)."""
        scenario_config = _make_scenario_config(evaluator_config=None)

        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_report_json()),
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(
                _make_terminal_state(), scenario_config,
            ):
                events.append(event)

        # 2 negotiators × 2 events each + 1 complete = 5
        assert len(events) == 5
