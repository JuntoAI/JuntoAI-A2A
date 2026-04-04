"""Milestone summary generator for hybrid agent memory.

At configurable turn intervals, generates compressed strategic summaries
per agent via lightweight LLM calls. Each summary captures key positions,
concessions, disputes, regulatory concerns, and trajectory from the
agent's own perspective (including private reasoning).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import HumanMessage

from app.orchestrator import model_router
from app.orchestrator.state import NegotiationState

logger = logging.getLogger(__name__)


def _format_history(history: list[dict[str, Any]]) -> str:
    """Format negotiation history entries into a readable string."""
    if not history:
        return "(No history yet)"
    parts: list[str] = []
    for entry in history:
        role = entry.get("role", "unknown")
        turn = entry.get("turn_number", "?")
        content = entry.get("content", {})
        if isinstance(content, dict):
            display = (
                content.get("public_message")
                or content.get("reasoning")
                or content.get("observation")
                or str(content)
            )
        else:
            display = str(content)
        parts.append(f"  [Turn {turn} - {role}]: {display}")
    return "\n".join(parts)


def _format_existing_milestones(milestones: list[dict[str, Any]]) -> str:
    """Format existing milestone summaries for context."""
    if not milestones:
        return ""
    parts: list[str] = ["Previous strategic summaries:"]
    for ms in milestones:
        turn = ms.get("turn_number", "?")
        summary = ms.get("summary", "")
        parts.append(f"  As of turn {turn}: {summary}")
    return "\n".join(parts)


def _build_milestone_prompt(
    agent_config: dict[str, Any],
    state: NegotiationState,
) -> str:
    """Build the prompt for milestone summary generation."""
    agent_name = agent_config.get("name", agent_config.get("role", "Agent"))
    agent_role = agent_config.get("role", "")

    history = state.get("history", [])
    formatted_history = _format_history(history)

    existing = state.get("milestone_summaries", {}).get(agent_role, [])
    existing_section = _format_existing_milestones(existing)

    # Agent's private context: goals, budget, inner thoughts from history
    private_parts: list[str] = []
    goals = agent_config.get("goals", [])
    if goals:
        private_parts.append("Goals: " + "; ".join(goals))
    budget = agent_config.get("budget")
    if budget and isinstance(budget, dict):
        budget_str = ", ".join(f"{k}={v}" for k, v in budget.items())
        private_parts.append(f"Budget constraints: {budget_str}")

    # Extract inner thoughts from history for this agent
    inner_thoughts: list[str] = []
    for entry in history:
        if entry.get("role") == agent_role:
            content = entry.get("content", {})
            if isinstance(content, dict):
                thought = content.get("inner_thought")
                if thought:
                    inner_thoughts.append(f"  Turn {entry.get('turn_number', '?')}: {thought}")
    if inner_thoughts:
        private_parts.append("Your inner reasoning history:\n" + "\n".join(inner_thoughts))

    private_context = "\n".join(private_parts) if private_parts else "(No private context)"

    prompt = (
        f"You are summarizing a negotiation from the perspective of {agent_name} ({agent_role}).\n\n"
        f"Produce a concise strategic summary (max 300 tokens) covering:\n"
        f"1. Key positions taken by all parties\n"
        f"2. Major concessions made and received\n"
        f"3. Unresolved disputes or sticking points\n"
        f"4. Regulatory concerns raised (if any)\n"
        f"5. Overall trajectory — is the deal moving toward agreement or deadlock?\n\n"
        f"Include your private strategic assessment based on your goals and reasoning.\n\n"
        f"Negotiation history:\n{formatted_history}\n\n"
    )
    if existing_section:
        prompt += f"{existing_section}\n\n"
    prompt += (
        f"Your private context:\n{private_context}\n\n"
        f"Respond with ONLY the summary text, no JSON wrapping."
    )
    return prompt


async def _generate_single_milestone(
    agent_config: dict[str, Any],
    state: NegotiationState,
) -> tuple[str, dict[str, Any] | None, int]:
    """Generate a milestone summary for a single agent.

    Returns (role, milestone_entry_or_None, tokens_used).
    """
    role = agent_config.get("role", "")
    model_id = agent_config.get("model_id", "")
    tokens_used = 0

    try:
        model = model_router.get_model(model_id)
        prompt = _build_milestone_prompt(agent_config, state)
        messages = [HumanMessage(content=prompt)]

        response = await model.ainvoke(messages, max_tokens=300)

        # Extract text content
        content = response.content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            summary_text = "\n".join(parts) if parts else str(content)
        else:
            summary_text = str(content)

        # Track token usage
        usage = getattr(response, "usage_metadata", None)
        if usage and isinstance(usage, dict):
            tokens_used = usage.get("total_tokens", 0)
        elif usage:
            tokens_used = getattr(usage, "total_tokens", 0)

        turn_number = state.get("turn_count", 0)
        milestone_entry = {
            "turn_number": turn_number,
            "summary": summary_text,
        }
        return role, milestone_entry, tokens_used

    except Exception:
        logger.exception(
            "Milestone generation failed for agent '%s' (model=%s). "
            "Continuing without summary.",
            role,
            model_id,
        )
        return role, None, 0


async def generate_milestones(
    state: NegotiationState,
) -> dict[str, Any]:
    """Generate milestone summaries for all agents.

    Returns a state delta dict with updated ``milestone_summaries``
    and ``total_tokens_used``.
    """
    agents = state.get("scenario_config", {}).get("agents", [])
    current_summaries: dict[str, list[dict[str, Any]]] = {
        k: list(v) for k, v in state.get("milestone_summaries", {}).items()
    }
    total_new_tokens = 0

    # Generate milestones concurrently for all agents
    tasks = [_generate_single_milestone(agent, state) for agent in agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.error("Milestone generation task raised: %s", result)
            continue
        role, entry, tokens = result
        if entry is not None:
            if role not in current_summaries:
                current_summaries[role] = []
            current_summaries[role].append(entry)
        total_new_tokens += tokens

    existing_total = state.get("total_tokens_used", 0)
    return {
        "milestone_summaries": current_summaries,
        "total_tokens_used": existing_total + total_new_tokens,
    }
