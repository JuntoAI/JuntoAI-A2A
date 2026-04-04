"""Property-based tests for create_initial_state milestone initialization.

# Feature: 110_hybrid-agent-memory, Property 2: milestone_summaries_enabled=True
# implies structured_memory_enabled=True

**Validates: Requirements 2.4, 2.5**
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.state import create_initial_state

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_role = st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L", "N")))
st_agent_type = st.sampled_from(["negotiator", "regulator", "observer"])
st_model_id = st.sampled_from([
    "gemini-3-flash-preview", "gemini-2.5-pro",
    "claude-3-5-sonnet-v2", "claude-sonnet-4-6",
])


@st.composite
def scenario_configs(draw: st.DrawFn) -> dict:
    """Generate random scenario configs with 1-6 agents and valid params."""
    num_agents = draw(st.integers(min_value=1, max_value=6))
    roles = draw(st.lists(st_role, min_size=num_agents, max_size=num_agents, unique=True))

    agents = []
    for role in roles:
        agents.append({
            "role": role,
            "name": f"Agent_{role}",
            "type": draw(st_agent_type),
            "model_id": draw(st_model_id),
        })

    turn_order = list(roles)  # simple: each role once

    params: dict = {
        "max_turns": draw(st.integers(min_value=1, max_value=100)),
        "agreement_threshold": draw(
            st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False)
        ),
        "turn_order": turn_order,
    }

    # Optionally include sliding_window_size and milestone_interval
    if draw(st.booleans()):
        params["sliding_window_size"] = draw(st.integers(min_value=1, max_value=50))
    if draw(st.booleans()):
        params["milestone_interval"] = draw(st.integers(min_value=2, max_value=50))

    return {"id": draw(st.text(min_size=1, max_size=20)), "agents": agents, "negotiation_params": params}


# ---------------------------------------------------------------------------
# Property 2: milestone_summaries_enabled=True implies structured_memory_enabled=True
# ---------------------------------------------------------------------------


class TestProperty2MilestoneImpliesStructuredMemory:
    """**Validates: Requirements 2.4, 2.5**

    Property 2: When milestone_summaries_enabled=True, structured_memory_enabled
    is also True and milestone_summaries has one empty list per agent role.
    """

    @settings(max_examples=100)
    @given(config=scenario_configs())
    def test_milestone_enabled_forces_structured_memory(self, config: dict):
        """When milestone_summaries_enabled=True, structured_memory_enabled must be True."""
        state = create_initial_state("prop-sess", config, milestone_summaries_enabled=True)

        assert state["milestone_summaries_enabled"] is True
        assert state["structured_memory_enabled"] is True

    @settings(max_examples=100)
    @given(config=scenario_configs())
    def test_milestone_enabled_initializes_summaries_per_role(self, config: dict):
        """milestone_summaries has one empty list per agent role when enabled."""
        state = create_initial_state("prop-sess", config, milestone_summaries_enabled=True)

        expected_roles = {a["role"] for a in config["agents"]}
        assert set(state["milestone_summaries"].keys()) == expected_roles
        for role in expected_roles:
            assert state["milestone_summaries"][role] == []

    @settings(max_examples=100)
    @given(config=scenario_configs())
    def test_milestone_disabled_empty_dict(self, config: dict):
        """milestone_summaries is an empty dict when disabled."""
        state = create_initial_state("prop-sess", config, milestone_summaries_enabled=False)

        assert state["milestone_summaries_enabled"] is False
        assert state["milestone_summaries"] == {}
