"""Confirmation round node for the LangGraph negotiation graph.

Prompts each negotiator for explicit accept/reject after price convergence.
Does NOT increment turn_count — this is a confirmation phase, not a turn.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.orchestrator import model_router
from app.orchestrator.exceptions import AgentOutputParseError
from app.orchestrator.outputs import ConfirmationOutput
from app.orchestrator.state import NegotiationState

logger = logging.getLogger(__name__)

_CONFIRMATION_SCHEMA = json.dumps(
    {
        "accept": "<bool: true to accept the deal, false to reject>",
        "final_statement": "<string: your final statement about the deal>",
        "conditions": "<list[string]: any conditions attached (empty if none)>",
    },
    indent=2,
)


def _find_agent_config(role: str, state: NegotiationState) -> dict[str, Any]:
    """Look up agent config from scenario_config by role."""
    agents = state.get("scenario_config", {}).get("agents", [])
    for agent in agents:
        if agent.get("role") == role:
            return agent
    raise AgentOutputParseError(
        agent_name=role,
        raw_response=f"Agent role {role!r} not found in scenario_config agents",
    )


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


def _build_confirmation_messages(
    agent_config: dict[str, Any], state: NegotiationState,
) -> list[SystemMessage | HumanMessage]:
    """Build the confirmation prompt messages for a negotiator."""
    role = agent_config.get("role", "")
    persona = agent_config.get("persona_prompt", "")
    goals = agent_config.get("goals", [])

    system_parts: list[str] = [persona] if persona else []
    if goals:
        system_parts.append("\nYour goals:")
        for goal in goals:
            system_parts.append(f"- {goal}")
    system_parts.append(
        f"\nYou MUST respond with valid JSON matching this schema:\n{_CONFIRMATION_SCHEMA}"
    )

    current_offer = state.get("current_offer", 0.0)
    turn_count = state.get("turn_count", 0)

    # Gather recent public messages for context
    history = state.get("history", [])
    recent_messages: list[str] = []
    for entry in history[-6:]:
        content = entry.get("content", {})
        if isinstance(content, dict):
            msg = content.get("public_message", "")
            if msg:
                recent_messages.append(f"  [{entry.get('role', '?')}]: {msg}")

    user_parts: list[str] = [
        "The negotiation has reached a potential agreement.",
        f"Current offer on the table: {current_offer}",
        f"This was reached after {turn_count} turns of negotiation.",
    ]
    if recent_messages:
        user_parts.append("\nRecent messages:")
        user_parts.extend(recent_messages)
    user_parts.append(
        "\nDo you accept this deal? Consider whether the terms meet your goals "
        "and constraints. If you accept with conditions, list them. "
        "If the deal does not serve your interests, reject it."
    )
    user_parts.append("\nRespond with JSON only.")

    return [
        SystemMessage(content="\n".join(system_parts)),
        HumanMessage(content="\n".join(user_parts)),
    ]


def _parse_confirmation(response_text: str, role: str) -> ConfirmationOutput:
    """Parse LLM response as ConfirmationOutput. Raises AgentOutputParseError on failure."""
    cleaned = _strip_markdown_fences(response_text)
    try:
        return ConfirmationOutput.model_validate_json(cleaned)
    except Exception as exc:
        raise AgentOutputParseError(agent_name=role, raw_response=response_text) from exc


def _fallback_rejection(role: str) -> ConfirmationOutput:
    """Return a fallback rejection when parsing fails after retry."""
    return ConfirmationOutput(
        accept=False,
        final_statement=f"[{role} could not provide a clear response. Treating as rejection.]",
        conditions=[],
    )


def confirmation_node(state: NegotiationState) -> dict[str, Any]:
    """Prompt the next pending negotiator for confirmation.

    Does NOT increment turn_count. Processes one negotiator per invocation,
    then returns to dispatcher. Dispatcher re-routes here until
    confirmation_pending is empty.
    """
    pending = list(state.get("confirmation_pending", []))
    if not pending:
        return {}

    role = pending[0]
    remaining = pending[1:]

    agent_config = _find_agent_config(role, state)
    model_overrides = state.get("model_overrides", {})
    effective_model_id = model_overrides.get(role, agent_config["model_id"])
    model = model_router.get_model(
        effective_model_id,
        fallback_model_id=agent_config.get("fallback_model_id"),
    )

    messages = _build_confirmation_messages(agent_config, state)

    # Invoke LLM
    response = model.invoke(messages)
    response_text = _extract_text_from_content(response.content)

    # Parse with retry + fallback
    try:
        parsed = _parse_confirmation(response_text, role)
    except AgentOutputParseError:
        logger.warning(
            "First confirmation parse failed for '%s'. Retrying.", role,
        )
        if response_text.strip():
            from langchain_core.messages import AIMessage
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
            parsed = _parse_confirmation(response_text, role)
        except Exception:
            logger.warning(
                "Retry also failed for '%s'. Using fallback rejection.", role,
            )
            parsed = _fallback_rejection(role)

    # Build history entry (agent_type = "confirmation")
    history_entry = {
        "role": role,
        "agent_type": "confirmation",
        "turn_number": state.get("turn_count", 0),
        "content": parsed.model_dump(),
    }

    return {
        "history": [history_entry],
        "confirmation_pending": remaining,
    }
