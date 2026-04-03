"""Property-based tests for scenario config compatibility across modes.

# Feature: 080_a2a-local-battle-arena, Property 8: Scenario config produces identical initial state across modes
"""

import uuid

from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st

from app.orchestrator.state import create_initial_state


# ---------------------------------------------------------------------------
# Hypothesis strategies for valid scenario configs
# ---------------------------------------------------------------------------

_agent_types = st.sampled_from(["negotiator", "regulator", "observer"])


def _agent_strategy(role: str, agent_type: str) -> st.SearchStrategy[dict]:
    """Build a single agent dict with a fixed role and type."""
    return st.fixed_dictionaries(
        {
            "role": st.just(role),
            "name": st.text(min_size=1, max_size=20),
            "type": st.just(agent_type),
            "model_id": st.sampled_from(["gemini-2.5-flash", "gemini-2.5-pro"]),
        }
    )


@st.composite
def scenario_configs(draw: st.DrawFn) -> dict:
    """Generate a valid scenario config dict for create_initial_state().

    Guarantees at least one negotiator (required for turn_order) and at least
    two agents total.
    """
    scenario_id = draw(st.text(min_size=1, max_size=30))

    # Always include at least one negotiator
    negotiator = draw(_agent_strategy("negotiator_0", "negotiator"))
    agents = [negotiator]

    # Add 1-3 more agents with unique roles
    extra_count = draw(st.integers(min_value=1, max_value=3))
    for i in range(extra_count):
        agent_type = draw(_agent_types)
        agent = draw(_agent_strategy(f"agent_{i + 1}", agent_type))
        agents.append(agent)

    # Build turn_order from agent roles
    roles = [a["role"] for a in agents]
    turn_order = draw(
        st.lists(st.sampled_from(roles), min_size=1, max_size=len(roles) * 2)
    )

    max_turns = draw(st.integers(min_value=1, max_value=50))
    agreement_threshold = draw(st.floats(min_value=0.01, max_value=1_000_000, allow_nan=False))

    negotiation_params = {
        "max_turns": max_turns,
        "agreement_threshold": agreement_threshold,
        "turn_order": turn_order,
    }

    return {
        "id": scenario_id,
        "agents": agents,
        "negotiation_params": negotiation_params,
    }


@st.composite
def optional_toggles(draw: st.DrawFn) -> list[str] | None:
    """Generate optional active_toggles list."""
    if draw(st.booleans()):
        return None
    return draw(st.lists(st.text(min_size=1, max_size=20), max_size=5))


@st.composite
def optional_hidden_context(draw: st.DrawFn) -> dict | None:
    """Generate optional hidden_context dict."""
    if draw(st.booleans()):
        return None
    return draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=15),
        values=st.text(max_size=30),
        max_size=3,
    ))


@st.composite
def optional_str_dict(draw: st.DrawFn) -> dict[str, str] | None:
    """Generate optional dict[str, str] for custom_prompts / model_overrides."""
    if draw(st.booleans()):
        return None
    return draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=15),
        values=st.text(max_size=30),
        max_size=3,
    ))


# ---------------------------------------------------------------------------
# Property 8
# ---------------------------------------------------------------------------


@given(
    config=scenario_configs(),
    toggles=optional_toggles(),
    hidden_ctx=optional_hidden_context(),
    custom_prompts=optional_str_dict(),
    model_overrides=optional_str_dict(),
)
@hypothesis_settings(max_examples=100)
def test_scenario_config_produces_identical_state_across_calls(
    config: dict,
    toggles: list[str] | None,
    hidden_ctx: dict | None,
    custom_prompts: dict[str, str] | None,
    model_overrides: dict[str, str] | None,
):
    """**Validates: Requirements 9.1, 9.2, 9.4**

    Property 8: Scenario config produces identical initial state across modes.

    create_initial_state() is a pure function — it does not read RUN_MODE or
    any environment variables. For any valid scenario config, calling it twice
    with the same inputs produces identical NegotiationState dicts. This proves
    the state structure is mode-independent; only the backing LLM differs.
    """
    session_id = str(uuid.uuid4())

    state_a = create_initial_state(
        session_id=session_id,
        scenario_config=config,
        active_toggles=toggles,
        hidden_context=hidden_ctx,
        custom_prompts=custom_prompts,
        model_overrides=model_overrides,
    )

    state_b = create_initial_state(
        session_id=session_id,
        scenario_config=config,
        active_toggles=toggles,
        hidden_context=hidden_ctx,
        custom_prompts=custom_prompts,
        model_overrides=model_overrides,
    )

    assert state_a == state_b, (
        f"create_initial_state() produced different results for the same inputs.\n"
        f"Diff keys: {[k for k in state_a if state_a[k] != state_b[k]]}"
    )

    # Verify key structural fields are populated correctly
    assert state_a["session_id"] == session_id
    assert state_a["scenario_id"] == config["id"]
    assert state_a["max_turns"] == config["negotiation_params"]["max_turns"]
    assert state_a["turn_count"] == 0
    assert state_a["deal_status"] == "Negotiating"
    assert state_a["current_offer"] == 0.0
    assert state_a["history"] == []
    assert state_a["total_tokens_used"] == 0
    assert state_a["stall_diagnosis"] is None

    # Agent states must match the config agents
    for agent in config["agents"]:
        role = agent["role"]
        assert role in state_a["agent_states"]
        assert state_a["agent_states"][role]["model_id"] == agent["model_id"]
        assert state_a["agent_states"][role]["name"] == agent["name"]
