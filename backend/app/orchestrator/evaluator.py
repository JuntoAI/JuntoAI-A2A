"""Post-negotiation evaluator agent (standalone, outside LangGraph).

Runs AFTER the LangGraph state machine terminates. Interviews each negotiator
independently, produces a multi-dimensional quality score, and yields SSE events.

This is NOT a LangGraph node. It does NOT modify NegotiationState.
It does NOT increment turn_count.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.models.events import EvaluationCompleteEvent, EvaluationInterviewEvent
from app.orchestrator import model_router
from app.orchestrator.evaluator_prompts import (
    build_interview_system_prompt,
    build_interview_user_prompt,
    build_scoring_system_prompt,
    build_scoring_user_prompt,
)
from app.orchestrator.outputs import EvaluationInterview, EvaluationReport

logger = logging.getLogger(__name__)


def _extract_text_from_content(content: Any) -> str:
    """Extract plain text from an LLM response content field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        if parts:
            return "\n".join(parts)
    return str(content)


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1:]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()
    return stripped


def _resolve_evaluator_model(scenario_config: dict[str, Any]):
    """Resolve the LLM model for the evaluator.

    Uses evaluator_config.model_id if present, else first negotiator's model_id.
    """
    evaluator_config = scenario_config.get("evaluator_config")
    if evaluator_config and evaluator_config.get("model_id"):
        return model_router.get_model(
            evaluator_config["model_id"],
            fallback_model_id=evaluator_config.get("fallback_model_id"),
        )

    # Fallback: first negotiator's model_id
    agents = scenario_config.get("agents", [])
    for agent in agents:
        if agent.get("type", "negotiator") == "negotiator":
            return model_router.get_model(
                agent["model_id"],
                fallback_model_id=agent.get("fallback_model_id"),
            )

    raise ValueError("No negotiator agent found in scenario config")


def _get_negotiator_configs(scenario_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return agent configs where type == 'negotiator'."""
    return [
        a for a in scenario_config.get("agents", [])
        if a.get("type", "negotiator") == "negotiator"
    ]


def _fallback_interview() -> EvaluationInterview:
    """Return a neutral fallback interview when parsing fails."""
    return EvaluationInterview(
        feels_served=True,
        felt_respected=True,
        is_win_win=True,
        criticism="Unable to assess",
        satisfaction_rating=5,
    )


def _fallback_report(
    interviews: list[dict[str, Any]], deal_status: str,
) -> EvaluationReport:
    """Return a neutral fallback report when scoring fails."""
    return EvaluationReport(
        participant_interviews=interviews,
        dimensions={
            "fairness": 5,
            "mutual_respect": 5,
            "value_creation": 5,
            "satisfaction": 5,
        },
        overall_score=5,
        verdict="Evaluation could not be completed — defaulting to neutral score.",
        deal_status=deal_status,
    )


async def _interview_participant(
    model,
    agent_config: dict[str, Any],
    history: list[dict[str, Any]],
    terminal_state: dict[str, Any],
) -> EvaluationInterview:
    """Conduct a single evaluation interview with one participant."""
    system_prompt = build_interview_system_prompt(agent_config)
    user_prompt = build_interview_user_prompt(agent_config, history, terminal_state)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = model.invoke(messages)
    response_text = _extract_text_from_content(response.content)

    try:
        cleaned = _strip_markdown_fences(response_text)
        return EvaluationInterview.model_validate_json(cleaned)
    except Exception:
        role = agent_config.get("role", "unknown")
        logger.warning("Interview parse failed for '%s'. Retrying.", role)

        # Retry with explicit JSON instruction
        from langchain_core.messages import AIMessage
        if response_text.strip():
            messages.append(AIMessage(content=response_text))
        messages.append(
            HumanMessage(
                content="Your previous response was not valid JSON. "
                "Please respond with ONLY valid JSON matching the schema."
            )
        )
        try:
            response = model.invoke(messages)
            response_text = _extract_text_from_content(response.content)
            cleaned = _strip_markdown_fences(response_text)
            return EvaluationInterview.model_validate_json(cleaned)
        except Exception:
            logger.warning(
                "Retry also failed for '%s'. Using fallback interview.", role,
            )
            return _fallback_interview()


async def _score_negotiation(
    model,
    interviews: list[dict[str, Any]],
    history: list[dict[str, Any]],
    terminal_state: dict[str, Any],
    scenario_config: dict[str, Any],
) -> EvaluationReport:
    """Produce the final evaluation score from all interviews + history."""
    system_prompt = build_scoring_system_prompt()
    user_prompt = build_scoring_user_prompt(
        interviews, history, terminal_state, scenario_config,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = model.invoke(messages)
    response_text = _extract_text_from_content(response.content)
    deal_status = terminal_state.get("deal_status", "")

    try:
        cleaned = _strip_markdown_fences(response_text)
        return EvaluationReport.model_validate_json(cleaned)
    except Exception:
        logger.warning("Scoring parse failed. Retrying.")

        from langchain_core.messages import AIMessage
        if response_text.strip():
            messages.append(AIMessage(content=response_text))
        messages.append(
            HumanMessage(
                content="Your previous response was not valid JSON. "
                "Please respond with ONLY valid JSON matching the schema."
            )
        )
        try:
            response = model.invoke(messages)
            response_text = _extract_text_from_content(response.content)
            cleaned = _strip_markdown_fences(response_text)
            return EvaluationReport.model_validate_json(cleaned)
        except Exception:
            logger.warning("Retry also failed. Using fallback report.")
            return _fallback_report(interviews, deal_status)


async def run_evaluation(
    terminal_state: dict[str, Any],
    scenario_config: dict[str, Any],
) -> AsyncGenerator[EvaluationInterviewEvent | EvaluationCompleteEvent, None]:
    """Run post-negotiation evaluation. Yields SSE events as it progresses.

    Called from the streaming endpoint AFTER run_negotiation() completes.
    NOT a LangGraph node. Does NOT modify NegotiationState.

    Interviews are run concurrently via asyncio.gather() for speed.
    """
    import asyncio

    evaluator_config = scenario_config.get("evaluator_config")
    if evaluator_config and not evaluator_config.get("enabled", True):
        return

    model = _resolve_evaluator_model(scenario_config)
    negotiators = _get_negotiator_configs(scenario_config)
    history = terminal_state.get("history", [])
    deal_status = terminal_state.get("deal_status", "")

    # Emit all "interviewing" events upfront
    for step, agent_config in enumerate(negotiators, 1):
        yield EvaluationInterviewEvent(
            event_type="evaluation_interview",
            agent_name=agent_config["role"],
            turn_number=step,
            status="interviewing",
        )

    # Run all interviews concurrently
    interview_tasks = [
        _interview_participant(model, agent_config, history, terminal_state)
        for agent_config in negotiators
    ]
    interview_results = await asyncio.gather(*interview_tasks)

    interviews: list[dict[str, Any]] = []
    for step, (agent_config, interview) in enumerate(
        zip(negotiators, interview_results), 1,
    ):
        role = agent_config["role"]
        interviews.append({"role": role, **interview.model_dump()})

        # Emit "complete" event with results
        yield EvaluationInterviewEvent(
            event_type="evaluation_interview",
            agent_name=role,
            turn_number=step,
            status="complete",
            satisfaction_rating=interview.satisfaction_rating,
            felt_respected=interview.felt_respected,
            is_win_win=interview.is_win_win,
        )

    # Scoring call
    report = await _score_negotiation(
        model, interviews, history, terminal_state, scenario_config,
    )

    yield EvaluationCompleteEvent(
        event_type="evaluation_complete",
        dimensions=report.dimensions,
        overall_score=report.overall_score,
        verdict=report.verdict,
        participant_interviews=interviews,
        deal_status=deal_status,
    )
