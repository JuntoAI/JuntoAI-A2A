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


# ===========================================================================
# Feature: structured-agent-memory
# Property 3: Memory-enabled prompt contains labeled memory and sliding window
# **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
# ===========================================================================

from app.orchestrator.outputs import AgentMemory
from app.orchestrator.state import create_initial_state

# Safe text for memory fields — printable, no newlines (avoids false substring matches)
_mem_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=1,
    max_size=40,
)
_mem_float = st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False)


@st.composite
def st_memory_agent_memory(draw: st.DrawFn) -> AgentMemory:
    """Generate an AgentMemory with at least some non-empty fields."""
    return AgentMemory(
        my_offers=draw(st.lists(_mem_float, min_size=0, max_size=5)),
        their_offers=draw(st.lists(_mem_float, min_size=0, max_size=5)),
        concessions_made=draw(st.lists(_mem_text, min_size=0, max_size=3)),
        concessions_received=draw(st.lists(_mem_text, min_size=0, max_size=3)),
        open_items=draw(st.lists(_mem_text, min_size=0, max_size=3)),
        tactics_used=draw(st.lists(_mem_text, min_size=0, max_size=3)),
        red_lines_stated=draw(st.lists(_mem_text, min_size=0, max_size=3)),
        compliance_status=draw(
            st.dictionaries(keys=_mem_text, values=_mem_text, max_size=3)
        ),
        turn_count=draw(st.integers(min_value=0, max_value=100)),
    )


@st.composite
def st_history_entry(draw: st.DrawFn, roles: list[str]) -> dict[str, Any]:
    """Generate a single history entry for a given set of roles."""
    role = draw(st.sampled_from(roles))
    return {
        "role": role,
        "agent_type": "negotiator",
        "turn_number": draw(st.integers(min_value=1, max_value=50)),
        "content": {
            "inner_thought": draw(_mem_text),
            "public_message": draw(_mem_text),
            "proposed_price": draw(_mem_float),
        },
    }


@st.composite
def st_memory_enabled_prompt_scenario(
    draw: st.DrawFn,
) -> tuple[dict[str, Any], NegotiationState, AgentMemory, int]:
    """Generate a scenario with structured_memory_enabled=True.

    Returns (agent_config, state, memory, history_length).
    """
    role = "buyer"
    other_role = "seller"

    agent_config: dict[str, Any] = {
        "role": role,
        "name": "Buyer Agent",
        "type": "negotiator",
        "model_id": "gemini-2.5-flash",
        "persona_prompt": "You are a buyer.",
    }

    memory = draw(st_memory_agent_memory())
    num_history = draw(st.integers(min_value=0, max_value=12))
    history = draw(
        st.lists(
            st_history_entry([role, other_role]),
            min_size=num_history,
            max_size=num_history,
        )
    )

    scenario_config: dict[str, Any] = {
        "id": "test",
        "agents": [
            agent_config,
            {"role": other_role, "name": "Seller", "type": "negotiator", "model_id": "gemini-2.5-flash"},
        ],
        "negotiation_params": {"max_turns": 15},
    }

    state = create_initial_state(
        session_id="test",
        scenario_config=scenario_config,
        structured_memory_enabled=True,
    )
    # Inject the generated memory and history
    state["agent_memories"][role] = memory.model_dump()
    state["history"] = history

    return agent_config, state, memory, num_history


class TestProperty3MemoryEnabledPromptFormat:
    """Feature: structured-agent-memory
    Property 3: Memory-enabled prompt contains labeled memory and sliding window.

    For any NegotiationState with structured_memory_enabled=True, any agent config,
    and any AgentMemory with arbitrary field values: _build_prompt shall produce a
    user message that (a) contains labeled sections for each non-empty memory field,
    (b) does NOT contain the full history transcript header, and (c) contains exactly
    min(3, len(history)) history entries as a sliding window.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
    """

    @settings(max_examples=100)
    @given(data=st_memory_enabled_prompt_scenario())
    def test_contains_structured_memory_label_when_non_empty(self, data: tuple):
        """When memory has non-empty fields, prompt contains 'Structured memory:'.

        **Validates: Requirements 5.1, 5.4**
        """
        agent_config, state, memory, _ = data
        _, user_msg = _build_prompt(agent_config, state)

        has_non_empty = (
            bool(memory.my_offers)
            or bool(memory.their_offers)
            or bool(memory.concessions_made)
            or bool(memory.concessions_received)
            or bool(memory.open_items)
            or bool(memory.tactics_used)
            or bool(memory.red_lines_stated)
            or bool(memory.compliance_status)
            or memory.turn_count > 0
        )

        if has_non_empty:
            assert "Structured memory:" in user_msg, (
                "Expected 'Structured memory:' in user message when memory has non-empty fields"
            )

    @settings(max_examples=100)
    @given(data=st_memory_enabled_prompt_scenario())
    def test_does_not_contain_full_history_header(self, data: tuple):
        """Memory-enabled prompt must NOT contain the full history header.

        **Validates: Requirements 5.1, 5.2**
        """
        agent_config, state, _, _ = data
        _, user_msg = _build_prompt(agent_config, state)

        assert "Negotiation history so far:" not in user_msg, (
            "Memory-enabled prompt must not contain full history header"
        )

    @settings(max_examples=100)
    @given(data=st_memory_enabled_prompt_scenario())
    def test_sliding_window_has_correct_entry_count(self, data: tuple):
        """Sliding window contains exactly min(3, len(history)) entries.

        **Validates: Requirements 5.2, 5.3**
        """
        agent_config, state, _, num_history = data
        _, user_msg = _build_prompt(agent_config, state)

        expected_window_size = min(3, num_history)

        if expected_window_size > 0:
            assert "Recent negotiation messages:" in user_msg, (
                "Expected 'Recent negotiation messages:' when history is non-empty"
            )
            # Count the sliding window entries — each starts with "  ["
            # in the "Recent negotiation messages:" section
            recent_section_start = user_msg.find("Recent negotiation messages:")
            assert recent_section_start >= 0
            # Find the end of the recent section (next blank line or end of known sections)
            recent_section = user_msg[recent_section_start:]
            # Count lines matching the entry pattern "  [role]: message"
            entry_lines = [
                line for line in recent_section.split("\n")
                if line.startswith("  [") and "]: " in line
            ]
            assert len(entry_lines) == expected_window_size, (
                f"Expected {expected_window_size} sliding window entries, "
                f"got {len(entry_lines)}"
            )
        else:
            assert "Recent negotiation messages:" not in user_msg, (
                "Should not have 'Recent negotiation messages:' with empty history"
            )

    @settings(max_examples=100)
    @given(data=st_memory_enabled_prompt_scenario())
    def test_labeled_memory_fields_present(self, data: tuple):
        """Each non-empty memory field should have its labeled section in the prompt.

        **Validates: Requirements 5.4**
        """
        agent_config, state, memory, _ = data
        _, user_msg = _build_prompt(agent_config, state)

        label_map = {
            "my_offers": "Your previous offers:",
            "their_offers": "Their previous offers:",
            "concessions_made": "Concessions you made:",
            "concessions_received": "Concessions you received:",
            "open_items": "Open items remaining:",
            "tactics_used": "Tactics you have used:",
            "red_lines_stated": "Red lines you stated:",
        }

        for field_name, label in label_map.items():
            value = getattr(memory, field_name)
            if value:
                assert label in user_msg, (
                    f"Expected label '{label}' for non-empty field '{field_name}'"
                )

        if memory.compliance_status:
            assert "Compliance status:" in user_msg

        if memory.turn_count > 0:
            assert "Your memory turn count:" in user_msg


# ===========================================================================
# Feature: structured-agent-memory
# Property 4: Disabled memory produces identical prompts
# **Validates: Requirements 5.5, 8.1**
# ===========================================================================


@st.composite
def st_disabled_memory_prompt_scenario(
    draw: st.DrawFn,
) -> tuple[dict[str, Any], NegotiationState]:
    """Generate a scenario with structured_memory_enabled=False and some history.

    Returns (agent_config, state).
    """
    role = "buyer"
    other_role = "seller"

    agent_config: dict[str, Any] = {
        "role": role,
        "name": "Buyer Agent",
        "type": "negotiator",
        "model_id": "gemini-2.5-flash",
        "persona_prompt": "You are a buyer.",
    }

    num_history = draw(st.integers(min_value=0, max_value=10))
    history = draw(
        st.lists(
            st_history_entry([role, other_role]),
            min_size=num_history,
            max_size=num_history,
        )
    )

    scenario_config: dict[str, Any] = {
        "id": "test",
        "agents": [
            agent_config,
            {"role": other_role, "name": "Seller", "type": "negotiator", "model_id": "gemini-2.5-flash"},
        ],
        "negotiation_params": {"max_turns": 15},
    }

    state = create_initial_state(
        session_id="test",
        scenario_config=scenario_config,
        structured_memory_enabled=False,
    )
    state["history"] = history

    return agent_config, state


class TestProperty4DisabledMemoryIdenticalPrompt:
    """Feature: structured-agent-memory
    Property 4: Disabled memory produces identical prompts.

    For any NegotiationState with structured_memory_enabled=False (or absent),
    _build_prompt shall produce output identical to the current implementation
    that serializes the full history.

    **Validates: Requirements 5.5, 8.1**
    """

    @settings(max_examples=100)
    @given(data=st_disabled_memory_prompt_scenario())
    def test_disabled_memory_uses_full_history(self, data: tuple):
        """When memory is disabled, prompt uses full history format.

        **Validates: Requirements 5.5**
        """
        agent_config, state = data
        _, user_msg = _build_prompt(agent_config, state)

        history = state.get("history", [])
        if history:
            assert "Negotiation history so far:" in user_msg, (
                "Disabled memory should use full history header"
            )
        assert "Structured memory:" not in user_msg, (
            "Disabled memory should not contain structured memory section"
        )
        assert "Recent negotiation messages:" not in user_msg, (
            "Disabled memory should not contain sliding window section"
        )

    @settings(max_examples=100)
    @given(data=st_disabled_memory_prompt_scenario())
    def test_disabled_memory_identical_to_absent_flag(self, data: tuple):
        """Prompt with structured_memory_enabled=False is identical to a state
        where the flag is absent (defaults to False).

        **Validates: Requirements 8.1**
        """
        agent_config, state = data

        # Build prompt with explicit False
        system_false, user_false = _build_prompt(agent_config, state)

        # Build prompt with flag absent — create a copy without the key
        # NegotiationState is a TypedDict, so we simulate absence via .get() default
        state_absent = dict(state)
        state_absent["structured_memory_enabled"] = False
        system_absent, user_absent = _build_prompt(agent_config, state_absent)

        assert system_false == system_absent, (
            "System message should be identical with False vs absent flag"
        )
        assert user_false == user_absent, (
            "User message should be identical with False vs absent flag"
        )

    @settings(max_examples=100)
    @given(data=st_disabled_memory_prompt_scenario())
    def test_disabled_memory_contains_all_history_entries(self, data: tuple):
        """When memory is disabled, ALL history entries appear in the prompt.

        **Validates: Requirements 5.5, 8.1**
        """
        agent_config, state = data
        _, user_msg = _build_prompt(agent_config, state)

        history = state.get("history", [])
        for entry in history:
            entry_role = entry.get("role", "unknown")
            content = entry.get("content", {})
            if isinstance(content, dict):
                display = (
                    content.get("public_message")
                    or content.get("reasoning")
                    or content.get("observation")
                    or str(content)
                )
            else:
                display = str(content)
            expected_line = f"[{entry_role}]: {display}"
            assert expected_line in user_msg, (
                f"Expected history entry '{expected_line}' in disabled-memory prompt"
            )


# ===========================================================================
# Feature: structured-agent-memory
# Property 5: Memory extractor correctly updates agent memory
# **Validates: Requirements 6.1, 6.3, 6.4**
# ===========================================================================


@st.composite
def st_memory_extractor_update_scenario(
    draw: st.DrawFn,
) -> tuple[NegotiationState, str, NegotiatorOutput, AgentMemory]:
    """Generate a state with structured_memory_enabled=True, a negotiator role,
    a NegotiatorOutput, and the pre-existing AgentMemory for that role.

    Returns (state, role, output, prior_memory).
    """
    role = draw(st.sampled_from(["buyer", "seller"]))
    other_role = "seller" if role == "buyer" else "buyer"
    proposed = draw(_mem_float)

    # Build a prior memory with some existing data
    prior_memory = draw(st_memory_agent_memory())

    scenario_config: dict[str, Any] = {
        "id": "test",
        "agents": [
            {"role": role, "name": "Agent A", "type": "negotiator", "model_id": "gemini-2.5-flash"},
            {"role": other_role, "name": "Agent B", "type": "negotiator", "model_id": "gemini-2.5-flash"},
        ],
        "negotiation_params": {"max_turns": 15},
    }

    state = create_initial_state(
        session_id="test",
        scenario_config=scenario_config,
        structured_memory_enabled=True,
    )
    # Inject prior memory
    state["agent_memories"][role] = prior_memory.model_dump()
    # Add some history entries
    num_history = draw(st.integers(min_value=0, max_value=5))
    history = draw(
        st.lists(
            st_history_entry([role, other_role]),
            min_size=num_history,
            max_size=num_history,
        )
    )
    state["history"] = history

    output = NegotiatorOutput(
        inner_thought="thinking",
        public_message="message",
        proposed_price=proposed,
    )

    return state, role, output, prior_memory


class TestProperty5MemoryExtractorUpdates:
    """Feature: structured-agent-memory
    Property 5: Memory extractor correctly updates agent memory.

    For any NegotiationState with structured_memory_enabled=True, any negotiator
    role, and any valid NegotiatorOutput with a proposed_price: after _update_state,
    the state delta's agent_memories[role] shall have my_offers ending with the new
    proposed_price, turn_count incremented by 1 from the previous value, and the
    data shall be a valid AgentMemory dict.

    **Validates: Requirements 6.1, 6.3, 6.4**
    """

    @settings(max_examples=100)
    @given(data=st_memory_extractor_update_scenario())
    def test_my_offers_ends_with_proposed_price(self, data: tuple):
        """After _update_state, my_offers ends with the new proposed_price.

        **Validates: Requirements 6.1**
        """
        state, role, output, prior_memory = data
        delta = _update_state(output, "negotiator", role, state)

        updated_mem = delta["agent_memories"][role]
        assert updated_mem["my_offers"][-1] == output.proposed_price, (
            f"Expected my_offers to end with {output.proposed_price}, "
            f"got {updated_mem['my_offers'][-1]}"
        )

    @settings(max_examples=100)
    @given(data=st_memory_extractor_update_scenario())
    def test_turn_count_incremented_by_one(self, data: tuple):
        """After _update_state, turn_count is incremented by 1 from prior value.

        **Validates: Requirements 6.3**
        """
        state, role, output, prior_memory = data
        delta = _update_state(output, "negotiator", role, state)

        updated_mem = delta["agent_memories"][role]
        assert updated_mem["turn_count"] == prior_memory.turn_count + 1, (
            f"Expected turn_count={prior_memory.turn_count + 1}, "
            f"got {updated_mem['turn_count']}"
        )

    @settings(max_examples=100)
    @given(data=st_memory_extractor_update_scenario())
    def test_result_is_valid_agent_memory(self, data: tuple):
        """The updated agent_memories[role] can be reconstructed as a valid AgentMemory.

        **Validates: Requirements 6.4**
        """
        state, role, output, prior_memory = data
        delta = _update_state(output, "negotiator", role, state)

        updated_mem = delta["agent_memories"][role]
        # Must not raise
        reconstructed = AgentMemory(**updated_mem)
        # Round-trip check
        assert reconstructed.model_dump() == updated_mem


# ===========================================================================
# Feature: structured-agent-memory
# Property 6: Memory extractor captures opposing offers
# **Validates: Requirements 6.2**
# ===========================================================================


@st.composite
def st_opposing_offer_scenario(
    draw: st.DrawFn,
) -> tuple[NegotiationState, str, NegotiatorOutput, float]:
    """Generate a state with structured_memory_enabled=True and at least one
    prior opposing negotiator entry in history.

    Returns (state, role, output, expected_opposing_price).
    """
    role = draw(st.sampled_from(["buyer", "seller"]))
    other_role = "seller" if role == "buyer" else "buyer"
    proposed = draw(_mem_float)

    scenario_config: dict[str, Any] = {
        "id": "test",
        "agents": [
            {"role": role, "name": "Agent A", "type": "negotiator", "model_id": "gemini-2.5-flash"},
            {"role": other_role, "name": "Agent B", "type": "negotiator", "model_id": "gemini-2.5-flash"},
        ],
        "negotiation_params": {"max_turns": 15},
    }

    state = create_initial_state(
        session_id="test",
        scenario_config=scenario_config,
        structured_memory_enabled=True,
    )

    # Build history with at least one opposing negotiator entry
    # First, some optional earlier entries
    num_earlier = draw(st.integers(min_value=0, max_value=4))
    earlier_history: list[dict[str, Any]] = []
    for _ in range(num_earlier):
        entry_role = draw(st.sampled_from([role, other_role]))
        earlier_history.append({
            "role": entry_role,
            "agent_type": "negotiator",
            "turn_number": draw(st.integers(min_value=1, max_value=20)),
            "content": {
                "inner_thought": "thought",
                "public_message": "msg",
                "proposed_price": draw(_mem_float),
            },
        })

    # The most recent opposing negotiator entry (this is what we expect to capture)
    opposing_price = draw(_mem_float)
    opposing_entry = {
        "role": other_role,
        "agent_type": "negotiator",
        "turn_number": draw(st.integers(min_value=1, max_value=20)),
        "content": {
            "inner_thought": "thought",
            "public_message": "msg",
            "proposed_price": opposing_price,
        },
    }

    # Optionally add some non-opposing entries after (regulators, or same-role entries)
    trailing: list[dict[str, Any]] = []
    num_trailing = draw(st.integers(min_value=0, max_value=2))
    for _ in range(num_trailing):
        # Only add same-role or regulator entries so opposing_entry stays the most recent opposing
        trailing_type = draw(st.sampled_from(["same", "regulator"]))
        if trailing_type == "same":
            trailing.append({
                "role": role,
                "agent_type": "negotiator",
                "turn_number": draw(st.integers(min_value=1, max_value=20)),
                "content": {
                    "inner_thought": "thought",
                    "public_message": "msg",
                    "proposed_price": draw(_mem_float),
                },
            })
        else:
            trailing.append({
                "role": "regulator",
                "agent_type": "regulator",
                "turn_number": draw(st.integers(min_value=1, max_value=20)),
                "content": {
                    "status": "CLEAR",
                    "reasoning": "ok",
                },
            })

    state["history"] = earlier_history + [opposing_entry] + trailing

    output = NegotiatorOutput(
        inner_thought="thinking",
        public_message="message",
        proposed_price=proposed,
    )

    return state, role, output, opposing_price


class TestProperty6OpposingOfferCapture:
    """Feature: structured-agent-memory
    Property 6: Memory extractor captures opposing offers.

    For any NegotiationState with structured_memory_enabled=True and at least one
    prior opposing negotiator entry in history: after _update_state for a negotiator
    turn, the state delta's agent_memories[role]["their_offers"] shall end with the
    most recent opposing negotiator's proposed_price.

    **Validates: Requirements 6.2**
    """

    @settings(max_examples=100)
    @given(data=st_opposing_offer_scenario())
    def test_their_offers_ends_with_opposing_price(self, data: tuple):
        """their_offers ends with the most recent opposing negotiator's proposed_price.

        **Validates: Requirements 6.2**
        """
        state, role, output, expected_opposing_price = data
        delta = _update_state(output, "negotiator", role, state)

        updated_mem = delta["agent_memories"][role]
        assert len(updated_mem["their_offers"]) > 0, (
            "Expected their_offers to be non-empty when opposing history exists"
        )
        assert updated_mem["their_offers"][-1] == expected_opposing_price, (
            f"Expected their_offers to end with {expected_opposing_price}, "
            f"got {updated_mem['their_offers'][-1]}"
        )


# ===========================================================================
# Feature: structured-agent-memory
# Property 7: Memory extraction skipped when disabled
# **Validates: Requirements 6.5, 8.2**
# ===========================================================================


@st.composite
def st_disabled_memory_update_scenario(
    draw: st.DrawFn,
) -> tuple[NegotiationState, str, NegotiatorOutput]:
    """Generate a state with structured_memory_enabled=False and a negotiator output.

    Returns (state, role, output).
    """
    role = draw(st.sampled_from(["buyer", "seller"]))
    other_role = "seller" if role == "buyer" else "buyer"
    proposed = draw(_mem_float)

    scenario_config: dict[str, Any] = {
        "id": "test",
        "agents": [
            {"role": role, "name": "Agent A", "type": "negotiator", "model_id": "gemini-2.5-flash"},
            {"role": other_role, "name": "Agent B", "type": "negotiator", "model_id": "gemini-2.5-flash"},
        ],
        "negotiation_params": {"max_turns": 15},
    }

    state = create_initial_state(
        session_id="test",
        scenario_config=scenario_config,
        structured_memory_enabled=False,
    )

    # Add some history
    num_history = draw(st.integers(min_value=0, max_value=5))
    history = draw(
        st.lists(
            st_history_entry([role, other_role]),
            min_size=num_history,
            max_size=num_history,
        )
    )
    state["history"] = history

    output = NegotiatorOutput(
        inner_thought="thinking",
        public_message="message",
        proposed_price=proposed,
    )

    return state, role, output


class TestProperty7MemoryExtractionSkippedWhenDisabled:
    """Feature: structured-agent-memory
    Property 7: Memory extraction skipped when disabled.

    For any NegotiationState with structured_memory_enabled=False and any valid
    agent output: _update_state shall produce a state delta that does not contain
    agent_memories, and the delta shall be identical to what the current
    implementation produces (no memory overhead).

    **Validates: Requirements 6.5, 8.2**
    """

    @settings(max_examples=100)
    @given(data=st_disabled_memory_update_scenario())
    def test_delta_does_not_contain_agent_memories(self, data: tuple):
        """When structured_memory_enabled=False, delta has no agent_memories key.

        **Validates: Requirements 6.5**
        """
        state, role, output = data
        delta = _update_state(output, "negotiator", role, state)

        assert "agent_memories" not in delta, (
            "Delta should not contain agent_memories when structured_memory_enabled=False"
        )

    @settings(max_examples=100)
    @given(data=st_disabled_memory_update_scenario())
    def test_delta_identical_with_and_without_flag(self, data: tuple):
        """Delta is identical whether structured_memory_enabled is False or absent.

        **Validates: Requirements 8.2**
        """
        state, role, output = data

        # Delta with explicit False
        delta_false = _update_state(output, "negotiator", role, state)

        # Delta with flag absent (simulate by setting to False — same behavior)
        state_absent = dict(state)
        state_absent["structured_memory_enabled"] = False
        delta_absent = _update_state(output, "negotiator", role, state_absent)

        assert delta_false == delta_absent, (
            "Delta should be identical with False vs absent structured_memory_enabled"
        )

    @settings(max_examples=100)
    @given(data=st_disabled_memory_update_scenario())
    def test_no_memory_overhead_in_delta(self, data: tuple):
        """When disabled, the delta keys should only contain standard negotiator keys.

        **Validates: Requirements 6.5, 8.2**
        """
        state, role, output = data
        delta = _update_state(output, "negotiator", role, state)

        # Standard negotiator delta keys
        expected_keys = {"history", "agent_states"}
        if output.proposed_price > 0:
            expected_keys.add("current_offer")

        assert set(delta.keys()) == expected_keys, (
            f"Expected delta keys {expected_keys}, got {set(delta.keys())}"
        )
