"""Unit tests for the post-negotiation evaluator agent.

Covers:
- Interview parse retry + fallback (invalid JSON → retry → neutral fallback with satisfaction_rating=5)
- Scoring parse retry + fallback (invalid JSON → retry → all 5s report)
- Evaluator disabled (enabled=False) yields no events
- Full run_evaluation flow with mocked LLM returning valid JSON
- run_evaluation with LLM returning invalid JSON → graceful fallback
- Evaluation with different scenario types (2-agent, 4-agent, single negotiator)
- Helper functions: _extract_text_from_content, _strip_markdown_fences,
  _resolve_evaluator_model, _get_negotiator_configs
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.models.events import EvaluationCompleteEvent, EvaluationInterviewEvent
from app.orchestrator.evaluator import (
    _extract_text_from_content,
    _get_negotiator_configs,
    _interview_participant,
    _resolve_evaluator_model,
    _score_negotiation,
    _strip_markdown_fences,
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


# ===========================================================================
# Test: Helper functions (_extract_text_from_content, _strip_markdown_fences)
# ===========================================================================


class TestExtractTextFromContent:
    """Test _extract_text_from_content with various LLM response formats."""

    def test_string_content(self):
        assert _extract_text_from_content("hello") == "hello"

    def test_list_of_text_blocks(self):
        content = [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]
        assert _extract_text_from_content(content) == "first\nsecond"

    def test_list_of_strings(self):
        content = ["part1", "part2"]
        assert _extract_text_from_content(content) == "part1\npart2"

    def test_mixed_list(self):
        content = [
            {"type": "text", "text": "block"},
            "raw string",
        ]
        assert _extract_text_from_content(content) == "block\nraw string"

    def test_empty_list_falls_through(self):
        # Empty list with no text blocks → str(content)
        assert _extract_text_from_content([]) == "[]"

    def test_non_text_block_ignored(self):
        content = [{"type": "image", "url": "http://example.com"}]
        # No text parts extracted → falls through to str()
        assert _extract_text_from_content(content) == str(content)

    def test_integer_content(self):
        assert _extract_text_from_content(42) == "42"


class TestStripMarkdownFences:
    """Test _strip_markdown_fences with various fence formats."""

    def test_no_fences(self):
        assert _strip_markdown_fences('{"key": "value"}') == '{"key": "value"}'

    def test_json_fences(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_markdown_fences(text) == '{"key": "value"}'

    def test_plain_fences(self):
        text = '```\n{"key": "value"}\n```'
        assert _strip_markdown_fences(text) == '{"key": "value"}'

    def test_fences_with_whitespace(self):
        text = '  ```json\n{"key": "value"}\n```  '
        assert _strip_markdown_fences(text) == '{"key": "value"}'


# ===========================================================================
# Test: _resolve_evaluator_model and _get_negotiator_configs
# ===========================================================================


class TestResolveEvaluatorModel:
    """Test model resolution logic for the evaluator."""

    def test_uses_evaluator_config_model_id(self):
        scenario = _make_scenario_config(
            evaluator_config={"model_id": "custom-model", "enabled": True},
        )
        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = MagicMock()
            _resolve_evaluator_model(scenario)
            mock_router.get_model.assert_called_once_with(
                "custom-model", fallback_model_id=None,
            )

    def test_falls_back_to_first_negotiator_model(self):
        scenario = _make_scenario_config()  # no evaluator_config
        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = MagicMock()
            _resolve_evaluator_model(scenario)
            mock_router.get_model.assert_called_once_with(
                "gemini-3-flash-preview", fallback_model_id=None,
            )

    def test_raises_when_no_negotiator_agents(self):
        scenario = {
            "agents": [
                {"role": "Regulator", "type": "regulator", "model_id": "x"},
            ],
        }
        with patch("app.orchestrator.evaluator.model_router"):
            with pytest.raises(ValueError, match="No negotiator agent"):
                _resolve_evaluator_model(scenario)


class TestGetNegotiatorConfigs:
    """Test _get_negotiator_configs filters correctly."""

    def test_returns_only_negotiators(self):
        agents = [
            {"role": "Buyer", "type": "negotiator"},
            {"role": "Regulator", "type": "regulator"},
            {"role": "Seller", "type": "negotiator"},
            {"role": "Analyst", "type": "observer"},
        ]
        result = _get_negotiator_configs({"agents": agents})
        assert len(result) == 2
        assert result[0]["role"] == "Buyer"
        assert result[1]["role"] == "Seller"

    def test_default_type_is_negotiator(self):
        """Agents without explicit type default to negotiator."""
        agents = [{"role": "Buyer"}]  # no "type" key
        result = _get_negotiator_configs({"agents": agents})
        assert len(result) == 1

    def test_empty_agents(self):
        assert _get_negotiator_configs({"agents": []}) == []
        assert _get_negotiator_configs({}) == []


# ===========================================================================
# Test: Full run_evaluation with mocked LLM returning valid JSON
# ===========================================================================


class TestRunEvaluationFullFlow:
    """Test run_evaluation end-to-end with mocked LLM returning valid JSON."""

    @pytest.mark.asyncio
    async def test_two_agent_evaluation_yields_correct_events(self):
        """Standard 2-negotiator scenario yields 5 events in correct order."""
        scenario_config = _make_scenario_config()
        terminal_state = _make_terminal_state()

        mock_model = MagicMock()
        # 2 interview calls + 1 scoring call
        mock_model.invoke.side_effect = [
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_report_json()),
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(terminal_state, scenario_config):
                events.append(event)

        # 2 negotiators × (interviewing + complete) + 1 evaluation_complete = 5
        assert len(events) == 5

        # Event 0: Buyer interviewing
        assert isinstance(events[0], EvaluationInterviewEvent)
        assert events[0].agent_name == "Buyer"
        assert events[0].status == "interviewing"
        assert events[0].turn_number == 1

        # Event 1: Buyer complete with results
        assert isinstance(events[1], EvaluationInterviewEvent)
        assert events[1].agent_name == "Buyer"
        assert events[1].status == "complete"
        assert events[1].satisfaction_rating == 8
        assert events[1].felt_respected is True
        assert events[1].is_win_win is True

        # Event 2: Seller interviewing
        assert isinstance(events[2], EvaluationInterviewEvent)
        assert events[2].agent_name == "Seller"
        assert events[2].status == "interviewing"
        assert events[2].turn_number == 2

        # Event 3: Seller complete
        assert isinstance(events[3], EvaluationInterviewEvent)
        assert events[3].agent_name == "Seller"
        assert events[3].status == "complete"
        assert events[3].satisfaction_rating == 8

        # Event 4: Final evaluation report
        assert isinstance(events[4], EvaluationCompleteEvent)
        assert events[4].overall_score == 7
        assert events[4].dimensions["fairness"] == 7
        assert events[4].verdict == "A solid negotiation."
        assert events[4].deal_status == "Agreed"
        assert len(events[4].participant_interviews) == 2

    @pytest.mark.asyncio
    async def test_evaluation_passes_deal_status_from_terminal_state(self):
        """EvaluationCompleteEvent.deal_status comes from terminal_state, not report."""
        terminal_state = _make_terminal_state()
        terminal_state["deal_status"] = "Failed"
        scenario_config = _make_scenario_config()

        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_report_json()),
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(terminal_state, scenario_config):
                events.append(event)

        complete_event = events[-1]
        assert isinstance(complete_event, EvaluationCompleteEvent)
        # deal_status comes from terminal_state, not the report JSON
        assert complete_event.deal_status == "Failed"


# ===========================================================================
# Test: run_evaluation with LLM returning invalid JSON → graceful fallback
# ===========================================================================


class TestRunEvaluationInvalidJsonFallback:
    """Test run_evaluation end-to-end when LLM returns garbage JSON."""

    @pytest.mark.asyncio
    async def test_all_invalid_json_produces_fallback_events(self):
        """When all LLM calls return garbage, evaluation still completes with fallbacks."""
        scenario_config = _make_scenario_config()
        terminal_state = _make_terminal_state()

        mock_model = MagicMock()
        # All calls return garbage — interviews fall back, scoring falls back
        mock_model.invoke.return_value = AIMessage(content="not json at all")

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(terminal_state, scenario_config):
                events.append(event)

        # Still yields 5 events (2 × interviewing/complete + 1 evaluation_complete)
        assert len(events) == 5

        # Interview complete events should have fallback satisfaction_rating=5
        buyer_complete = events[1]
        assert buyer_complete.satisfaction_rating == 5

        seller_complete = events[3]
        assert seller_complete.satisfaction_rating == 5

        # Final report should be fallback with all 5s
        report = events[4]
        assert isinstance(report, EvaluationCompleteEvent)
        assert report.overall_score == 5
        assert report.dimensions["fairness"] == 5
        assert "could not be completed" in report.verdict

    @pytest.mark.asyncio
    async def test_interview_invalid_but_scoring_valid(self):
        """Interviews fail (fallback), but scoring succeeds with valid JSON."""
        scenario_config = _make_scenario_config()
        terminal_state = _make_terminal_state()

        mock_model = MagicMock()
        # First 4 calls are interview attempts (2 agents × 2 tries each) → garbage
        # Last call is scoring → valid
        mock_model.invoke.side_effect = [
            AIMessage(content="garbage"),  # Buyer interview attempt 1
            AIMessage(content="garbage"),  # Buyer interview retry
            AIMessage(content="garbage"),  # Seller interview attempt 1
            AIMessage(content="garbage"),  # Seller interview retry
            AIMessage(content=_valid_report_json()),  # Scoring succeeds
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(terminal_state, scenario_config):
                events.append(event)

        assert len(events) == 5

        # Interviews used fallback
        assert events[1].satisfaction_rating == 5
        assert events[3].satisfaction_rating == 5

        # But scoring succeeded
        report = events[4]
        assert report.overall_score == 7
        assert report.verdict == "A solid negotiation."


# ===========================================================================
# Test: Evaluation with different scenario types
# ===========================================================================


class TestRunEvaluationDifferentScenarios:
    """Test run_evaluation with various scenario configurations."""

    @pytest.mark.asyncio
    async def test_four_agent_scenario_only_interviews_negotiators(self):
        """4-agent scenario (2 negotiators + regulator + observer) only interviews negotiators."""
        agents = [
            _make_agent_config("Buyer"),
            _make_agent_config("Seller"),
            {
                "role": "Regulator", "name": "Regulator", "type": "regulator",
                "model_id": "gemini-3-flash-preview",
                "persona_prompt": "You are a regulator.",
            },
            {
                "role": "Analyst", "name": "Analyst", "type": "observer",
                "model_id": "gemini-3-flash-preview",
                "persona_prompt": "You are an observer.",
            },
        ]
        scenario_config = _make_scenario_config(agents=agents)
        terminal_state = _make_terminal_state()

        mock_model = MagicMock()
        # Only 2 interviews (negotiators) + 1 scoring = 3 LLM calls
        mock_model.invoke.side_effect = [
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_report_json()),
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(terminal_state, scenario_config):
                events.append(event)

        # 2 negotiators × 2 events + 1 complete = 5 (regulator/observer NOT interviewed)
        assert len(events) == 5
        interview_names = [
            e.agent_name for e in events if isinstance(e, EvaluationInterviewEvent)
        ]
        assert "Regulator" not in interview_names
        assert "Analyst" not in interview_names
        assert interview_names == ["Buyer", "Buyer", "Seller", "Seller"]

    @pytest.mark.asyncio
    async def test_single_negotiator_scenario(self):
        """Scenario with only 1 negotiator yields 3 events."""
        agents = [_make_agent_config("Solo")]
        scenario_config = _make_scenario_config(agents=agents)
        terminal_state = _make_terminal_state()

        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content=_valid_interview_json()),  # interview
            AIMessage(content=_valid_report_json()),      # scoring
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(terminal_state, scenario_config):
                events.append(event)

        # 1 negotiator × 2 events + 1 complete = 3
        assert len(events) == 3
        assert events[0].agent_name == "Solo"
        assert events[0].status == "interviewing"
        assert events[1].agent_name == "Solo"
        assert events[1].status == "complete"
        assert isinstance(events[2], EvaluationCompleteEvent)

    @pytest.mark.asyncio
    async def test_evaluation_with_failed_deal_status(self):
        """Evaluation works correctly when deal_status is 'Failed'."""
        terminal_state = {
            "deal_status": "Failed",
            "current_offer": 0.0,
            "turn_count": 15,
            "history": [],
        }
        scenario_config = _make_scenario_config()

        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_report_json()),
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(terminal_state, scenario_config):
                events.append(event)

        report = events[-1]
        assert isinstance(report, EvaluationCompleteEvent)
        assert report.deal_status == "Failed"

    @pytest.mark.asyncio
    async def test_evaluation_with_blocked_deal_status(self):
        """Evaluation works correctly when deal_status is 'Blocked'."""
        terminal_state = {
            "deal_status": "Blocked",
            "current_offer": 50000.0,
            "turn_count": 3,
            "history": [
                {
                    "role": "Buyer", "agent_type": "negotiator",
                    "turn_number": 1,
                    "content": {"public_message": "I offer 50k", "proposed_price": 50000.0},
                },
            ],
        }
        scenario_config = _make_scenario_config()

        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_interview_json()),
            AIMessage(content=_valid_report_json()),
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(terminal_state, scenario_config):
                events.append(event)

        report = events[-1]
        assert report.deal_status == "Blocked"

    @pytest.mark.asyncio
    async def test_markdown_fenced_llm_response_parsed_correctly(self):
        """LLM response wrapped in markdown fences is still parsed correctly."""
        scenario_config = _make_scenario_config()
        terminal_state = _make_terminal_state()

        fenced_interview = "```json\n" + _valid_interview_json() + "\n```"
        fenced_report = "```json\n" + _valid_report_json() + "\n```"

        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content=fenced_interview),
            AIMessage(content=fenced_interview),
            AIMessage(content=fenced_report),
        ]

        with patch("app.orchestrator.evaluator.model_router") as mock_router:
            mock_router.get_model.return_value = mock_model

            events = []
            async for event in run_evaluation(terminal_state, scenario_config):
                events.append(event)

        assert len(events) == 5
        assert events[1].satisfaction_rating == 8
        report = events[-1]
        assert report.overall_score == 7
