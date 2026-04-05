"""Converters between LangGraph NegotiationState TypedDict and Pydantic model."""

from app.models.negotiation import NegotiationStateModel
from app.orchestrator.state import NegotiationState


def to_pydantic(state: NegotiationState) -> NegotiationStateModel:
    """Convert a LangGraph NegotiationState TypedDict to a Pydantic model.

    The Pydantic ``NegotiationStateModel`` does **not** have a
    ``scenario_config`` field, so it is intentionally dropped here.
    """
    return NegotiationStateModel(
        session_id=state["session_id"],
        scenario_id=state["scenario_id"],
        turn_count=state["turn_count"],
        max_turns=state["max_turns"],
        current_speaker=state["current_speaker"],
        deal_status=state["deal_status"],
        current_offer=state["current_offer"],
        history=state["history"],
        hidden_context=state["hidden_context"],
        warning_count=state["warning_count"],
        agreement_threshold=state["agreement_threshold"],
        turn_order=state["turn_order"],
        turn_order_index=state["turn_order_index"],
        agent_states=state["agent_states"],
        active_toggles=state["active_toggles"],
        total_tokens_used=state.get("total_tokens_used", 0),
        custom_prompts=state.get("custom_prompts", {}),
        model_overrides=state.get("model_overrides", {}),
        structured_memory_enabled=state.get("structured_memory_enabled", False),
        structured_memory_roles=state.get("structured_memory_roles", []),
        agent_memories=state.get("agent_memories", {}),
        milestone_summaries_enabled=state.get("milestone_summaries_enabled", False),
        milestone_summaries=state.get("milestone_summaries", {}),
        sliding_window_size=state.get("sliding_window_size", 3),
        milestone_interval=state.get("milestone_interval", 4),
        no_memory_roles=state.get("no_memory_roles", []),
        agent_calls=state.get("agent_calls", []),
    )


def from_pydantic(model: NegotiationStateModel) -> NegotiationState:
    """Convert a Pydantic NegotiationStateModel back to a LangGraph TypedDict.

    ``scenario_config`` and ``stall_diagnosis`` are set to defaults because
    the Pydantic model does not carry them.
    """
    return NegotiationState(
        session_id=model.session_id,
        scenario_id=model.scenario_id,
        turn_count=model.turn_count,
        max_turns=model.max_turns,
        current_speaker=model.current_speaker,
        deal_status=model.deal_status,
        current_offer=model.current_offer,
        history=model.history,
        hidden_context=model.hidden_context,
        warning_count=model.warning_count,
        agreement_threshold=model.agreement_threshold,
        scenario_config={},
        turn_order=model.turn_order,
        turn_order_index=model.turn_order_index,
        agent_states=model.agent_states,
        active_toggles=model.active_toggles,
        total_tokens_used=model.total_tokens_used,
        stall_diagnosis=None,
        custom_prompts=model.custom_prompts,
        model_overrides=model.model_overrides,
        structured_memory_enabled=model.structured_memory_enabled,
        structured_memory_roles=model.structured_memory_roles,
        agent_memories=model.agent_memories,
        milestone_summaries_enabled=model.milestone_summaries_enabled,
        milestone_summaries=model.milestone_summaries,
        sliding_window_size=model.sliding_window_size,
        milestone_interval=model.milestone_interval,
        no_memory_roles=model.no_memory_roles,
        agent_calls=model.agent_calls,
    )
