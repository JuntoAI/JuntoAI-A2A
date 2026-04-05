"""Dynamic graph construction, dispatcher routing, and agreement detection.

Builds a LangGraph ``StateGraph`` from scenario config with one node per
unique agent role plus a central ``dispatcher`` node.  The dispatcher
checks terminal conditions (deal_status, max_turns, agreement) and routes
to the appropriate agent node or ``END``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.orchestrator.agent_node import create_agent_node
from app.orchestrator.confirmation_node import confirmation_node
from app.orchestrator.milestone_generator import generate_milestones
from app.orchestrator.stall_detector import detect_stall
from app.orchestrator.state import NegotiationState

logger = logging.getLogger(__name__)

DISPATCHER_NODE = "dispatcher"
CONFIRMATION_NODE = "confirmation"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_graph(scenario_config: dict[str, Any]) -> CompiledStateGraph:
    """Construct and compile a ``StateGraph`` from *scenario_config*.

    1. Read the ``agents`` array and create one node per unique role.
    2. Add a ``dispatcher`` node for central routing.
    3. Set the entry point to ``dispatcher``.
    4. Wire every agent node back to ``dispatcher``.
    5. Add conditional edges from ``dispatcher`` to agent nodes + END.
    """
    agents = scenario_config["agents"]
    unique_roles: list[str] = list({a["role"] for a in agents})

    # Guard against agent roles colliding with reserved internal node names
    _RESERVED = {DISPATCHER_NODE, CONFIRMATION_NODE}
    for role in unique_roles:
        if role in _RESERVED:
            raise ValueError(
                f"Agent role {role!r} collides with reserved node name. "
                f"Reserved names: {_RESERVED}"
            )

    graph = StateGraph(NegotiationState)

    # Agent nodes
    for role in unique_roles:
        graph.add_node(role, create_agent_node(role))

    # Dispatcher node
    graph.add_node(DISPATCHER_NODE, _dispatcher)

    # Confirmation node
    graph.add_node(CONFIRMATION_NODE, confirmation_node)

    # Entry point
    graph.set_entry_point(DISPATCHER_NODE)

    # Each agent → dispatcher
    for role in unique_roles:
        graph.add_edge(role, DISPATCHER_NODE)

    # Confirmation → dispatcher
    graph.add_edge(CONFIRMATION_NODE, DISPATCHER_NODE)

    # Conditional edges from dispatcher
    route_map: dict[str, str] = {role: role for role in unique_roles}
    route_map["__end__"] = END
    route_map[CONFIRMATION_NODE] = CONFIRMATION_NODE
    graph.add_conditional_edges(DISPATCHER_NODE, _route_dispatcher, route_map)

    return graph.compile()


# ---------------------------------------------------------------------------
# Dispatcher node + routing
# ---------------------------------------------------------------------------


async def _dispatcher(state: NegotiationState) -> dict[str, Any]:
    """Central routing node — modifies state on terminal conditions.

    * If ``deal_status`` is already terminal → return ``{}`` (no changes).
    * If ``turn_count >= max_turns`` → set ``deal_status`` to ``"Failed"``.
    * If all negotiators have converged → set ``deal_status`` to ``"Agreed"``.
    * If stall detected → set ``deal_status`` to ``"Failed"`` with stall info.
    * If milestone generation is due → generate and merge summaries.
    * Otherwise → return ``{}`` (routing handled by ``_route_dispatcher``).
    """
    # Handle confirmation resolution when all confirmations are in
    if state["deal_status"] == "Confirming":
        if not state.get("confirmation_pending", []):
            return _resolve_confirmation(state)
        return {}

    if state["deal_status"] != "Negotiating":
        return {}

    if state["turn_count"] >= state["max_turns"]:
        return {
            "deal_status": "Failed",
            "current_offer": state["current_offer"],
            "turn_count": state["turn_count"],
            "warning_count": state["warning_count"],
            "total_tokens_used": state.get("total_tokens_used", 0),
            "agent_states": state["agent_states"],
            "max_turns": state["max_turns"],
        }

    if _check_agreement(state):
        # Populate confirmation_pending with negotiator roles in turn_order
        # sequence (Req 1.3), skipping regulators and observers.
        turn_order = state.get("turn_order", [])
        negotiator_set = {
            role for role, info in state["agent_states"].items()
            if info.get("agent_type") == "negotiator"
        }
        negotiator_roles = [r for r in turn_order if r in negotiator_set]
        # Fallback: if turn_order doesn't cover all negotiators (shouldn't
        # happen), append any missing ones at the end.
        for role in state["agent_states"]:
            if role in negotiator_set and role not in negotiator_roles:
                negotiator_roles.append(role)
        return {
            "deal_status": "Confirming",
            "confirmation_pending": negotiator_roles,
            "closure_status": "",
            "current_offer": state["current_offer"],
            "turn_count": state["turn_count"],
            "warning_count": state["warning_count"],
            "total_tokens_used": state.get("total_tokens_used", 0),
            "agent_states": state["agent_states"],
        }

    # Stall detection — catch loops before max_turns
    diagnosis = detect_stall(state)
    if diagnosis.is_stalled:
        logger.warning(
            "Stall detected in session %s: %s (confidence=%.2f)",
            state.get("session_id", "?"),
            diagnosis.stall_type,
            diagnosis.confidence,
        )
        return {
            "deal_status": "Failed",
            "stall_diagnosis": diagnosis.to_dict(),
            "current_offer": state["current_offer"],
            "turn_count": state["turn_count"],
            "warning_count": state["warning_count"],
            "total_tokens_used": state.get("total_tokens_used", 0),
            "agent_states": state["agent_states"],
            "max_turns": state["max_turns"],
        }

    # Milestone generation — triggered after turn advancement when
    # turn_count is a non-zero multiple of milestone_interval.
    delta: dict[str, Any] = {}
    if _should_generate_milestones(state):
        try:
            milestone_delta = await generate_milestones(state)
            delta.update(milestone_delta)
        except Exception:
            logger.exception(
                "Milestone generation failed for session %s. "
                "Continuing without milestones.",
                state.get("session_id", "?"),
            )

    return delta


def _resolve_confirmation(state: NegotiationState) -> dict[str, Any]:
    """Resolve confirmation round results after all negotiators have responded.

    Only considers confirmation entries from the CURRENT round (matching
    the current turn_count) to avoid stale entries from previous rejected
    confirmation rounds contaminating the result.
    """
    current_turn = state.get("turn_count", 0)
    confirmations = [
        e for e in state["history"]
        if e.get("agent_type") == "confirmation"
        and e.get("turn_number") == current_turn
    ]

    if not confirmations:
        # No confirmation entries for this round — shouldn't happen, but
        # treat as rejection to avoid silent agreement.
        return {
            "deal_status": "Negotiating",
            "closure_status": "Rejected",
            "confirmation_pending": [],
        }

    all_accepted = all(e["content"]["accept"] for e in confirmations)
    any_conditions = any(e["content"].get("conditions", []) for e in confirmations)

    if all_accepted and not any_conditions:
        return {
            "deal_status": "Agreed",
            "closure_status": "Confirmed",
            "confirmation_pending": [],
        }
    elif not all_accepted:
        return {
            "deal_status": "Negotiating",
            "closure_status": "Rejected",
            "confirmation_pending": [],
        }
    else:
        return {
            "deal_status": "Negotiating",
            "closure_status": "Conditional",
            "confirmation_pending": [],
        }


def _should_generate_milestones(state: NegotiationState) -> bool:
    """Return True if milestone generation should be triggered this turn."""
    if not state.get("milestone_summaries_enabled", False):
        return False
    turn_count = state.get("turn_count", 0)
    if turn_count == 0:
        return False
    milestone_interval = state.get("milestone_interval", 4)
    return turn_count % milestone_interval == 0


def _route_dispatcher(state: NegotiationState) -> str:
    """Return the next node name or ``"__end__"`` (mapped to ``END``).

    Separate from ``_dispatcher`` so that LangGraph can use this as a
    pure routing function on the conditional edge.

    Note: when ``deal_status == "Confirming"`` and ``confirmation_pending``
    is empty, the dispatcher has already called ``_resolve_confirmation()``
    which changes ``deal_status`` to ``"Agreed"`` or ``"Negotiating"``.
    So by the time this function runs, the Confirming+empty case is resolved.
    The guard below handles the edge case defensively.
    """
    if state["deal_status"] == "Confirming":
        if state.get("confirmation_pending", []):
            return CONFIRMATION_NODE
        # Dispatcher already resolved — but guard defensively
        return "__end__"
    if state["deal_status"] not in ("Negotiating",):
        return "__end__"
    return state["current_speaker"]


# ---------------------------------------------------------------------------
# Agreement detection
# ---------------------------------------------------------------------------


def _check_agreement(state: NegotiationState) -> bool:
    """Return ``True`` if all negotiators have converged within threshold.

    * Collect ``last_proposed_price`` from ``agent_states`` where
      ``agent_type == "negotiator"``.
    * If only 1 negotiator → return ``False`` (skip convergence).
    * If any price is ``0.0`` (hasn't proposed yet) → return ``False``.
    * Normalize prices when agents use different units (e.g. hourly vs total)
      using the scenario's ``normalization_factor``.
    * Check: ``max(normalized) - min(normalized) <= agreement_threshold``.
    """
    agent_states = state.get("agent_states", {})
    scenario_config = state.get("scenario_config", {})
    params = scenario_config.get("negotiation_params", {})
    normalization_factor = params.get("normalization_factor", 1.0)

    prices: list[float] = []

    for _role, info in agent_states.items():
        if info.get("agent_type") == "negotiator":
            prices.append(info.get("last_proposed_price", 0.0))

    # Single negotiator — skip convergence
    if len(prices) <= 1:
        return False

    # Any negotiator hasn't proposed yet
    if any(p == 0.0 for p in prices):
        return False

    # Normalize: if agents operate at different scales, the smaller-value
    # agent's price gets multiplied by normalization_factor.  We detect
    # "small" vs "large" by checking if any price is < 1% of the max price.
    if normalization_factor != 1.0 and len(prices) >= 2:
        max_price = max(prices)
        normalized = []
        for p in prices:
            if max_price > 0 and p < max_price * 0.01:
                # This agent is quoting in a smaller unit (e.g. hourly)
                normalized.append(p * normalization_factor)
            else:
                normalized.append(p)
        prices = normalized

    threshold = state.get("agreement_threshold", 1_000_000.0)
    return (max(prices) - min(prices)) <= threshold


# ---------------------------------------------------------------------------
# Execution entry point
# ---------------------------------------------------------------------------


async def run_negotiation(
    initial_state: NegotiationState,
    scenario_config: dict[str, Any],
) -> AsyncGenerator[NegotiationState, None]:
    """Execute the compiled graph, yielding state snapshots after each node."""
    graph = build_graph(scenario_config)
    async for state_snapshot in graph.astream(initial_state):
        yield state_snapshot
