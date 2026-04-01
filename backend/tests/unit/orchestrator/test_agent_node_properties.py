"""Property-based tests for the agent node factory.

P3:  Turn Order Advancement
P4:  Negotiator State Update
P5:  Regulator State Update
P6:  Observer Read-Only
P7:  Hidden Context Injection
P15: Turn Number Consistency
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.agent_node import (
    _advance_turn_order,
    _build_prompt,
    _update_state,
)
from app.orchestrator.outputs import NegotiatorOutput, ObserverOutput, RegulatorOutput
from app.orchestrator.state import NegotiationState

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

st_role = st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L", "N")))
st_text = st.text(min_size=1, max_size=80, alphabet=st.characters(categories=("L", "N", "P")))
st_price = st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False)
st_agent_type = st.sampled_from(["negotiator", "regulator", "observer"])
st_model_id = st.sampled_from(["gemini-2.5-flash", "gemini-2.5-pro", "claude-3-5-sonnet-v2", "claude-sonnet-4"])
st_status = st.sampled_from(["CLEAR", "WARNING", "BLOCKED"])


@st.composite
def st_turn_order_state(draw: st.DrawFn) -> NegotiationState:
    """Generate a state with a valid turn_order and turn_order_index."""
    num_roles = draw(st.integers(min_value=1, max_value=8))
    roles = draw(st.lists(st_role, min_size=num_roles, max_size=num_roles, unique=True))
    # turn_order can repeat roles (e.g. regulator appears twice)
    turn_order = draw(st.lists(st.sampled_from(roles), min_size=1, max_size=max(len(roles) * 2, 2)))
    idx = draw(st.integers(min_value=0, max_value=len(turn_order) - 1))
    turn_count = draw(st.integers(min_value=0, max_value=500))

    agent_states: dict[str, dict[str, Any]] = {}
    for r in roles:
        agent_states[r] = {
            "role": r, "name": draw(st_text), "agent_type": draw(st_agent_type),
            "model_id": draw(st_model_id), "last_proposed_price": 0.0, "warning_count": 0,
        }

    return NegotiationState(
        session_id="s", scenario_id="s", turn_count=turn_count,
        max_turns=draw(st.integers(min_value=1, max_value=100)),
        current_speaker=turn_order[idx], deal_status="Negotiating",
        current_offer=draw(st_price), history=[],
        hidden_context={}, warning_count=0,
        agreement_threshold=5000.0, scenario_config={},
        turn_order=turn_order, turn_order_index=idx,
        agent_states=agent_states, active_toggles=[],
    )


@st.composite
def st_negotiator_state(draw: st.DrawFn) -> tuple[NegotiationState, str, NegotiatorOutput]:
    """Generate a state + role + NegotiatorOutput for negotiator update tests."""
    role = draw(st_role)
    other_role = draw(st_role.filter(lambda r: r != role))
    proposed = draw(st_price)

    agent_states = {
        role: {"role": role, "name": "A", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
        other_role: {"role": other_role, "name": "B", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
    }
    state = NegotiationState(
        session_id="s", scenario_id="s", turn_count=draw(st.integers(min_value=0, max_value=100)),
        max_turns=15, current_speaker=role, deal_status="Negotiating",
        current_offer=draw(st_price), history=[],
        hidden_context={}, warning_count=0,
        agreement_threshold=5000.0, scenario_config={},
        turn_order=[role, other_role], turn_order_index=0,
        agent_states=agent_states, active_toggles=[],
    )
    output = NegotiatorOutput(inner_thought="t", public_message="m", proposed_price=proposed)
    return state, role, output


@st.composite
def st_regulator_state(draw: st.DrawFn) -> tuple[NegotiationState, str, RegulatorOutput]:
    """Generate a state + role + RegulatorOutput for regulator update tests."""
    role = draw(st_role)
    prior_warnings = draw(st.integers(min_value=0, max_value=5))
    global_warnings = draw(st.integers(min_value=prior_warnings, max_value=prior_warnings + 10))
    status = draw(st_status)

    agent_states = {
        role: {"role": role, "name": "R", "agent_type": "regulator", "model_id": "claude-sonnet-4", "last_proposed_price": 0.0, "warning_count": prior_warnings},
    }
    state = NegotiationState(
        session_id="s", scenario_id="s", turn_count=0,
        max_turns=15, current_speaker=role, deal_status="Negotiating",
        current_offer=0.0, history=[],
        hidden_context={}, warning_count=global_warnings,
        agreement_threshold=5000.0, scenario_config={},
        turn_order=[role], turn_order_index=0,
        agent_states=agent_states, active_toggles=[],
    )
    output = RegulatorOutput(status=status, reasoning="reason")
    return state, role, output


@st.composite
def st_observer_state(draw: st.DrawFn) -> tuple[NegotiationState, str, ObserverOutput]:
    """Generate a state + role + ObserverOutput for observer update tests."""
    role = draw(st_role)
    agent_states = {
        role: {"role": role, "name": "O", "agent_type": "observer", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
    }
    state = NegotiationState(
        session_id="s", scenario_id="s", turn_count=0,
        max_turns=15, current_speaker=role, deal_status="Negotiating",
        current_offer=draw(st_price), history=[],
        hidden_context={}, warning_count=draw(st.integers(min_value=0, max_value=10)),
        agreement_threshold=5000.0, scenario_config={},
        turn_order=[role], turn_order_index=0,
        agent_states=agent_states, active_toggles=[],
    )
    output = ObserverOutput(observation="obs", recommendation="rec")
    return state, role, output


# ===========================================================================
# P3: Turn Order Advancement
# **Validates: Requirements 3.9, 3.10**
# ===========================================================================


class TestP3TurnOrderAdvancement:
    """After any agent node executes, turn_order_index increments by 1,
    wraps correctly, and current_speaker == turn_order[turn_order_index]."""

    @settings(max_examples=200)
    @given(state=st_turn_order_state())
    def test_index_increments_by_one_mod_length(self, state: NegotiationState):
        """**Validates: Requirements 3.9**"""
        old_idx = state["turn_order_index"]
        turn_order = state["turn_order"]
        delta = _advance_turn_order(state)

        expected_idx = (old_idx + 1) % len(turn_order)
        assert delta["turn_order_index"] == expected_idx

    @settings(max_examples=200)
    @given(state=st_turn_order_state())
    def test_current_speaker_matches_new_index(self, state: NegotiationState):
        """**Validates: Requirements 3.10**"""
        turn_order = state["turn_order"]
        delta = _advance_turn_order(state)
        new_idx = delta["turn_order_index"]
        assert delta["current_speaker"] == turn_order[new_idx]

    @settings(max_examples=200)
    @given(state=st_turn_order_state())
    def test_turn_count_increments_only_on_wrap(self, state: NegotiationState):
        """**Validates: Requirements 3.9**"""
        old_idx = state["turn_order_index"]
        old_count = state["turn_count"]
        turn_order = state["turn_order"]
        delta = _advance_turn_order(state)

        wraps = (old_idx + 1) % len(turn_order) == 0
        if wraps:
            assert delta.get("turn_count") == old_count + 1
        else:
            assert "turn_count" not in delta


# ===========================================================================
# P4: Negotiator State Update
# **Validates: Requirements 3.4**
# ===========================================================================


class TestP4NegotiatorStateUpdate:
    """After a negotiator node, current_offer == proposed_price AND
    agent_states[role]["last_proposed_price"] == proposed_price."""

    @settings(max_examples=200)
    @given(data=st_negotiator_state())
    def test_current_offer_equals_proposed_price(self, data: tuple):
        """**Validates: Requirements 3.4**"""
        state, role, output = data
        delta = _update_state(output, "negotiator", role, state)
        assert delta["current_offer"] == output.proposed_price

    @settings(max_examples=200)
    @given(data=st_negotiator_state())
    def test_agent_state_last_proposed_price(self, data: tuple):
        """**Validates: Requirements 3.4**"""
        state, role, output = data
        delta = _update_state(output, "negotiator", role, state)
        assert delta["agent_states"][role]["last_proposed_price"] == output.proposed_price

    @settings(max_examples=200)
    @given(data=st_negotiator_state())
    def test_history_has_one_entry(self, data: tuple):
        """**Validates: Requirements 3.4**"""
        state, role, output = data
        delta = _update_state(output, "negotiator", role, state)
        assert len(delta["history"]) == 1
        assert delta["history"][0]["role"] == role
        assert delta["history"][0]["agent_type"] == "negotiator"


# ===========================================================================
# P5: Regulator State Update
# **Validates: Requirements 3.5, 3.6**
# ===========================================================================


class TestP5RegulatorStateUpdate:
    """After regulator returns WARNING, warning_count increments;
    after 3 cumulative warnings, deal_status == "Blocked"."""

    @settings(max_examples=200)
    @given(data=st_regulator_state())
    def test_warning_increments_counts(self, data: tuple):
        """**Validates: Requirements 3.5**"""
        state, role, output = data
        old_global = state["warning_count"]
        old_role = state["agent_states"][role]["warning_count"]

        delta = _update_state(output, "regulator", role, state)

        if output.status == "WARNING":
            assert delta["warning_count"] == old_global + 1
            assert delta["agent_states"][role]["warning_count"] == old_role + 1
        else:
            assert delta["warning_count"] == old_global
            assert delta["agent_states"][role]["warning_count"] == old_role

    @settings(max_examples=200)
    @given(data=st_regulator_state())
    def test_three_warnings_blocks(self, data: tuple):
        """**Validates: Requirements 3.6**"""
        state, role, output = data
        old_role_warnings = state["agent_states"][role]["warning_count"]

        delta = _update_state(output, "regulator", role, state)

        new_role_warnings = delta["agent_states"][role]["warning_count"]
        if new_role_warnings >= 3 or output.status == "BLOCKED":
            assert delta.get("deal_status") == "Blocked"

    @settings(max_examples=200)
    @given(data=st_regulator_state())
    def test_blocked_status_always_blocks(self, data: tuple):
        """**Validates: Requirements 3.7**"""
        state, role, output = data
        if output.status == "BLOCKED":
            delta = _update_state(output, "regulator", role, state)
            assert delta.get("deal_status") == "Blocked"


# ===========================================================================
# P6: Observer Read-Only
# **Validates: Requirements 3.8**
# ===========================================================================


class TestP6ObserverReadOnly:
    """After observer executes, current_offer, deal_status, warning_count
    are unchanged."""

    @settings(max_examples=200)
    @given(data=st_observer_state())
    def test_no_state_mutations(self, data: tuple):
        """**Validates: Requirements 3.8**"""
        state, role, output = data
        delta = _update_state(output, "observer", role, state)

        # Observer delta must NOT contain these keys
        assert "current_offer" not in delta
        assert "deal_status" not in delta
        assert "warning_count" not in delta
        assert "agent_states" not in delta

    @settings(max_examples=200)
    @given(data=st_observer_state())
    def test_only_history_appended(self, data: tuple):
        """**Validates: Requirements 3.8**"""
        state, role, output = data
        delta = _update_state(output, "observer", role, state)

        assert "history" in delta
        assert len(delta["history"]) == 1
        assert delta["history"][0]["role"] == role
        assert delta["history"][0]["agent_type"] == "observer"


# ===========================================================================
# P7: Hidden Context Injection
# **Validates: Requirements 3.11**
# ===========================================================================


@st.composite
def st_prompt_with_hidden_context(draw: st.DrawFn) -> tuple[dict, NegotiationState, bool]:
    """Generate agent_config + state with or without hidden context for the role."""
    role = draw(st_role)
    has_context = draw(st.booleans())
    context_value = draw(st_text)

    agent_config: dict[str, Any] = {
        "role": role,
        "name": "Agent",
        "type": "negotiator",
        "model_id": "gemini-2.5-flash",
        "persona_prompt": "You are an agent.",
    }

    hidden_context: dict[str, Any] = {}
    if has_context:
        hidden_context[role] = context_value

    state = NegotiationState(
        session_id="s", scenario_id="s", turn_count=0, max_turns=10,
        current_speaker=role, deal_status="Negotiating", current_offer=0.0,
        history=[], hidden_context=hidden_context, warning_count=0,
        agreement_threshold=5000.0, scenario_config={},
        turn_order=[role], turn_order_index=0, agent_states={},
        active_toggles=[],
    )
    return agent_config, state, has_context


class TestP7HiddenContextInjection:
    """When hidden_context[role] exists, system prompt contains it;
    when absent, prompt does not contain hidden context."""

    @settings(max_examples=200)
    @given(data=st_prompt_with_hidden_context())
    def test_hidden_context_presence(self, data: tuple):
        """**Validates: Requirements 3.11**"""
        agent_config, state, has_context = data
        system, _ = _build_prompt(agent_config, state)

        if has_context:
            assert "Confidential information" in system
        else:
            assert "Confidential" not in system


# ===========================================================================
# P15: Turn Number Consistency
# **Validates: Requirements 3.9 (turn_count only increments on wrap)**
# ===========================================================================


@st.composite
def st_full_cycle_state(draw: st.DrawFn) -> NegotiationState:
    """Generate a state at the START of a cycle (turn_order_index=0)."""
    num_roles = draw(st.integers(min_value=2, max_value=6))
    roles = draw(st.lists(st_role, min_size=num_roles, max_size=num_roles, unique=True))
    turn_count = draw(st.integers(min_value=0, max_value=100))

    agent_states: dict[str, dict[str, Any]] = {}
    for r in roles:
        agent_states[r] = {
            "role": r, "name": "N", "agent_type": "negotiator",
            "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0,
        }

    return NegotiationState(
        session_id="s", scenario_id="s", turn_count=turn_count,
        max_turns=100, current_speaker=roles[0], deal_status="Negotiating",
        current_offer=0.0, history=[], hidden_context={},
        warning_count=0, agreement_threshold=5000.0, scenario_config={},
        turn_order=roles, turn_order_index=0,
        agent_states=agent_states, active_toggles=[],
    )


class TestP15TurnNumberConsistency:
    """All history entries in the same cycle share the same turn_number,
    and turn_count only increments on wrap."""

    @settings(max_examples=100)
    @given(state=st_full_cycle_state())
    def test_all_entries_same_turn_number_within_cycle(self, state: NegotiationState):
        """**Validates: Requirements 3.9**

        Simulate a full cycle by calling _update_state for each role in turn_order.
        All history entries should have the same turn_number (the initial turn_count).
        """
        turn_order = state["turn_order"]
        initial_turn_count = state["turn_count"]
        all_entries: list[dict] = []

        # Simulate each agent in the cycle producing a history entry
        current_state = dict(state)
        for i, role in enumerate(turn_order):
            output = NegotiatorOutput(inner_thought="t", public_message="m", proposed_price=100.0)
            delta = _update_state(output, "negotiator", role, current_state)
            all_entries.extend(delta["history"])

            # Advance turn order
            turn_delta = _advance_turn_order(current_state)
            current_state = {**current_state, **turn_delta}

        # All entries within this cycle should share the initial turn_count
        for entry in all_entries:
            assert entry["turn_number"] == initial_turn_count

    @settings(max_examples=100)
    @given(state=st_full_cycle_state())
    def test_turn_count_increments_after_full_cycle(self, state: NegotiationState):
        """**Validates: Requirements 3.9**

        After advancing through all positions in turn_order, turn_count
        should have incremented by exactly 1.
        """
        turn_order = state["turn_order"]
        initial_count = state["turn_count"]

        current_state = dict(state)
        for _ in turn_order:
            delta = _advance_turn_order(current_state)
            current_state = {**current_state, **delta}

        # After a full cycle, turn_count should be initial + 1
        assert current_state["turn_count"] == initial_count + 1
        # And index should be back to 0
        assert current_state["turn_order_index"] == 0
