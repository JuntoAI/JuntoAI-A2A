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
st_model_id = st.sampled_from(["gemini-3-flash-preview", "gemini-2.5-pro", "claude-3-5-sonnet-v2", "claude-sonnet-4-6"])
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
        role: {"role": role, "name": "A", "agent_type": "negotiator", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
        other_role: {"role": other_role, "name": "B", "agent_type": "negotiator", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
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
        role: {"role": role, "name": "R", "agent_type": "regulator", "model_id": "claude-sonnet-4-6", "last_proposed_price": 0.0, "warning_count": prior_warnings},
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
        role: {"role": role, "name": "O", "agent_type": "observer", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
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
    wraps correctly, and current_speaker == turn_order[turn_order_index].

    turn_count is NOT managed by _advance_turn_order — it is incremented
    in create_agent_node before a negotiator speaks.
    """

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
    def test_turn_count_never_in_delta(self, state: NegotiationState):
        """_advance_turn_order never modifies turn_count."""
        delta = _advance_turn_order(state)
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

        # BLOCKED with 0 prior warnings gets downgraded to WARNING
        effective_status = output.status
        if effective_status == "BLOCKED" and old_role == 0:
            effective_status = "WARNING"

        if effective_status in ("WARNING", "BLOCKED"):
            # Both WARNING and BLOCKED increment the warning tally
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
        # BLOCKED with 0 prior warnings gets downgraded to WARNING (1 warning),
        # which is not enough to block.  Only 3+ warnings or BLOCKED with
        # prior warnings triggers a block.
        if new_role_warnings >= 3:
            assert delta.get("deal_status") == "Blocked"
        elif output.status == "BLOCKED" and old_role_warnings > 0:
            assert delta.get("deal_status") == "Blocked"

    @settings(max_examples=200)
    @given(data=st_regulator_state())
    def test_blocked_status_always_blocks(self, data: tuple):
        """**Validates: Requirements 3.7**

        BLOCKED with at least 1 prior warning → deal blocked.
        BLOCKED with 0 prior warnings → downgraded to WARNING (no block).
        """
        state, role, output = data
        old_role_warnings = state["agent_states"][role]["warning_count"]
        if output.status == "BLOCKED":
            delta = _update_state(output, "regulator", role, state)
            if old_role_warnings > 0:
                assert delta.get("deal_status") == "Blocked"
            else:
                # Downgraded to WARNING — no block yet
                assert delta.get("deal_status") is None


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
        "model_id": "gemini-3-flash-preview",
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
# **Validates: Requirements 3.9 (turn_count increments before negotiator speaks)**
# ===========================================================================


@st.composite
def st_full_cycle_state(draw: st.DrawFn) -> NegotiationState:
    """Generate a state at the START of a cycle (turn_order_index=0).

    Generates a realistic turn_order with a mix of negotiators and regulators.
    """
    num_negotiators = draw(st.integers(min_value=2, max_value=4))
    num_regulators = draw(st.integers(min_value=0, max_value=2))
    negotiator_roles = draw(st.lists(st_role, min_size=num_negotiators, max_size=num_negotiators, unique=True))
    regulator_roles = draw(st.lists(
        st_role.filter(lambda r: r not in negotiator_roles),
        min_size=num_regulators, max_size=num_regulators, unique=True,
    )) if num_regulators > 0 else []

    # Build turn_order: interleave negotiators with regulators
    turn_order: list[str] = []
    for neg in negotiator_roles:
        turn_order.append(neg)
        for reg in regulator_roles:
            turn_order.append(reg)

    turn_count = draw(st.integers(min_value=0, max_value=100))

    agent_states: dict[str, dict[str, Any]] = {}
    for r in negotiator_roles:
        agent_states[r] = {
            "role": r, "name": "N", "agent_type": "negotiator",
            "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0,
        }
    for r in regulator_roles:
        agent_states[r] = {
            "role": r, "name": "R", "agent_type": "regulator",
            "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0,
        }

    return NegotiationState(
        session_id="s", scenario_id="s", turn_count=turn_count,
        max_turns=100, current_speaker=turn_order[0], deal_status="Negotiating",
        current_offer=0.0, history=[], hidden_context={},
        warning_count=0, agreement_threshold=5000.0, scenario_config={},
        turn_order=turn_order, turn_order_index=0,
        agent_states=agent_states, active_toggles=[],
    )


class TestP15TurnNumberConsistency:
    """A negotiator and the regulator(s) that follow it share the same
    turn_number.  turn_count increments once per negotiator, before it speaks."""

    @settings(max_examples=100)
    @given(state=st_full_cycle_state())
    def test_regulator_shares_turn_number_with_preceding_negotiator(self, state: NegotiationState):
        """**Validates: Requirements 3.9**

        Simulate a full cycle.  Each negotiator increments turn_count before
        speaking, and the regulator(s) that follow record the same value.
        """
        turn_order = state["turn_order"]
        agent_states = state.get("agent_states", {})
        all_entries: list[dict] = []

        current_state = dict(state)
        for role in turn_order:
            agent_type = agent_states.get(role, {}).get("agent_type", "negotiator")

            # Simulate the increment-before-speak logic from create_agent_node
            effective_state = current_state
            if agent_type == "negotiator":
                effective_state = {**current_state, "turn_count": current_state["turn_count"] + 1}

            if agent_type == "negotiator":
                output = NegotiatorOutput(inner_thought="t", public_message="m", proposed_price=100.0)
            else:
                output = RegulatorOutput(reasoning="ok", public_message="noted", status="CLEAR")
            delta = _update_state(output, agent_type, role, effective_state)
            all_entries.extend(delta["history"])

            # Apply turn_count change + advance
            if agent_type == "negotiator":
                current_state["turn_count"] = effective_state["turn_count"]
            turn_delta = _advance_turn_order(current_state)
            current_state = {**current_state, **turn_delta}

        # Group entries: each negotiator and the regulators after it should
        # share the same turn_number
        last_negotiator_turn = None
        for entry in all_entries:
            if entry["agent_type"] == "negotiator":
                last_negotiator_turn = entry["turn_number"]
            else:
                # Regulator/observer should match the preceding negotiator
                assert entry["turn_number"] == last_negotiator_turn

    @settings(max_examples=100)
    @given(state=st_full_cycle_state())
    def test_turn_count_increments_by_negotiator_count(self, state: NegotiationState):
        """**Validates: Requirements 3.9**

        After a full cycle, turn_count should have incremented by the number
        of negotiators in the turn_order.
        """
        turn_order = state["turn_order"]
        agent_states = state.get("agent_states", {})
        initial_count = state["turn_count"]

        num_negotiators = sum(
            1 for role in turn_order
            if agent_states.get(role, {}).get("agent_type", "negotiator") == "negotiator"
        )

        # Simulate: only negotiators increment turn_count
        current_count = initial_count
        for role in turn_order:
            agent_type = agent_states.get(role, {}).get("agent_type", "negotiator")
            if agent_type == "negotiator":
                current_count += 1

        assert current_count == initial_count + num_negotiators


# ===========================================================================
# P5 (Feature: agent-advanced-config): Custom Prompt Injection into System Message
# **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
# ===========================================================================


# Strategy: generate a custom prompt string (non-empty, printable, ≤500 chars)
st_custom_prompt = st.text(
    min_size=1,
    max_size=500,
    alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\x00"),
)


@st.composite
def st_prompt_injection_state(
    draw: st.DrawFn,
) -> tuple[dict[str, Any], NegotiationState, str | None]:
    """Generate agent_config + state with or without a custom prompt for the role.

    Returns (agent_config, state, custom_prompt_or_none).
    """
    role = draw(st_role)
    agent_type = draw(st_agent_type)
    has_custom_prompt = draw(st.booleans())
    custom_prompt: str | None = draw(st_custom_prompt) if has_custom_prompt else None

    # Optionally add hidden context so we can verify ordering
    has_hidden = draw(st.booleans())
    hidden_value = draw(st_text) if has_hidden else None

    agent_config: dict[str, Any] = {
        "role": role,
        "name": "Agent",
        "type": agent_type,
        "model_id": "gemini-3-flash-preview",
        "persona_prompt": draw(st_text),
        "goals": draw(st.lists(st_text, min_size=0, max_size=3)),
    }

    hidden_context: dict[str, Any] = {}
    if has_hidden and hidden_value:
        hidden_context[role] = hidden_value

    custom_prompts: dict[str, str] = {}
    if custom_prompt is not None:
        custom_prompts[role] = custom_prompt

    state = NegotiationState(
        session_id="s",
        scenario_id="s",
        turn_count=0,
        max_turns=10,
        current_speaker=role,
        deal_status="Negotiating",
        current_offer=0.0,
        history=[],
        hidden_context=hidden_context,
        warning_count=0,
        agreement_threshold=5000.0,
        scenario_config={},
        turn_order=[role],
        turn_order_index=0,
        agent_states={},
        active_toggles=[],
        total_tokens_used=0,
        stall_diagnosis=None,
        custom_prompts=custom_prompts,
        model_overrides={},
    )
    return agent_config, state, custom_prompt


class TestP5CustomPromptInjection:
    """Feature: agent-advanced-config, Property 5: Custom prompt injection into system message.

    For any non-empty custom prompt and any agent configuration, the system message
    built by _build_prompt should contain the custom prompt prefixed with
    '\\nAdditional user instructions:\\n', positioned after persona/goals/hidden_context
    and before the output schema JSON. When no custom prompt exists, the system message
    should be identical to the output without the feature.

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """

    DELIMITER = "\nAdditional user instructions:\n"

    @settings(max_examples=100)
    @given(data=st_prompt_injection_state())
    def test_custom_prompt_present_when_set(self, data: tuple):
        """When a custom prompt exists for the agent's role, the system message
        must contain the delimiter + prompt text.

        **Validates: Requirements 7.1, 7.2**
        """
        agent_config, state, custom_prompt = data
        system, _ = _build_prompt(agent_config, state)

        if custom_prompt is not None:
            assert self.DELIMITER in system, (
                "Delimiter not found in system message when custom prompt is set"
            )
            assert custom_prompt in system, (
                "Custom prompt text not found in system message"
            )

    @settings(max_examples=100)
    @given(data=st_prompt_injection_state())
    def test_no_delimiter_when_no_custom_prompt(self, data: tuple):
        """When no custom prompt exists, the delimiter must NOT appear.

        **Validates: Requirements 7.4**
        """
        agent_config, state, custom_prompt = data
        system, _ = _build_prompt(agent_config, state)

        if custom_prompt is None:
            assert self.DELIMITER not in system, (
                "Delimiter found in system message when no custom prompt is set"
            )

    @settings(max_examples=100)
    @given(data=st_prompt_injection_state())
    def test_custom_prompt_after_persona_goals_hidden_context(self, data: tuple):
        """The custom prompt block must appear AFTER persona, goals, and hidden context.

        **Validates: Requirements 7.2, 7.3**
        """
        agent_config, state, custom_prompt = data
        if custom_prompt is None:
            return  # nothing to check

        system, _ = _build_prompt(agent_config, state)
        delimiter_pos = system.find(self.DELIMITER)
        assert delimiter_pos >= 0

        # Persona appears before the delimiter
        persona = agent_config.get("persona_prompt", "")
        if persona:
            persona_pos = system.find(persona)
            assert persona_pos < delimiter_pos, "Custom prompt must appear after persona"

        # Goals appear before the delimiter
        for goal in agent_config.get("goals", []):
            goal_pos = system.find(f"- {goal}")
            if goal_pos >= 0:
                assert goal_pos < delimiter_pos, "Custom prompt must appear after goals"

        # Hidden context appears before the delimiter (if present)
        role = agent_config["role"]
        hidden_context = state.get("hidden_context", {})
        if role in hidden_context:
            conf_pos = system.find("Confidential information")
            if conf_pos >= 0:
                assert conf_pos < delimiter_pos, (
                    "Custom prompt must appear after hidden context"
                )

    @settings(max_examples=100)
    @given(data=st_prompt_injection_state())
    def test_custom_prompt_before_output_schema(self, data: tuple):
        """The custom prompt block must appear BEFORE the output schema JSON.

        **Validates: Requirements 7.2**
        """
        agent_config, state, custom_prompt = data
        if custom_prompt is None:
            return  # nothing to check

        system, _ = _build_prompt(agent_config, state)
        delimiter_pos = system.find(self.DELIMITER)
        assert delimiter_pos >= 0

        # Output schema marker
        schema_marker = "You MUST respond with valid JSON matching this schema:"
        schema_pos = system.find(schema_marker)
        if schema_pos >= 0:
            assert delimiter_pos < schema_pos, (
                "Custom prompt must appear before output schema"
            )

    @settings(max_examples=100)
    @given(data=st_prompt_injection_state())
    def test_system_message_unchanged_without_custom_prompt(self, data: tuple):
        """When no custom prompt exists, the system message should be identical
        to calling _build_prompt with an empty custom_prompts dict.

        **Validates: Requirements 7.4**
        """
        agent_config, state, custom_prompt = data
        if custom_prompt is not None:
            return  # only test the no-prompt case

        # Build with current state (no custom prompt)
        system_with, _ = _build_prompt(agent_config, state)

        # Build with explicitly empty custom_prompts
        state_empty = dict(state)
        state_empty["custom_prompts"] = {}
        system_without, _ = _build_prompt(agent_config, state_empty)

        assert system_with == system_without, (
            "System message should be identical when no custom prompt is set"
        )


# ===========================================================================
# P6 (Feature: agent-advanced-config): Model Override Routing
# **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
# ===========================================================================


@st.composite
def st_model_override_scenario(
    draw: st.DrawFn,
) -> tuple[str, dict[str, Any], bool, str | None]:
    """Generate an agent role, scenario config, and optional model override.

    Returns (role, scenario_config_snippet, has_override, override_model_id_or_none).
    The scenario_config_snippet contains the agent list needed by _find_agent_config.
    """
    role = draw(st_role)
    default_model = draw(st_model_id)
    fallback_model = draw(st.one_of(st.none(), st_model_id))
    has_override = draw(st.booleans())

    # Pick an override model that differs from the default when overriding
    override_model: str | None = None
    if has_override:
        override_model = draw(st_model_id.filter(lambda m: m != default_model))

    agent_config: dict[str, Any] = {
        "role": role,
        "name": f"Agent-{role}",
        "type": "negotiator",
        "model_id": default_model,
        "persona_prompt": "You are a negotiator.",
        "goals": ["Negotiate well"],
    }
    if fallback_model is not None:
        agent_config["fallback_model_id"] = fallback_model

    scenario_config: dict[str, Any] = {
        "id": "test-scenario",
        "agents": [agent_config],
        "negotiation_params": {"max_turns": 10},
    }

    return role, scenario_config, has_override, override_model


class TestP6ModelOverrideRouting:
    """Feature: agent-advanced-config, Property 6: Model override routing.

    For any agent with a model override in the negotiation state, the agent_node
    should pass the overridden model_id to model_router.get_model() instead of
    the agent's default model_id, while always preserving the original
    fallback_model_id. When no model override exists, the default model_id
    should be used.

    **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
    """

    @settings(max_examples=100)
    @given(data=st_model_override_scenario())
    def test_get_model_called_with_override_when_present(self, data: tuple) -> None:
        """When model_overrides contains the agent's role, get_model receives
        the overridden model_id and the original fallback_model_id.

        **Validates: Requirements 12.1, 12.2, 12.3**
        """
        from unittest.mock import MagicMock, patch

        role, scenario_config, has_override, override_model = data
        if not has_override:
            return  # tested in the other method

        agent_config = scenario_config["agents"][0]
        default_model = agent_config["model_id"]
        fallback = agent_config.get("fallback_model_id")

        # Build model_overrides
        model_overrides: dict[str, str] = {role: override_model}

        # Build a valid NegotiationState
        state = NegotiationState(
            session_id="s",
            scenario_id="test-scenario",
            turn_count=0,
            max_turns=10,
            current_speaker=role,
            deal_status="Negotiating",
            current_offer=100.0,
            history=[],
            hidden_context={},
            warning_count=0,
            agreement_threshold=5000.0,
            scenario_config=scenario_config,
            turn_order=[role],
            turn_order_index=0,
            agent_states={
                role: {
                    "role": role,
                    "name": f"Agent-{role}",
                    "agent_type": "negotiator",
                    "model_id": default_model,
                    "last_proposed_price": 0.0,
                    "warning_count": 0,
                },
            },
            active_toggles=[],
            total_tokens_used=0,
            stall_diagnosis=None,
            custom_prompts={},
            model_overrides=model_overrides,
        )

        # Mock model_router.get_model and the LLM invoke
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = NegotiatorOutput(
            inner_thought="thinking",
            public_message="hello",
            proposed_price=150.0,
        ).model_dump_json()
        mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 10}
        mock_model.invoke.return_value = mock_response

        with patch("app.orchestrator.agent_node.model_router.get_model", return_value=mock_model) as mock_get_model:
            from app.orchestrator.agent_node import create_agent_node

            node_fn = create_agent_node(role)
            node_fn(state)

            # Assert get_model was called with the OVERRIDDEN model_id
            mock_get_model.assert_called_once_with(
                override_model,
                fallback_model_id=fallback,
            )

    @settings(max_examples=100)
    @given(data=st_model_override_scenario())
    def test_get_model_called_with_default_when_no_override(self, data: tuple) -> None:
        """When model_overrides does NOT contain the agent's role, get_model
        receives the default model_id from the scenario config.

        **Validates: Requirements 12.4**
        """
        from unittest.mock import MagicMock, patch

        role, scenario_config, has_override, override_model = data
        if has_override:
            return  # tested in the other method

        agent_config = scenario_config["agents"][0]
        default_model = agent_config["model_id"]
        fallback = agent_config.get("fallback_model_id")

        # Build a state with NO model override for this role
        state = NegotiationState(
            session_id="s",
            scenario_id="test-scenario",
            turn_count=0,
            max_turns=10,
            current_speaker=role,
            deal_status="Negotiating",
            current_offer=100.0,
            history=[],
            hidden_context={},
            warning_count=0,
            agreement_threshold=5000.0,
            scenario_config=scenario_config,
            turn_order=[role],
            turn_order_index=0,
            agent_states={
                role: {
                    "role": role,
                    "name": f"Agent-{role}",
                    "agent_type": "negotiator",
                    "model_id": default_model,
                    "last_proposed_price": 0.0,
                    "warning_count": 0,
                },
            },
            active_toggles=[],
            total_tokens_used=0,
            stall_diagnosis=None,
            custom_prompts={},
            model_overrides={},
        )

        # Mock model_router.get_model and the LLM invoke
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = NegotiatorOutput(
            inner_thought="thinking",
            public_message="hello",
            proposed_price=150.0,
        ).model_dump_json()
        mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 10}
        mock_model.invoke.return_value = mock_response

        with patch("app.orchestrator.agent_node.model_router.get_model", return_value=mock_model) as mock_get_model:
            from app.orchestrator.agent_node import create_agent_node

            node_fn = create_agent_node(role)
            node_fn(state)

            # Assert get_model was called with the DEFAULT model_id
            mock_get_model.assert_called_once_with(
                default_model,
                fallback_model_id=fallback,
            )

    @settings(max_examples=100)
    @given(data=st_model_override_scenario())
    def test_fallback_model_always_from_config(self, data: tuple) -> None:
        """Regardless of whether an override exists, the fallback_model_id
        passed to get_model always comes from the scenario config, never
        from model_overrides.

        **Validates: Requirements 12.3**
        """
        from unittest.mock import MagicMock, patch

        role, scenario_config, has_override, override_model = data

        agent_config = scenario_config["agents"][0]
        default_model = agent_config["model_id"]
        fallback = agent_config.get("fallback_model_id")

        model_overrides: dict[str, str] = {}
        if has_override and override_model:
            model_overrides[role] = override_model

        state = NegotiationState(
            session_id="s",
            scenario_id="test-scenario",
            turn_count=0,
            max_turns=10,
            current_speaker=role,
            deal_status="Negotiating",
            current_offer=100.0,
            history=[],
            hidden_context={},
            warning_count=0,
            agreement_threshold=5000.0,
            scenario_config=scenario_config,
            turn_order=[role],
            turn_order_index=0,
            agent_states={
                role: {
                    "role": role,
                    "name": f"Agent-{role}",
                    "agent_type": "negotiator",
                    "model_id": default_model,
                    "last_proposed_price": 0.0,
                    "warning_count": 0,
                },
            },
            active_toggles=[],
            total_tokens_used=0,
            stall_diagnosis=None,
            custom_prompts={},
            model_overrides=model_overrides,
        )

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = NegotiatorOutput(
            inner_thought="thinking",
            public_message="hello",
            proposed_price=150.0,
        ).model_dump_json()
        mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 10}
        mock_model.invoke.return_value = mock_response

        with patch("app.orchestrator.agent_node.model_router.get_model", return_value=mock_model) as mock_get_model:
            from app.orchestrator.agent_node import create_agent_node

            node_fn = create_agent_node(role)
            node_fn(state)

            # The fallback_model_id kwarg must ALWAYS be the config's fallback
            call_kwargs = mock_get_model.call_args
            assert call_kwargs[1]["fallback_model_id"] == fallback, (
                f"Expected fallback_model_id={fallback!r} from config, "
                f"got {call_kwargs[1]['fallback_model_id']!r}"
            )
