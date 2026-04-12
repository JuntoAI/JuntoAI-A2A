"""Integration test: evaluation event ordering and graceful degradation.

Task 10.2 — Validates Requirement 8.4:
- Full stream test verifying evaluation_interview → evaluation_complete ordering
- Mock evaluator to raise exception, verify error propagates (caller handles it)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.models.events import EvaluationCompleteEvent, EvaluationInterviewEvent
from app.orchestrator.evaluator import run_evaluation


def _agent_def(
    role: str,
    name: str,
    agent_type: str = "negotiator",
    model_id: str = "gemini-3-flash-preview",
) -> dict[str, Any]:
    return {
        "role": role,
        "name": name,
        "type": agent_type,
        "model_id": model_id,
        "persona_prompt": f"You are {name}.",
        "goals": ["Close the deal"],
        "budget": {"target": 100000, "min": 80000, "max": 120000},
    }


def _make_scenario(num_negotiators: int = 2) -> dict[str, Any]:
    agents = []
    for i in range(num_negotiators):
        role = f"Agent{i}"
        agents.append(_agent_def(role, f"Person{i}"))
    return {
        "id": "evaluator-integration",
        "agents": agents,
        "negotiation_params": {
            "max_turns": 10,
            "agreement_threshold": 5000.0,
            "turn_order": [a["role"] for a in agents],
        },
    }


def _make_terminal_state(deal_status: str = "Agreed") -> dict[str, Any]:
    return {
        "deal_status": deal_status,
        "current_offer": 105000.0,
        "turn_count": 5,
        "history": [
            {
                "role": "Agent0",
                "agent_type": "negotiator",
                "turn_number": 1,
                "content": {"public_message": "I propose 100000", "proposed_price": 100000.0},
            },
            {
                "role": "Agent1",
                "agent_type": "negotiator",
                "turn_number": 2,
                "content": {"public_message": "I counter with 110000", "proposed_price": 110000.0},
            },
        ],
    }


def _interview_json() -> str:
    return json.dumps({
        "feels_served": True,
        "felt_respected": True,
        "is_win_win": True,
        "criticism": "Could have been faster.",
        "satisfaction_rating": 7,
    })


def _report_json(deal_status: str = "Agreed") -> str:
    return json.dumps({
        "participant_interviews": [],
        "dimensions": {
            "fairness": 7,
            "mutual_respect": 8,
            "value_creation": 5,
            "satisfaction": 7,
        },
        "overall_score": 6,
        "verdict": "A functional deal but lacking creative value creation.",
        "deal_status": deal_status,
    })


class TestEvaluationEventOrdering:
    """Verify evaluation events are emitted in correct order."""

    @patch("app.orchestrator.evaluator.model_router")
    @pytest.mark.asyncio
    async def test_event_ordering_two_negotiators(self, mock_router):
        """Concurrent impl: interviewing(0) → interviewing(1) → complete(0) → complete(1) → evaluation_complete."""
        call_count = 0

        def _invoke(messages):
            nonlocal call_count
            call_count += 1
            # First N calls are interviews, last call is scoring
            if call_count <= 2:
                return AIMessage(content=_interview_json())
            else:
                return AIMessage(content=_report_json())

        mock_model = MagicMock()
        mock_model.invoke.side_effect = _invoke
        mock_router.get_model.return_value = mock_model

        scenario = _make_scenario(num_negotiators=2)
        terminal_state = _make_terminal_state()

        events = []
        async for event in run_evaluation(terminal_state, scenario):
            events.append(event)

        # Expect: 2 interviewing + 2 complete + 1 evaluation_complete = 5
        assert len(events) == 5

        # All "interviewing" events emitted upfront before concurrent interviews run
        assert isinstance(events[0], EvaluationInterviewEvent)
        assert events[0].status == "interviewing"
        assert events[0].agent_name == "Agent0"

        assert isinstance(events[1], EvaluationInterviewEvent)
        assert events[1].status == "interviewing"
        assert events[1].agent_name == "Agent1"

        # "complete" events emitted after all interviews finish
        assert isinstance(events[2], EvaluationInterviewEvent)
        assert events[2].status == "complete"
        assert events[2].agent_name == "Agent0"
        assert events[2].satisfaction_rating == 7

        assert isinstance(events[3], EvaluationInterviewEvent)
        assert events[3].status == "complete"
        assert events[3].agent_name == "Agent1"
        assert events[3].satisfaction_rating == 7

        assert isinstance(events[4], EvaluationCompleteEvent)
        assert events[4].overall_score == 6
        assert events[4].dimensions["fairness"] == 7

    @patch("app.orchestrator.evaluator.model_router")
    @pytest.mark.asyncio
    async def test_event_ordering_three_negotiators(self, mock_router):
        """With 3 negotiators: 3 interview pairs + 1 complete = 7 events."""
        call_count = 0

        def _invoke(messages):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return AIMessage(content=_interview_json())
            else:
                return AIMessage(content=_report_json())

        mock_model = MagicMock()
        mock_model.invoke.side_effect = _invoke
        mock_router.get_model.return_value = mock_model

        scenario = _make_scenario(num_negotiators=3)
        terminal_state = _make_terminal_state()

        events = []
        async for event in run_evaluation(terminal_state, scenario):
            events.append(event)

        assert len(events) == 7

        # All interview events before the complete event
        interview_events = [e for e in events if isinstance(e, EvaluationInterviewEvent)]
        complete_events = [e for e in events if isinstance(e, EvaluationCompleteEvent)]
        assert len(interview_events) == 6  # 3 pairs
        assert len(complete_events) == 1

        # The EvaluationCompleteEvent is always last
        assert isinstance(events[-1], EvaluationCompleteEvent)


class TestEvaluationGracefulDegradation:
    """Verify run_evaluation propagates exceptions for the caller to handle."""

    @patch("app.orchestrator.evaluator.model_router")
    @pytest.mark.asyncio
    async def test_run_evaluation_propagates_exception(self, mock_router):
        """When the LLM raises, run_evaluation propagates the error.

        The actual try/except is in the streaming endpoint — here we verify
        that run_evaluation does NOT silently swallow errors.
        """
        mock_router.get_model.side_effect = RuntimeError("Model unavailable")

        scenario = _make_scenario(num_negotiators=2)
        terminal_state = _make_terminal_state()

        with pytest.raises(RuntimeError, match="Model unavailable"):
            async for _event in run_evaluation(terminal_state, scenario):
                pass  # pragma: no cover

    @patch("app.orchestrator.evaluator.model_router")
    @pytest.mark.asyncio
    async def test_evaluator_disabled_yields_nothing(self, mock_router):
        """When evaluator_config.enabled is False, no events are emitted."""
        scenario = _make_scenario(num_negotiators=2)
        scenario["evaluator_config"] = {
            "model_id": "gemini-3-flash-preview",
            "enabled": False,
        }
        terminal_state = _make_terminal_state()

        events = []
        async for event in run_evaluation(terminal_state, scenario):
            events.append(event)

        assert events == []
        # Model should never be called
        mock_router.get_model.assert_not_called()
