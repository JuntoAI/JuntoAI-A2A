"""Unit tests for graph.py — agreement detection, dispatcher, and build_graph.

Covers subtasks 7.5–7.7:
- 7.5: _check_agreement with converged, diverged, single negotiator, zero prices
- 7.6: _dispatcher routing: terminal → END, max_turns → Failed, normal → current_speaker
- 7.7: build_graph node count and no hardcoded role names
"""

from __future__ import annotations

from typing import Any

import pytest

from app.orchestrator.graph import (
    DISPATCHER_NODE,
    _check_agreement,
    _dispatcher,
    _route_dispatcher,
    build_graph,
)
from app.orchestrator.state import NegotiationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    agent_states: dict[str, dict[str, Any]] | None = None,
    agreement_threshold: float = 5000.0,
    deal_status: str = "Negotiating",
    turn_count: int = 0,
    max_turns: int = 10,
    current_speaker: str = "Buyer",
    turn_order: list[str] | None = None,
) -> NegotiationState:
    if turn_order is None:
        turn_order = ["Buyer", "Seller"]
    return NegotiationState(
        session_id="s",
        scenario_id="s",
        turn_count=turn_count,
        max_turns=max_turns,
        current_speaker=current_speaker,
        deal_status=deal_status,
        current_offer=0.0,
        history=[],
        hidden_context={},
        warning_count=0,
        agreement_threshold=agreement_threshold,
        scenario_config={},
        turn_order=turn_order,
        turn_order_index=0,
        agent_states=agent_states or {},
        active_toggles=[],
        total_tokens_used=0,
        stall_diagnosis=None,
    )


def _negotiator_state(role: str, price: float) -> dict[str, Any]:
    return {
        "role": role,
        "name": role,
        "agent_type": "negotiator",
        "model_id": "gemini-2.5-flash",
        "last_proposed_price": price,
        "warning_count": 0,
    }


def _regulator_state(role: str) -> dict[str, Any]:
    return {
        "role": role,
        "name": role,
        "agent_type": "regulator",
        "model_id": "claude-sonnet-4-6",
        "last_proposed_price": 0.0,
        "warning_count": 0,
    }


def _make_scenario(agents: list[dict], turn_order: list[str] | None = None) -> dict:
    params: dict[str, Any] = {"max_turns": 10, "agreement_threshold": 5000.0}
    if turn_order is not None:
        params["turn_order"] = turn_order
    return {"id": "test", "agents": agents, "negotiation_params": params}


def _agent_def(role: str, agent_type: str = "negotiator", model_id: str = "gemini-2.5-flash") -> dict:
    return {"role": role, "name": role, "type": agent_type, "model_id": model_id, "persona_prompt": "You are an agent."}


# ===========================================================================
# 7.5: _check_agreement tests
# ===========================================================================


class TestCheckAgreement:
    """Unit tests for _check_agreement()."""

    def test_two_negotiators_converged(self):
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 100000.0),
            "Seller": _negotiator_state("Seller", 103000.0),
        }
        state = _make_state(agent_states=agent_states, agreement_threshold=5000.0)
        assert _check_agreement(state) is True

    def test_two_negotiators_diverged(self):
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 100000.0),
            "Seller": _negotiator_state("Seller", 200000.0),
        }
        state = _make_state(agent_states=agent_states, agreement_threshold=5000.0)
        assert _check_agreement(state) is False

    def test_single_negotiator_returns_false(self):
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 100000.0),
        }
        state = _make_state(agent_states=agent_states)
        assert _check_agreement(state) is False

    def test_zero_price_returns_false(self):
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 100000.0),
            "Seller": _negotiator_state("Seller", 0.0),
        }
        state = _make_state(agent_states=agent_states)
        assert _check_agreement(state) is False

    def test_both_zero_returns_false(self):
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 0.0),
            "Seller": _negotiator_state("Seller", 0.0),
        }
        state = _make_state(agent_states=agent_states)
        assert _check_agreement(state) is False

    def test_exact_threshold_boundary(self):
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 100000.0),
            "Seller": _negotiator_state("Seller", 105000.0),
        }
        state = _make_state(agent_states=agent_states, agreement_threshold=5000.0)
        assert _check_agreement(state) is True

    def test_mixed_types_only_checks_negotiators(self):
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 100000.0),
            "Seller": _negotiator_state("Seller", 102000.0),
            "Regulator": _regulator_state("Regulator"),
        }
        state = _make_state(agent_states=agent_states, agreement_threshold=5000.0)
        assert _check_agreement(state) is True

    def test_three_negotiators_converged(self):
        agent_states = {
            "A": _negotiator_state("A", 100000.0),
            "B": _negotiator_state("B", 101000.0),
            "C": _negotiator_state("C", 102000.0),
        }
        state = _make_state(agent_states=agent_states, agreement_threshold=5000.0)
        assert _check_agreement(state) is True

    def test_three_negotiators_one_diverged(self):
        agent_states = {
            "A": _negotiator_state("A", 100000.0),
            "B": _negotiator_state("B", 101000.0),
            "C": _negotiator_state("C", 200000.0),
        }
        state = _make_state(agent_states=agent_states, agreement_threshold=5000.0)
        assert _check_agreement(state) is False


# ===========================================================================
# 7.6: _dispatcher tests
# ===========================================================================


class TestDispatcher:
    """Unit tests for _dispatcher() and _route_dispatcher()."""

    def test_terminal_agreed_returns_empty(self):
        state = _make_state(deal_status="Agreed")
        assert _dispatcher(state) == {}

    def test_terminal_blocked_returns_empty(self):
        state = _make_state(deal_status="Blocked")
        assert _dispatcher(state) == {}

    def test_terminal_failed_returns_empty(self):
        state = _make_state(deal_status="Failed")
        assert _dispatcher(state) == {}

    def test_max_turns_sets_failed(self):
        state = _make_state(turn_count=10, max_turns=10)
        delta = _dispatcher(state)
        assert delta == {"deal_status": "Failed"}

    def test_max_turns_exceeded_sets_failed(self):
        state = _make_state(turn_count=12, max_turns=10)
        delta = _dispatcher(state)
        assert delta == {"deal_status": "Failed"}

    def test_agreement_sets_agreed(self):
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 100000.0),
            "Seller": _negotiator_state("Seller", 102000.0),
        }
        state = _make_state(agent_states=agent_states, agreement_threshold=5000.0)
        delta = _dispatcher(state)
        assert delta == {"deal_status": "Agreed"}

    def test_normal_returns_empty(self):
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 100000.0),
            "Seller": _negotiator_state("Seller", 200000.0),
        }
        state = _make_state(agent_states=agent_states, agreement_threshold=5000.0)
        delta = _dispatcher(state)
        assert delta == {}

    def test_route_terminal_returns_end(self):
        for status in ("Agreed", "Blocked", "Failed"):
            state = _make_state(deal_status=status)
            assert _route_dispatcher(state) == "__end__"

    def test_route_negotiating_returns_current_speaker(self):
        state = _make_state(current_speaker="Seller")
        assert _route_dispatcher(state) == "Seller"


# ===========================================================================
# 7.7: build_graph tests
# ===========================================================================


class TestBuildGraph:
    """Unit tests for build_graph()."""

    def test_node_count_two_agents(self):
        scenario = _make_scenario(
            agents=[_agent_def("Buyer"), _agent_def("Seller")],
            turn_order=["Buyer", "Seller"],
        )
        compiled = build_graph(scenario)
        graph = compiled.get_graph()
        # Unique roles (2) + dispatcher (1) = 3, plus __start__ and __end__
        # LangGraph adds __start__ and __end__ nodes automatically
        node_names = set(graph.nodes.keys())
        assert "Buyer" in node_names
        assert "Seller" in node_names
        assert DISPATCHER_NODE in node_names

    def test_node_count_three_agents(self):
        scenario = _make_scenario(
            agents=[
                _agent_def("Buyer"),
                _agent_def("Seller"),
                _agent_def("Regulator", "regulator", "claude-sonnet-4-6"),
            ],
            turn_order=["Buyer", "Regulator", "Seller", "Regulator"],
        )
        compiled = build_graph(scenario)
        graph = compiled.get_graph()
        node_names = set(graph.nodes.keys())
        assert "Buyer" in node_names
        assert "Seller" in node_names
        assert "Regulator" in node_names
        assert DISPATCHER_NODE in node_names
        # 3 unique roles + dispatcher = 4 (excluding __start__/__end__)
        real_nodes = {n for n in node_names if not n.startswith("__")}
        assert len(real_nodes) == 4

    def test_no_hardcoded_role_names(self):
        """Graph works with completely custom role names."""
        scenario = _make_scenario(
            agents=[_agent_def("AlphaBot"), _agent_def("BetaBot")],
            turn_order=["AlphaBot", "BetaBot"],
        )
        compiled = build_graph(scenario)
        graph = compiled.get_graph()
        node_names = set(graph.nodes.keys())
        assert "AlphaBot" in node_names
        assert "BetaBot" in node_names
        # Standard names should NOT be present
        assert "Buyer" not in node_names
        assert "Seller" not in node_names

    def test_single_agent(self):
        scenario = _make_scenario(
            agents=[_agent_def("Solo")],
            turn_order=["Solo"],
        )
        compiled = build_graph(scenario)
        graph = compiled.get_graph()
        real_nodes = {n for n in graph.nodes.keys() if not n.startswith("__")}
        assert real_nodes == {"Solo", DISPATCHER_NODE}

    def test_duplicate_roles_deduplicated(self):
        """Two agents with the same role should produce only one node."""
        scenario = _make_scenario(
            agents=[_agent_def("Agent"), _agent_def("Agent")],
            turn_order=["Agent"],
        )
        compiled = build_graph(scenario)
        graph = compiled.get_graph()
        real_nodes = {n for n in graph.nodes.keys() if not n.startswith("__")}
        assert len(real_nodes) == 2  # Agent + dispatcher
