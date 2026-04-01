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
from app.orchestrator.state import NegotiationState

logger = logging.getLogger(__name__)

DISPATCHER_NODE = "dispatcher"


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

    graph = StateGraph(NegotiationState)

    # Agent nodes
    for role in unique_roles:
        graph.add_node(role, create_agent_node(role))

    # Dispatcher node
    graph.add_node(DISPATCHER_NODE, _dispatcher)

    # Entry point
    graph.set_entry_point(DISPATCHER_NODE)

    # Each agent → dispatcher
    for role in unique_roles:
        graph.add_edge(role, DISPATCHER_NODE)

    # Conditional edges from dispatcher
    route_map: dict[str, str] = {role: role for role in unique_roles}
    route_map["__end__"] = END
    graph.add_conditional_edges(DISPATCHER_NODE, _route_dispatcher, route_map)

    return graph.compile()


# ---------------------------------------------------------------------------
# Dispatcher node + routing
# ---------------------------------------------------------------------------


def _dispatcher(state: NegotiationState) -> dict[str, Any]:
    """Central routing node — modifies state on terminal conditions.

    * If ``deal_status`` is already terminal → return ``{}`` (no changes).
    * If ``turn_count >= max_turns`` → set ``deal_status`` to ``"Failed"``.
    * If all negotiators have converged → set ``deal_status`` to ``"Agreed"``.
    * Otherwise → return ``{}`` (routing handled by ``_route_dispatcher``).
    """
    if state["deal_status"] != "Negotiating":
        return {}

    if state["turn_count"] >= state["max_turns"]:
        return {"deal_status": "Failed"}

    if _check_agreement(state):
        return {"deal_status": "Agreed"}

    return {}


def _route_dispatcher(state: NegotiationState) -> str:
    """Return the next node name or ``"__end__"`` (mapped to ``END``).

    Separate from ``_dispatcher`` so that LangGraph can use this as a
    pure routing function on the conditional edge.
    """
    if state["deal_status"] != "Negotiating":
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
    * Check: ``max(prices) - min(prices) <= agreement_threshold``.
    """
    agent_states = state.get("agent_states", {})
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
