"""Property-based tests for NegotiationState conversion round-trip.

P2: State Conversion Round-Trip
**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**

FOR ALL valid NegotiationState dicts, from_pydantic(to_pydantic(state))
produces an equivalent state dict (except scenario_config which is lost).
turn_order, turn_order_index, and agent_states must survive.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.converters import from_pydantic, to_pydantic
from app.orchestrator.state import NegotiationState

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_text = st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N", "P")))
st_role = st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L", "N")))
st_price = st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False)
st_deal_status = st.sampled_from(["Negotiating", "Agreed", "Blocked", "Failed"])
st_agent_type = st.sampled_from(["negotiator", "regulator", "observer"])
st_model_id = st.sampled_from(["gemini-2.5-flash", "gemini-2.5-pro", "claude-3-5-sonnet-v2", "claude-sonnet-4-6"])

st_history_entry = st.fixed_dictionaries({
    "role": st_role,
    "message": st_text,
})

st_agent_state_value = st.fixed_dictionaries({
    "role": st_role,
    "name": st_text,
    "agent_type": st_agent_type,
    "model_id": st_model_id,
    "last_proposed_price": st_price,
    "warning_count": st.integers(min_value=0, max_value=100),
})


@st.composite
def st_negotiation_state(draw: st.DrawFn) -> NegotiationState:
    """Generate a valid NegotiationState with consistent turn_order and agent_states."""
    # Generate 1-6 unique roles
    num_agents = draw(st.integers(min_value=1, max_value=6))
    roles = draw(
        st.lists(
            st_role,
            min_size=num_agents,
            max_size=num_agents,
            unique=True,
        )
    )

    # Build turn_order from roles (may repeat roles like regulators)
    turn_order = draw(
        st.lists(
            st.sampled_from(roles),
            min_size=1,
            max_size=max(len(roles) * 2, 2),
        )
    )

    turn_order_index = draw(st.integers(min_value=0, max_value=len(turn_order) - 1))

    # Build agent_states keyed by role
    agent_states: dict = {}
    for role in roles:
        agent_states[role] = {
            "role": role,
            "name": draw(st_text),
            "agent_type": draw(st_agent_type),
            "model_id": draw(st_model_id),
            "last_proposed_price": draw(st_price),
            "warning_count": draw(st.integers(min_value=0, max_value=100)),
        }

    history = draw(st.lists(st_history_entry, max_size=10))
    active_toggles = draw(st.lists(st_text, max_size=5))

    return NegotiationState(
        session_id=draw(st_text),
        scenario_id=draw(st_text),
        turn_count=draw(st.integers(min_value=0, max_value=1000)),
        max_turns=draw(st.integers(min_value=1, max_value=1000)),
        current_speaker=turn_order[turn_order_index],
        deal_status=draw(st_deal_status),
        current_offer=draw(st_price),
        history=history,
        hidden_context=draw(st.fixed_dictionaries({})),
        warning_count=draw(st.integers(min_value=0, max_value=1000)),
        agreement_threshold=draw(st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False)),
        scenario_config={},  # Always empty — Pydantic model doesn't carry it
        turn_order=turn_order,
        turn_order_index=turn_order_index,
        agent_states=agent_states,
        active_toggles=active_toggles,
    )


# ---------------------------------------------------------------------------
# P2: State Conversion Round-Trip
# ---------------------------------------------------------------------------


class TestP2StateConversionRoundTrip:
    """from_pydantic(to_pydantic(state)) == state when scenario_config is {}."""

    @settings(max_examples=100)
    @given(state=st_negotiation_state())
    def test_round_trip_preserves_all_fields(self, state: NegotiationState):
        """**Validates: Requirements 10.1, 10.2, 10.3**"""
        restored = from_pydantic(to_pydantic(state))

        for key in state:
            assert restored[key] == state[key], f"Field {key!r} mismatch"

    @settings(max_examples=100)
    @given(state=st_negotiation_state())
    def test_turn_order_survives(self, state: NegotiationState):
        """**Validates: Requirements 10.1, 10.2** — turn_order and turn_order_index survive."""
        restored = from_pydantic(to_pydantic(state))

        assert restored["turn_order"] == state["turn_order"]
        assert restored["turn_order_index"] == state["turn_order_index"]

    @settings(max_examples=100)
    @given(state=st_negotiation_state())
    def test_agent_states_survives(self, state: NegotiationState):
        """**Validates: Requirements 10.4, 10.5** — agent_states dict survives round-trip."""
        restored = from_pydantic(to_pydantic(state))

        assert restored["agent_states"] == state["agent_states"]
        # Verify each agent's sub-fields
        for role, agent_data in state["agent_states"].items():
            assert role in restored["agent_states"]
            for field_key, field_val in agent_data.items():
                assert restored["agent_states"][role][field_key] == field_val
