"""LangGraph-compatible NegotiationState TypedDict and initial state factory."""

from operator import add
from typing import Annotated, Any, TypedDict

from app.orchestrator.outputs import AgentMemory


class NegotiationState(TypedDict):
    """LangGraph runtime state for a negotiation session.

    The ``history`` field uses ``Annotated[list, add]`` so each node returns
    ``{"history": [new_entry]}`` and LangGraph appends automatically.
    All other fields are plain types replaced on each update.
    """

    session_id: str
    scenario_id: str
    turn_count: int
    max_turns: int
    current_speaker: str
    deal_status: str
    current_offer: float
    history: Annotated[list[dict[str, Any]], add]
    hidden_context: dict[str, Any]
    warning_count: int
    agreement_threshold: float
    scenario_config: dict[str, Any]
    turn_order: list[str]
    turn_order_index: int
    agent_states: dict[str, dict[str, Any]]
    active_toggles: list[str]
    total_tokens_used: int
    stall_diagnosis: dict[str, Any] | None
    custom_prompts: dict[str, str]
    model_overrides: dict[str, str]
    structured_memory_enabled: bool
    structured_memory_roles: list[str]
    agent_memories: dict[str, dict[str, Any]]
    milestone_summaries_enabled: bool
    milestone_summaries: dict[str, list[dict[str, Any]]]
    sliding_window_size: int
    milestone_interval: int
    no_memory_roles: list[str]
    closure_status: str
    confirmation_pending: list[str]


def create_initial_state(
    session_id: str,
    scenario_config: dict[str, Any],
    active_toggles: list[str] | None = None,
    hidden_context: dict[str, Any] | None = None,
    custom_prompts: dict[str, str] | None = None,
    model_overrides: dict[str, str] | None = None,
    structured_memory_enabled: bool = False,
    structured_memory_roles: list[str] | None = None,
    milestone_summaries_enabled: bool = False,
    no_memory_roles: list[str] | None = None,
) -> NegotiationState:
    """Build the initial NegotiationState from a scenario config dict.

    If ``negotiation_params.turn_order`` is present, use it directly.
    Otherwise derive it: interleave negotiators with regulators, then append
    observers.
    """
    agents = scenario_config["agents"]
    params = scenario_config["negotiation_params"]

    turn_order: list[str] | None = params.get("turn_order")
    if turn_order is None:
        negotiators = [a for a in agents if a.get("type", "negotiator") == "negotiator"]
        regulators = [a for a in agents if a.get("type") == "regulator"]
        turn_order = []
        for neg in negotiators:
            turn_order.append(neg["role"])
            for reg in regulators:
                turn_order.append(reg["role"])
        for a in agents:
            if a.get("type") == "observer":
                turn_order.append(a["role"])

    agent_states: dict[str, dict[str, Any]] = {}
    for a in agents:
        agent_type = a.get("type", "negotiator")
        agent_states[a["role"]] = {
            "role": a["role"],
            "name": a["name"],
            "agent_type": agent_type,
            "model_id": a["model_id"],
            "last_proposed_price": 0.0,
            "warning_count": 0,
        }

    # Resolve which roles have structured memory enabled.
    # Legacy callers may pass structured_memory_enabled=True (global flag)
    # which enables memory for ALL agents. New callers pass
    # structured_memory_roles with specific role names.
    # Milestone summaries require structured memory — force it on.
    if milestone_summaries_enabled:
        structured_memory_enabled = True

    effective_roles: list[str] = list(structured_memory_roles or [])
    if structured_memory_enabled and not effective_roles:
        effective_roles = [a["role"] for a in agents]

    agent_memories: dict[str, dict[str, Any]] = {}
    for a in agents:
        if a["role"] in effective_roles:
            agent_memories[a["role"]] = AgentMemory().model_dump()

    # Read sliding window and milestone interval from scenario params.
    sliding_window_size: int = params.get("sliding_window_size", 3)
    milestone_interval: int = params.get("milestone_interval", 4)

    # Initialize milestone summaries: one empty list per agent role when
    # enabled, empty dict when disabled.
    milestone_summaries: dict[str, list[dict[str, Any]]] = {}
    if milestone_summaries_enabled:
        milestone_summaries = {a["role"]: [] for a in agents}

    return NegotiationState(
        session_id=session_id,
        scenario_id=scenario_config["id"],
        turn_count=0,
        max_turns=params.get("max_turns", 15),
        current_speaker=turn_order[0],
        deal_status="Negotiating",
        current_offer=0.0,
        history=[],
        hidden_context=hidden_context or {},
        warning_count=0,
        agreement_threshold=params.get("agreement_threshold", 1000000.0),
        scenario_config=scenario_config,
        turn_order=turn_order,
        turn_order_index=0,
        agent_states=agent_states,
        active_toggles=active_toggles or [],
        total_tokens_used=0,
        stall_diagnosis=None,
        custom_prompts=custom_prompts or {},
        model_overrides=model_overrides or {},
        structured_memory_enabled=bool(effective_roles),
        structured_memory_roles=effective_roles,
        agent_memories=agent_memories,
        milestone_summaries_enabled=milestone_summaries_enabled,
        milestone_summaries=milestone_summaries,
        sliding_window_size=sliding_window_size,
        milestone_interval=milestone_interval,
        no_memory_roles=list(no_memory_roles or []),
        closure_status="",
        confirmation_pending=[],
    )
