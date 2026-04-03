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
from pydantic import BaseModel

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
            "proposed_price": "<float: your proposed value>",
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


def _fallback_output(
    agent_type: str,
    agent_name: str,
    state: NegotiationState | None = None,
    agent_role: str = "",
) -> BaseModel:
    """Return a safe fallback output when the LLM fails to produce valid JSON.

    For negotiators, reuses the agent's last proposed price (from
    ``agent_states``) so a parse failure doesn't reset the offer to 0
    and corrupt agreement detection.
    """
    if agent_type == "negotiator":
        # Recover last real proposal so we hold the line instead of
        # emitting 0.0 which maps to the scenario default.
        last_price = 0.0
        if state and agent_role:
            agent_states = state.get("agent_states", {})
            last_price = agent_states.get(agent_role, {}).get(
                "last_proposed_price", 0.0,
            )
        return NegotiatorOutput(
            inner_thought=f"[{agent_name} is gathering their thoughts...]",
            public_message="I need a moment to consider my position. Let me think about this.",
            proposed_price=last_price,
        )
    elif agent_type == "regulator":
        return RegulatorOutput(
            status="CLEAR",
            reasoning=f"[{agent_name} is reviewing the current state of the discussion.]",
        )
    else:
        return ObserverOutput(
            observation=f"[{agent_name} is observing the discussion.]",
        )


_VALUE_FORMAT_HINTS: dict[str, str] = {
    "currency": "numeric amount in the scenario's currency (e.g. 110000 for €110,000)",
    "time_from_22": (
        "number of MINUTES after 10:00 PM. "
        "Examples: 0 = 10:00 PM, 60 = 11:00 PM, 90 = 11:30 PM, "
        "120 = 12:00 AM (midnight), 150 = 12:30 AM, 180 = 1:00 AM. "
        "You MUST use this encoding, do NOT put a clock time here"
    ),
    "percent": "a percentage value (e.g. 75 for 75%)",
    "number": "a plain numeric value",
}


def _get_negotiator_schema(value_label: str, value_format: str = "currency") -> str:
    """Return the negotiator JSON schema with a contextual proposed_price description."""
    hint = _VALUE_FORMAT_HINTS.get(value_format, _VALUE_FORMAT_HINTS["number"])
    return json.dumps(
        {
            "inner_thought": "<string: your private reasoning>",
            "public_message": "<string: what you say publicly>",
            "proposed_price": f"<float: your proposed {value_label.lower()} — {hint}>",
            "extra_fields": "<object: optional additional fields>",
        },
        indent=2,
    )


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

        # 1b. Increment turn_count BEFORE the negotiator speaks so that:
        #     - The history entry records the correct turn number
        #     - The following regulator/observer shares the same turn number
        #     Regulators and observers do NOT increment — they are part of
        #     the preceding negotiator's turn.
        effective_state = state
        if agent_type == "negotiator":
            new_turn_count = state.get("turn_count", 0) + 1
            effective_state = {**state, "turn_count": new_turn_count}

        # 2. Get LLM via model router (apply model override if present)
        model_overrides = state.get("model_overrides", {})
        effective_model_id = model_overrides.get(agent_role, agent_config["model_id"])
        model = model_router.get_model(
            effective_model_id,
            fallback_model_id=agent_config.get("fallback_model_id"),
        )

        # 3. Build prompt
        messages = _build_messages(agent_config, effective_state)

        # 4. Invoke LLM
        response: AIMessage = model.invoke(messages)
        response_text = response.content if isinstance(response.content, str) else str(response.content)

        # Track token usage
        tokens_used = 0
        usage = getattr(response, "usage_metadata", None)
        if usage and isinstance(usage, dict):
            tokens_used += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        elif usage:
            tokens_used += getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)

        # 5. Parse output (retry once on failure)
        logger.debug(
            "Raw LLM response for agent '%s' (type=%s, model=%s): %s",
            agent_name, agent_type, effective_model_id, response_text[:500],
        )
        try:
            parsed = _parse_output(response_text, agent_type, agent_name)
        except AgentOutputParseError:
            logger.warning(
                "First parse failed for agent '%s'. Raw response (%d chars): %s",
                agent_name, len(response_text), response_text[:500],
            )
            # Retry with explicit JSON instruction
            # Only include the failed response if it's non-empty (Gemini rejects empty parts)
            if response_text.strip():
                messages.append(AIMessage(content=response_text))
            messages.append(HumanMessage(content="Your previous response was not valid JSON. Please respond with ONLY valid JSON matching the schema."))
            try:
                response = model.invoke(messages)
                response_text = response.content if isinstance(response.content, str) else str(response.content)
                logger.debug(
                    "Retry LLM response for agent '%s': %s",
                    agent_name, response_text[:500],
                )
                # Add retry tokens
                usage = getattr(response, "usage_metadata", None)
                if usage and isinstance(usage, dict):
                    tokens_used += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                elif usage:
                    tokens_used += getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)
                parsed = _parse_output(response_text, agent_type, agent_name)
            except Exception as retry_exc:
                logger.warning(
                    "Retry also failed for agent '%s': %s. "
                    "Retry raw response (%d chars): %s. Using fallback response.",
                    agent_name, retry_exc, len(response_text), response_text[:500],
                )
                parsed = _fallback_output(agent_type, agent_name, effective_state, agent_role)

        # 6. Build state delta (uses effective_state so turn_number is correct)
        state_delta = _update_state(parsed, agent_type, agent_role, effective_state)

        # 7. Advance turn order (index + next speaker only, no turn_count)
        turn_delta = _advance_turn_order(state)

        # 8. Merge deltas
        merged = {**state_delta, **turn_delta}
        # Always carry turn_count forward so it survives regulator/observer
        # nodes and is present in the final state for transcript generation.
        merged["turn_count"] = effective_state.get("turn_count", state.get("turn_count", 0))
        merged["total_tokens_used"] = state.get("total_tokens_used", 0) + tokens_used
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

    .. note::

       The public API (return type) is unchanged for backward compatibility
       with tests and callers.  Use :func:`_build_messages` when you need
       the full multi-turn message list for the LLM call.
    """
    agent_type: str = agent_config.get("type", "negotiator")
    role: str = agent_config.get("role", "")

    system_message = _build_system_message(agent_config, state)

    # --- User message (flat format, kept for backward compat) ---
    user_parts: list[str] = []

    history = state.get("history", [])
    if history:
        user_parts.append("Negotiation history so far:")
        for entry in history:
            entry_role = entry.get("role", "unknown")
            content = entry.get("content", {})
            if isinstance(content, dict):
                display = content.get("public_message") or content.get("reasoning") or content.get("observation") or str(content)
            else:
                display = str(content)
            user_parts.append(f"  [{entry_role}]: {display}")

    current_offer = state.get("current_offer", 0.0)
    neg_params = state.get("scenario_config", {}).get("negotiation_params", {})
    value_label = neg_params.get("value_label", "Price")
    value_format = neg_params.get("value_format", "currency")
    user_parts.append(f"\nCurrent {value_label.lower()} on the table: {current_offer}")
    if value_format == "time_from_22":
        user_parts.append(
            "Remember: proposed_price is in MINUTES after 10:00 PM "
            "(0=10PM, 60=11PM, 90=11:30PM, 120=midnight, 180=1AM)."
        )

    agent_states = state.get("agent_states", {})
    my_state = agent_states.get(role, {})
    last_price = my_state.get("last_proposed_price", 0.0)
    if last_price > 0:
        user_parts.append(f"Your last proposed value: {last_price}")
        user_parts.append("You MUST propose a DIFFERENT value this turn.")

    turn_count = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 15)
    user_parts.append(f"Turn: {turn_count} of {max_turns}")

    user_parts.append("\nRespond with JSON only.")

    user_message = "\n".join(user_parts)

    return system_message, user_message


def _build_system_message(agent_config: dict[str, Any], state: NegotiationState) -> str:
    """Build the system message with persona, goals, budget, context, and rules."""
    agent_type: str = agent_config.get("type", "negotiator")
    role: str = agent_config.get("role", "")

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

    # Custom prompt injection
    custom_prompts = state.get("custom_prompts", {})
    custom_prompt = custom_prompts.get(role)
    if custom_prompt:
        parts.append(f"\nAdditional user instructions:\n{custom_prompt}")

    # Output schema
    if agent_type == "negotiator":
        neg_params = state.get("scenario_config", {}).get("negotiation_params", {})
        value_label = neg_params.get("value_label", "Price")
        value_format = neg_params.get("value_format", "currency")
        schema = _get_negotiator_schema(value_label, value_format)
    else:
        schema = _OUTPUT_SCHEMA_DESCRIPTIONS.get(agent_type, "")
    if schema:
        parts.append(f"\nYou MUST respond with valid JSON matching this schema:\n{schema}")

    # Negotiation strategy instructions (prevent loops)
    if agent_type == "negotiator":
        parts.append(
            "\nNEGOTIATION RULES — follow these strictly:"
            "\n- NEVER reveal your maximum or minimum budget to the other party."
            "\n- NEVER repeat the same price twice in a row. Each proposal must move."
            "\n- When you make a concession on price, demand something in return (terms, timeline, scope)."
            "\n- If the other party's offer is far from your target, counter with reasoning and data, not just a different number."
            "\n- Vary your arguments each turn. Do not restate the same points verbatim."
            "\n- If you are stuck, introduce a new dimension (payment terms, milestones, guarantees) to create movement."
            "\n- Your proposed_price MUST be different from your last proposed_price."
        )
    elif agent_type == "regulator":
        parts.append(
            "\nREGULATOR RULES — follow these strictly:"
            "\n- Do NOT rubber-stamp agreements. Scrutinize every claim."
            "\n- If a party says 'we comply' without specifics, issue a WARNING demanding documentation."
            "\n- Track unresolved items across turns. Do not let parties ignore your previous warnings."
            "\n- Vary your analysis each turn. Raise new concerns, don't just repeat old ones."
            "\n- You may only issue ONE status per response: CLEAR, WARNING, or BLOCKED."
            "\n- Do NOT describe multiple warnings in a single response. If you see multiple issues, pick the most severe one."
            "\n- Use BLOCKED only when you have already issued warnings on prior turns and the party has not corrected course."
        )
        # Tell the regulator how many warnings have been issued so far
        # so it can calibrate its response accurately.
        current_warnings = state.get("warning_count", 0)
        if current_warnings > 0:
            parts.append(
                f"\nCurrent warning count: {current_warnings} of 3. "
                f"At 3 warnings the deal is automatically blocked."
            )

    return "\n".join(parts)


def _extract_display_text(entry: dict[str, Any]) -> str:
    """Extract the display text from a history entry."""
    content = entry.get("content", {})
    if isinstance(content, dict):
        return (
            content.get("public_message")
            or content.get("reasoning")
            or content.get("observation")
            or str(content)
        )
    return str(content)


def _build_messages(
    agent_config: dict[str, Any], state: NegotiationState,
) -> list[SystemMessage | HumanMessage | AIMessage]:
    """Build a multi-turn message list for the LLM call.

    Instead of cramming the entire history into a single user message,
    this converts each history entry into a proper LangChain message:

    - Entries from *this* agent → ``AIMessage`` (things "I" said before)
    - Entries from *other* agents → ``HumanMessage`` (things "they" said)

    This gives the LLM genuine conversational context so it understands
    what it already said and can build on it rather than starting fresh.

    The final ``HumanMessage`` contains the current negotiation status
    (offer, turn count, last price) and the JSON instruction.
    """
    role: str = agent_config.get("role", "")

    system_msg = _build_system_message(agent_config, state)
    messages: list[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=system_msg),
    ]

    # Convert history into alternating AI/Human messages
    history = state.get("history", [])
    for entry in history:
        entry_role = entry.get("role", "unknown")
        display = _extract_display_text(entry)
        label = f"[{entry_role}]: {display}"

        if entry_role == role:
            # This agent's own past message → AIMessage
            messages.append(AIMessage(content=label))
        else:
            # Another agent's message → HumanMessage
            messages.append(HumanMessage(content=label))

    # Final instruction message with current state
    instruction_parts: list[str] = []

    neg_params = state.get("scenario_config", {}).get("negotiation_params", {})
    value_label = neg_params.get("value_label", "Price")
    value_format = neg_params.get("value_format", "currency")

    current_offer = state.get("current_offer", 0.0)
    instruction_parts.append(f"Current {value_label.lower()} on the table: {current_offer}")
    if value_format == "time_from_22":
        instruction_parts.append(
            "Remember: proposed_price is in MINUTES after 10:00 PM "
            "(0=10PM, 60=11PM, 90=11:30PM, 120=midnight, 180=1AM)."
        )

    agent_states = state.get("agent_states", {})
    my_state = agent_states.get(role, {})
    last_price = my_state.get("last_proposed_price", 0.0)
    if last_price > 0:
        instruction_parts.append(f"Your last proposed value: {last_price}")
        instruction_parts.append("You MUST propose a DIFFERENT value this turn.")

    turn_count = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 15)
    instruction_parts.append(f"Turn: {turn_count} of {max_turns}")

    instruction_parts.append("\nRespond with JSON only.")

    messages.append(HumanMessage(content="\n".join(instruction_parts)))

    return messages


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
            # Only update last_proposed_price if the agent actually proposed
            # a non-zero value. A 0 proposal means the agent stalled or
            # couldn't decide — keep the previous price to avoid breaking
            # agreement detection.
            if proposed > 0:
                agent_states[role]["last_proposed_price"] = proposed

        if proposed > 0:
            delta["current_offer"] = proposed
        delta["agent_states"] = agent_states

    elif agent_type == "regulator":
        assert isinstance(parsed_output, RegulatorOutput)

        # Copy full agent_states and update this role
        agent_states = {k: dict(v) for k, v in state.get("agent_states", {}).items()}

        global_warning_count = state.get("warning_count", 0)

        effective_status = parsed_output.status

        # Downgrade BLOCKED to WARNING if no prior warnings exist for this regulator.
        # Regulators must warn before they can block (3 warnings = block).
        role_warnings = agent_states.get(role, {}).get("warning_count", 0)
        if effective_status == "BLOCKED" and role_warnings == 0:
            logger.info(
                "Regulator '%s' attempted BLOCKED with 0 prior warnings — downgrading to WARNING.",
                role,
            )
            effective_status = "WARNING"
            # Update the history entry to reflect the downgrade
            history_entry["content"] = {**parsed_output.model_dump(), "status": effective_status}

        if effective_status in ("WARNING", "BLOCKED"):
            # Count both WARNING and BLOCKED toward the warning tally.
            # A BLOCKED response is the final escalation — it still
            # represents a warning event and must be reflected in the
            # total so the UI/transcript shows the correct count.
            global_warning_count += 1
            if role in agent_states:
                agent_states[role]["warning_count"] = agent_states[role].get("warning_count", 0) + 1

        delta["warning_count"] = global_warning_count
        delta["agent_states"] = agent_states

        # Check for block conditions: explicit BLOCKED (after at least 1 warning) or 3+ warnings
        role_warnings = agent_states.get(role, {}).get("warning_count", 0)
        if effective_status == "BLOCKED" or role_warnings >= 3:
            delta["deal_status"] = "Blocked"

    # Observer: only history entry, no other state changes

    return delta


def _advance_turn_order(state: NegotiationState) -> dict[str, Any]:
    """Advance turn_order_index and set current_speaker.

    Returns a state delta with ``turn_order_index`` and ``current_speaker``.
    Does NOT touch ``turn_count`` — that is incremented at the start of a
    negotiator's node execution so the turn number is available before the
    agent speaks (and shared by the regulator/observer that follows).
    """
    turn_order = state.get("turn_order", [])
    if not turn_order:
        return {}

    current_idx = state.get("turn_order_index", 0)
    new_idx = (current_idx + 1) % len(turn_order)

    return {
        "turn_order_index": new_idx,
        "current_speaker": turn_order[new_idx],
    }
