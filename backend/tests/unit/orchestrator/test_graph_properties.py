"""Property-based tests for graph.py.

P8:  Agreement Detection
P9:  Dispatcher Terminal Routing
P10: deal_status Invariant
P11: Dynamic Graph Node Count
P12: Dispatcher Routes to current_speaker
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

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
# Shared strategies
# ---------------------------------------------------------------------------

st_role = st.text(min_size=1, max_size=15, alphabet=st.characters(categories=("L", "N"))).filter(
    lambda s: s.lower() != "dispatcher"  # avoid collision with internal DISPATCHER_NODE
)
st_price = st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False)
st_threshold = st.floats(min_value=0.01, max_value=1e8, allow_nan=False, allow_infinity=False)
st_terminal_status = st.sampled_from(["Agreed", "Blocked", "Failed"])
st_model_id = st.sampled_from(["gemini-3-flash-preview", "gemini-2.5-pro", "claude-3-5-sonnet-v2", "claude-sonnet-4-6"])


def _negotiator_agent_state(role: str, price: float) -> dict[str, Any]:
    return {
        "role": role,
        "name": role,
        "agent_type": "negotiator",
        "model_id": "gemini-3-flash-preview",
        "last_proposed_price": price,
        "warning_count": 0,
    }


def _make_state(**overrides) -> NegotiationState:
    defaults: dict[str, Any] = {
        "session_id": "s",
        "scenario_id": "s",
        "turn_count": 0,
        "max_turns": 10,
        "current_speaker": "A",
        "deal_status": "Negotiating",
        "current_offer": 0.0,
        "history": [],
        "hidden_context": {},
        "warning_count": 0,
        "agreement_threshold": 5000.0,
        "scenario_config": {},
        "turn_order": ["A"],
        "turn_order_index": 0,
        "agent_states": {},
        "active_toggles": [],
        "total_tokens_used": 0,
        "stall_diagnosis": None,
        "custom_prompts": {},
        "model_overrides": {},
        "structured_memory_enabled": False,
        "structured_memory_roles": [],
        "agent_memories": {},
        "milestone_summaries_enabled": False,
        "milestone_summaries": {},
        "sliding_window_size": 3,
        "milestone_interval": 4,
        "no_memory_roles": [],
        "closure_status": "",
        "confirmation_pending": [],
    }
    defaults.update(overrides)
    return NegotiationState(**defaults)


# ===========================================================================
# P8: Agreement Detection
# **Validates: Requirements 8.1, 8.2**
# ===========================================================================


@st.composite
def st_converged_prices(draw: st.DrawFn) -> tuple[list[float], float]:
    """Generate N prices (N>=2) that are within threshold of each other."""
    n = draw(st.integers(min_value=2, max_value=6))
    # Use moderate ranges to avoid float precision issues at large magnitudes
    base = draw(st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False))
    threshold = draw(st.floats(min_value=100.0, max_value=1e5, allow_nan=False, allow_infinity=False))
    # Generate prices within [base, base + threshold * 0.9] to stay safely within threshold
    upper = base + threshold * 0.9
    prices = [
        draw(st.floats(min_value=base, max_value=upper, allow_nan=False, allow_infinity=False))
        for _ in range(n)
    ]
    return prices, threshold


@st.composite
def st_diverged_prices(draw: st.DrawFn) -> tuple[list[float], float]:
    """Generate N prices (N>=2) where max-min > threshold."""
    n = draw(st.integers(min_value=2, max_value=6))
    threshold = draw(st.floats(min_value=1.0, max_value=1e5, allow_nan=False, allow_infinity=False))
    low = draw(st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False))
    # Ensure at least one price is far enough away
    high = low + threshold + draw(st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False))
    prices = [low, high]
    for _ in range(n - 2):
        prices.append(draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False)))
    return prices, threshold


class TestP8AgreementDetection:
    """Convergence within threshold → True, divergence → False,
    single negotiator → False."""

    @settings(max_examples=200)
    @given(data=st_converged_prices())
    def test_converged_returns_true(self, data: tuple):
        """**Validates: Requirements 8.1**"""
        prices, threshold = data
        roles = [f"N{i}" for i in range(len(prices))]
        agent_states = {r: _negotiator_agent_state(r, p) for r, p in zip(roles, prices)}
        state = _make_state(
            agent_states=agent_states,
            agreement_threshold=threshold,
            turn_order=roles,
            current_speaker=roles[0],
        )
        assert _check_agreement(state) is True

    @settings(max_examples=200)
    @given(data=st_diverged_prices())
    def test_diverged_returns_false(self, data: tuple):
        """**Validates: Requirements 8.1**"""
        prices, threshold = data
        roles = [f"N{i}" for i in range(len(prices))]
        agent_states = {r: _negotiator_agent_state(r, p) for r, p in zip(roles, prices)}
        state = _make_state(
            agent_states=agent_states,
            agreement_threshold=threshold,
            turn_order=roles,
            current_speaker=roles[0],
        )
        assert _check_agreement(state) is False

    @settings(max_examples=200)
    @given(price=st_price, threshold=st_threshold)
    def test_single_negotiator_returns_false(self, price: float, threshold: float):
        """**Validates: Requirements 8.2**"""
        agent_states = {"Solo": _negotiator_agent_state("Solo", price)}
        state = _make_state(
            agent_states=agent_states,
            agreement_threshold=threshold,
            turn_order=["Solo"],
            current_speaker="Solo",
        )
        assert _check_agreement(state) is False

    @settings(max_examples=100)
    @given(
        price_a=st_price,
        threshold=st_threshold,
    )
    def test_zero_price_returns_false(self, price_a: float, threshold: float):
        """**Validates: Requirements 8.1**"""
        agent_states = {
            "A": _negotiator_agent_state("A", price_a),
            "B": _negotiator_agent_state("B", 0.0),
        }
        state = _make_state(
            agent_states=agent_states,
            agreement_threshold=threshold,
            turn_order=["A", "B"],
            current_speaker="A",
        )
        assert _check_agreement(state) is False


# ===========================================================================
# P9: Dispatcher Terminal Routing
# **Validates: Requirements 5.3, 5.4**
# ===========================================================================


class TestP9DispatcherTerminalRouting:
    """Terminal deal_status routes to END, Negotiating routes to current_speaker."""

    @settings(max_examples=200)
    @given(status=st_terminal_status)
    def test_terminal_routes_to_end(self, status: str):
        """**Validates: Requirements 5.3**"""
        state = _make_state(deal_status=status)
        assert _route_dispatcher(state) == "__end__"

    @settings(max_examples=200)
    @given(speaker=st_role)
    def test_negotiating_routes_to_speaker(self, speaker: str):
        """**Validates: Requirements 5.2**"""
        state = _make_state(deal_status="Negotiating", current_speaker=speaker)
        assert _route_dispatcher(state) == speaker

    @settings(max_examples=200)
    @given(status=st_terminal_status)
    @pytest.mark.asyncio
    async def test_dispatcher_node_returns_empty_on_terminal(self, status: str):
        """**Validates: Requirements 5.3**"""
        state = _make_state(deal_status=status)
        assert await _dispatcher(state) == {}


# ===========================================================================
# P10: deal_status Invariant
# **Validates: Requirements 8.6**
# ===========================================================================


VALID_STATUSES = {"Negotiating", "Agreed", "Blocked", "Failed", "Confirming"}


class TestP10DealStatusInvariant:
    """deal_status is always in valid set; once terminal, never changes."""

    @settings(max_examples=200)
    @given(
        turn_count=st.integers(min_value=0, max_value=50),
        max_turns=st.integers(min_value=1, max_value=50),
    )
    @pytest.mark.asyncio
    async def test_dispatcher_produces_valid_status(self, turn_count: int, max_turns: int):
        """**Validates: Requirements 8.6**"""
        agent_states = {
            "A": _negotiator_agent_state("A", 100.0),
            "B": _negotiator_agent_state("B", 200.0),
        }
        state = _make_state(
            turn_count=turn_count,
            max_turns=max_turns,
            agent_states=agent_states,
            agreement_threshold=5000.0,
            turn_order=["A", "B"],
            current_speaker="A",
        )
        delta = await _dispatcher(state)
        if "deal_status" in delta:
            assert delta["deal_status"] in VALID_STATUSES

    @settings(max_examples=200)
    @given(status=st_terminal_status)
    @pytest.mark.asyncio
    async def test_terminal_status_unchanged_by_dispatcher(self, status: str):
        """**Validates: Requirements 8.6**

        Once deal_status leaves Negotiating, dispatcher returns empty dict
        (no status change).
        """
        state = _make_state(deal_status=status)
        delta = await _dispatcher(state)
        assert "deal_status" not in delta

    @settings(max_examples=200)
    @given(
        turn_count=st.integers(min_value=0, max_value=100),
        max_turns=st.integers(min_value=1, max_value=100),
    )
    @pytest.mark.asyncio
    async def test_dispatcher_only_transitions_from_negotiating(self, turn_count: int, max_turns: int):
        """**Validates: Requirements 8.6**"""
        state = _make_state(
            deal_status="Negotiating",
            turn_count=turn_count,
            max_turns=max_turns,
        )
        delta = await _dispatcher(state)
        if "deal_status" in delta:
            assert delta["deal_status"] in {"Failed", "Agreed"}


# ===========================================================================
# P11: Dynamic Graph Node Count
# **Validates: Requirements 4.2, 4.5**
# ===========================================================================


@st.composite
def st_scenario_config(draw: st.DrawFn) -> tuple[dict[str, Any], int]:
    """Generate a scenario config with N unique roles and return expected node count."""
    n = draw(st.integers(min_value=1, max_value=6))
    roles = draw(st.lists(st_role, min_size=n, max_size=n, unique=True))
    agents = []
    for role in roles:
        agents.append({
            "role": role,
            "name": role,
            "type": "negotiator",
            "model_id": draw(st_model_id),
            "persona_prompt": "You are an agent.",
        })
    config = {
        "id": "gen",
        "agents": agents,
        "negotiation_params": {
            "max_turns": 10,
            "agreement_threshold": 5000.0,
            "turn_order": roles,
        },
    }
    return config, n


class TestP11DynamicGraphNodeCount:
    """build_graph creates len(unique_roles) + 1 nodes (roles + dispatcher)."""

    @settings(max_examples=100)
    @given(data=st_scenario_config())
    def test_node_count_matches(self, data: tuple):
        """**Validates: Requirements 4.2**"""
        config, n_roles = data
        compiled = build_graph(config)
        graph = compiled.get_graph()
        real_nodes = {n for n in graph.nodes.keys() if not n.startswith("__")}
        assert len(real_nodes) == n_roles + 2  # roles + dispatcher + confirmation

    @settings(max_examples=100)
    @given(data=st_scenario_config())
    def test_dispatcher_always_present(self, data: tuple):
        """**Validates: Requirements 4.4**"""
        config, _ = data
        compiled = build_graph(config)
        graph = compiled.get_graph()
        assert DISPATCHER_NODE in graph.nodes

    @settings(max_examples=100)
    @given(data=st_scenario_config())
    def test_all_roles_present_as_nodes(self, data: tuple):
        """**Validates: Requirements 4.5**"""
        config, _ = data
        compiled = build_graph(config)
        graph = compiled.get_graph()
        node_names = set(graph.nodes.keys())
        for agent in config["agents"]:
            assert agent["role"] in node_names


# ===========================================================================
# P12: Dispatcher Routes to current_speaker
# **Validates: Requirements 5.2, 5.5**
# ===========================================================================


class TestP12DispatcherRoutesToCurrentSpeaker:
    """Dispatcher conditional edge maps to current_speaker node name."""

    @settings(max_examples=200)
    @given(speaker=st_role)
    def test_routes_to_current_speaker(self, speaker: str):
        """**Validates: Requirements 5.2**"""
        state = _make_state(
            deal_status="Negotiating",
            current_speaker=speaker,
            turn_order=[speaker],
        )
        result = _route_dispatcher(state)
        assert result == speaker

    @settings(max_examples=200)
    @given(status=st_terminal_status, speaker=st_role)
    def test_terminal_overrides_speaker(self, status: str, speaker: str):
        """**Validates: Requirements 5.3**"""
        state = _make_state(
            deal_status=status,
            current_speaker=speaker,
        )
        result = _route_dispatcher(state)
        assert result == "__end__"
