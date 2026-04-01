"""Generic agent node factory for LangGraph negotiation orchestration.

Produces a callable node for any agent role. The agent's ``type`` field
(``negotiator`` | ``regulator`` | ``observer``) from the scenario config
determines the output schema and state-update behaviour.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.orchestrator import model_router
from app.orchestrator.exceptions import AgentOutputParseError
from app.orchestrator.outputs import NegotiatorOutput, ObserverOutput, RegulatorOutput
from app.orchestrator.state import NegotiationState

logger = logging.getLogger(__name__)

# Maps agent type → Pydantic output model class
_OUTPUT_MODEL_MAP: dict[str, type] = {
    "negotiator": NegotiatorOutput,
    "regulator": RegulatorOutput,
    "observer": ObserverOutput,
}

# JSON schema snippets shown to the LLM so it knows the expected format
_OUTPUT_SCHEMA_DESCRIPTIONS: dict[str, str] = {
    "negotiator": json.dumps(
        {
            "inner_thought": "<string: your private reasoning>",
            "public_message": "<string: what you say publicly>",
            "proposed_price": "<float: your proposed price>",
            "extra_fields": "<object: optional additional fields>",
        },
        indent=2,
    ),
    "regulator": json.dumps(
        {
            "status": "<string: one of CLEAR, WARNING, BLOCKED>",
            "reasoning": "<string: your regulatory reasoning>",
        },
        indent=2,
    ),
    "observer": json.dumps(
        {
            "observation": "<string: your observation>",
            "recommendation": "<string: optional recommendation>",
        },
        indent=2,
    ),
}


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def create_agent_node(agent_role: str) -> Callable[[NegotiationState], dict[str, Any]]:
    """Create a LangGraph node callable for the given agent role."""

    def _node(state: NegotiationState) -> dict[str, Any]:
        # 1. Look up agent config
        agent_config = _find_agent_config(agent_role, state)
        agent_type: str = agent_config.get("type", "negotiator")
        agent_name: str = agent_config.get("name", agent_role)

        # 2. Get LLM via model router
        model = model_router.get_model(
            agent_config["model_id"],
            fallback_model_id=agent_config.get("fallback_model_id"),
        )

        # 3. Build prompt
        system_msg, user_msg = _build_prompt(agent_config, state)

        # 4. Invoke LLM
        response: AIMessage = model.invoke([SystemMessage(content=system_msg), HumanMessage(content=user_msg)])
        response_text = response.content if isinstance(response.content, str) else str(response.content)

        # 5. Parse output (retry once on failure)
        try:
            parsed = _parse_output(response_text, agent_type, agent_name)
        except AgentOutputParseError:
            # Retry with explicit JSON instruction
            retry_msg = user_msg + "\n\nYour previous response was not valid JSON. Please respond with ONLY valid JSON matching the schema."
            response = model.invoke([SystemMessage(content=system_msg), HumanMessage(content=retry_msg)])
            response_text = response.content if isinstance(response.content, str) else str(response.content)
            parsed = _parse_output(response_text, agent_type, agent_name)

        # 6. Build state delta
        state_delta = _update_state(parsed, agent_type, agent_role, state)

        # 7. Advance turn order
        turn_delta = _advance_turn_order(state)

        # 8. Merge deltas
        merged = {**state_delta, **turn_delta}
        return merged

    return _node


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_agent_config(agent_role: str, state: NegotiationState) -> dict[str, Any]:
    """Look up agent config from scenario_config by role.

    Raises ``AgentOutputParseError`` if the role is not found.
    """
    agents = state.get("scenario_config", {}).get("agents", [])
    for agent in agents:
        if agent.get("role") == agent_role:
            return agent
    raise AgentOutputParseError(
        agent_name=agent_role,
        raw_response=f"Agent role {agent_role!r} not found in scenario_config agents",
    )


def _build_prompt(agent_config: dict[str, Any], state: NegotiationState) -> tuple[str, str]:
    """Construct (system_message, user_message) for the agent's LLM call.

    System message includes: persona_prompt, goals, budget, hidden_context,
    and the output JSON schema for the agent's type.

    User message includes: history, current_offer, turn info, JSON instruction.
    """
    agent_type: str = agent_config.get("type", "negotiator")
    role: str = agent_config.get("role", "")

    # --- System message ---
    parts: list[str] = []

    persona = agent_config.get("persona_prompt", "")
    if persona:
        parts.append(persona)

    goals = agent_config.get("goals", [])
    if goals:
        parts.append("\nYour goals:")
        for goal in goals:
            parts.append(f"- {goal}")

    budget = agent_config.get("budget")
    if budget and isinstance(budget, dict):
        budget_str = ", ".join(f"{k}={v}" for k, v in budget.items())
        parts.append(f"\nBudget constraints: {budget_str}")

    # Hidden context injection
    hidden_context = state.get("hidden_context", {})
    role_context = hidden_context.get(role)
    if role_context is not None:
        if isinstance(role_context, dict):
            ctx_lines = [f"  {k}: {v}" for k, v in role_context.items()]
            parts.append("\nConfidential information:\n" + "\n".join(ctx_lines))
        else:
            parts.append(f"\nConfidential information:\n  {role_context}")

    # Output schema
    schema = _OUTPUT_SCHEMA_DESCRIPTIONS.get(agent_type, "")
    if schema:
        parts.append(f"\nYou MUST respond with valid JSON matching this schema:\n{schema}")

    system_message = "\n".join(parts)

    # --- User message ---
    user_parts: list[str] = []

    history = state.get("history", [])
    if history:
        user_parts.append("Negotiation history so far:")
        for entry in history:
            entry_role = entry.get("role", "unknown")
            content = entry.get("content", {})
            if isinstance(content, dict):
                # Show public_message for negotiators, reasoning for regulators, observation for observers
                display = content.get("public_message") or content.get("reasoning") or content.get("observation") or str(content)
            else:
                display = str(content)
            user_parts.append(f"  [{entry_role}]: {display}")

    current_offer = state.get("current_offer", 0.0)
    user_parts.append(f"\nCurrent offer: {current_offer}")

    turn_count = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 15)
    user_parts.append(f"Turn: {turn_count} of {max_turns}")

    user_parts.append("\nRespond with JSON only.")

    user_message = "\n".join(user_parts)

    return system_message, user_message


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from LLM output."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1:]
        # Remove closing fence
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()
    return stripped


def _parse_output(
    response_text: str,
    agent_type: str,
    agent_name: str = "unknown",
) -> NegotiatorOutput | RegulatorOutput | ObserverOutput:
    """Parse LLM response JSON into the correct output model by agent type.

    Strips markdown code fences if present before parsing.
    Raises ``AgentOutputParseError`` on invalid JSON or schema mismatch.
    """
    model_cls = _OUTPUT_MODEL_MAP.get(agent_type)
    if model_cls is None:
        raise AgentOutputParseError(agent_name, response_text)
    cleaned = _strip_markdown_fences(response_text)
    try:
        return model_cls.model_validate_json(cleaned)
    except Exception as exc:
        raise AgentOutputParseError(agent_name, response_text) from exc


def _update_state(
    parsed_output: NegotiatorOutput | RegulatorOutput | ObserverOutput,
    agent_type: str,
    role: str,
    state: NegotiationState,
) -> dict[str, Any]:
    """Produce a state delta dict based on agent type and parsed output.

    Returns a partial state dict that LangGraph merges into the full state.
    For ``agent_states``, the delta contains the FULL agent_states dict
    (LangGraph replaces the whole value, not individual keys).
    """
    # History entry — always appended
    history_entry = {
        "role": role,
        "agent_type": agent_type,
        "turn_number": state.get("turn_count", 0),
        "content": parsed_output.model_dump(),
    }

    delta: dict[str, Any] = {"history": [history_entry]}

    if agent_type == "negotiator":
        assert isinstance(parsed_output, NegotiatorOutput)
        proposed = parsed_output.proposed_price

        # Copy full agent_states and update this role
        agent_states = {k: dict(v) for k, v in state.get("agent_states", {}).items()}
        if role in agent_states:
            agent_states[role]["last_proposed_price"] = proposed

        delta["current_offer"] = proposed
        delta["agent_states"] = agent_states

    elif agent_type == "regulator":
        assert isinstance(parsed_output, RegulatorOutput)

        # Copy full agent_states and update this role
        agent_states = {k: dict(v) for k, v in state.get("agent_states", {}).items()}

        global_warning_count = state.get("warning_count", 0)

        if parsed_output.status == "WARNING":
            global_warning_count += 1
            if role in agent_states:
                agent_states[role]["warning_count"] = agent_states[role].get("warning_count", 0) + 1

        delta["warning_count"] = global_warning_count
        delta["agent_states"] = agent_states

        # Check for block conditions
        role_warnings = agent_states.get(role, {}).get("warning_count", 0)
        if parsed_output.status == "BLOCKED" or role_warnings >= 3:
            delta["deal_status"] = "Blocked"

    # Observer: only history entry, no other state changes

    return delta


def _advance_turn_order(state: NegotiationState) -> dict[str, Any]:
    """Advance turn_order_index and set current_speaker.

    Returns a state delta with ``turn_order_index``, ``current_speaker``,
    and optionally ``turn_count`` (incremented on wrap).
    """
    turn_order = state.get("turn_order", [])
    if not turn_order:
        return {}

    current_idx = state.get("turn_order_index", 0)
    new_idx = (current_idx + 1) % len(turn_order)

    delta: dict[str, Any] = {
        "turn_order_index": new_idx,
        "current_speaker": turn_order[new_idx],
    }

    # Wrap: increment turn_count
    if new_idx == 0:
        delta["turn_count"] = state.get("turn_count", 0) + 1

    return delta
