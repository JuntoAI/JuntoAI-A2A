"""Property-based tests for the AgentMemory model.

Uses hypothesis to verify universal invariants across generated inputs.
"""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.outputs import AgentMemory


# ---------------------------------------------------------------------------
# Reusable hypothesis strategy for generating arbitrary AgentMemory instances
# ---------------------------------------------------------------------------

# Safe text: printable characters, reasonable length
_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs", "P")),
    min_size=0,
    max_size=50,
)

# Finite floats suitable for offer prices
_offer_float = st.floats(
    min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False
)


@st.composite
def agent_memory_strategy(draw):
    """Generate a random valid AgentMemory instance with realistic field values."""
    return AgentMemory(
        my_offers=draw(st.lists(_offer_float, min_size=0, max_size=20)),
        their_offers=draw(st.lists(_offer_float, min_size=0, max_size=20)),
        concessions_made=draw(st.lists(_safe_text, min_size=0, max_size=10)),
        concessions_received=draw(st.lists(_safe_text, min_size=0, max_size=10)),
        open_items=draw(st.lists(_safe_text, min_size=0, max_size=10)),
        tactics_used=draw(st.lists(_safe_text, min_size=0, max_size=10)),
        red_lines_stated=draw(st.lists(_safe_text, min_size=0, max_size=10)),
        compliance_status=draw(
            st.dictionaries(keys=_safe_text, values=_safe_text, max_size=10)
        ),
        turn_count=draw(st.integers(min_value=0, max_value=10000)),
    )


# ---------------------------------------------------------------------------
# Feature: structured-agent-memory
# Property 1: AgentMemory serialization round-trip
# **Validates: Requirements 1.4, 9.1**
#
# For any valid AgentMemory instance with arbitrary field values, calling
# model_dump() and then reconstructing via AgentMemory(**data) shall produce
# an object equal to the original.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(memory=agent_memory_strategy())
def test_agent_memory_round_trip(memory: AgentMemory):
    """Serializing and deserializing any valid AgentMemory must produce an equal object."""
    data = memory.model_dump()
    restored = AgentMemory(**data)
    assert restored == memory


# ---------------------------------------------------------------------------
# Feature: structured-agent-memory
# Property 10: AgentMemory produces JSON-serializable output
# **Validates: Requirements 9.3**
#
# For any valid AgentMemory instance, model_dump() shall produce a dict that
# json.dumps() can serialize without error (no custom objects, datetimes, or
# non-primitive types).
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(memory=agent_memory_strategy())
def test_agent_memory_json_serializable(memory: AgentMemory):
    """model_dump() output must be JSON-serializable for any valid AgentMemory."""
    data = memory.model_dump()
    serialized = json.dumps(data)
    # Verify the serialized JSON can be parsed back
    parsed = json.loads(serialized)
    assert parsed == data


# ---------------------------------------------------------------------------
# Feature: structured-agent-memory
# Property 2: create_initial_state memory initialization
# **Validates: Requirements 2.3, 2.4, 2.5**
#
# For any valid scenario config with N agents and any boolean value for
# structured_memory_enabled: when True, create_initial_state shall produce
# agent_memories with exactly N keys (one per agent role), each containing
# a default AgentMemory().model_dump(); when False, agent_memories shall be
# an empty dict.
# ---------------------------------------------------------------------------

from app.orchestrator.state import create_initial_state

# Strategy for generating unique agent role names
_role_name = st.text(
    alphabet=st.characters(whitelist_categories=("L",)),
    min_size=1,
    max_size=20,
)

_agent_type = st.sampled_from(["negotiator", "regulator", "observer"])


@st.composite
def scenario_config_strategy(draw):
    """Generate a valid scenario config with N agents (unique roles)."""
    n_agents = draw(st.integers(min_value=1, max_value=8))

    # Generate N unique role names
    roles = draw(
        st.lists(
            _role_name,
            min_size=n_agents,
            max_size=n_agents,
            unique=True,
        )
    )

    agents = []
    for role in roles:
        agents.append(
            {
                "role": role,
                "name": draw(_safe_text.filter(lambda x: len(x) > 0)),
                "model_id": "gemini-2.5-flash",
                "type": draw(_agent_type),
            }
        )

    # Ensure at least one negotiator so turn_order is non-empty
    if not any(a["type"] == "negotiator" for a in agents):
        agents[0]["type"] = "negotiator"

    config = {
        "id": draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))),
        "agents": agents,
        "negotiation_params": {
            "max_turns": draw(st.integers(min_value=1, max_value=50)),
        },
    }
    return config


@settings(max_examples=100)
@given(
    config=scenario_config_strategy(),
    memory_enabled=st.booleans(),
)
def test_create_initial_state_memory_init(config: dict, memory_enabled: bool):
    """create_initial_state must initialize agent_memories correctly based on the flag.

    When enabled: exactly N keys (one per agent role), each a default AgentMemory dict.
    When disabled: empty dict.
    """
    state = create_initial_state(
        session_id="test-session",
        scenario_config=config,
        structured_memory_enabled=memory_enabled,
    )

    expected_default = AgentMemory().model_dump()
    agent_roles = {a["role"] for a in config["agents"]}

    if memory_enabled:
        # Exactly N keys, one per agent role
        assert set(state["agent_memories"].keys()) == agent_roles
        assert len(state["agent_memories"]) == len(config["agents"])
        # Each value is a default AgentMemory dict
        for role in agent_roles:
            assert state["agent_memories"][role] == expected_default
    else:
        assert state["agent_memories"] == {}

    # Flag must be stored correctly
    assert state["structured_memory_enabled"] == memory_enabled


# ---------------------------------------------------------------------------
# Feature: structured-agent-memory
# Property 9: Full state round-trip with memory
# **Validates: Requirements 9.2**
#
# For any valid NegotiationState containing populated agent_memories,
# converting to NegotiationStateModel via to_pydantic and back via
# from_pydantic shall preserve all agent_memories data and the
# structured_memory_enabled flag without loss.
#
# NOTE: to_pydantic drops scenario_config, stall_diagnosis, custom_prompts,
# and model_overrides. from_pydantic sets them to defaults. This test only
# asserts on the memory-related fields that ARE preserved through the
# round-trip.
# ---------------------------------------------------------------------------

from app.orchestrator.converters import from_pydantic, to_pydantic


@st.composite
def state_with_populated_memories(draw):
    """Generate a valid NegotiationState with populated agent_memories.

    Uses create_initial_state for a structurally valid state, then replaces
    agent_memories with hypothesis-generated AgentMemory data per role.
    """
    config = draw(scenario_config_strategy())
    memory_enabled = draw(st.booleans())

    state = create_initial_state(
        session_id="roundtrip-test",
        scenario_config=config,
        structured_memory_enabled=memory_enabled,
    )

    # When memory is enabled, populate each role's memory with random data
    if memory_enabled:
        for role in state["agent_memories"]:
            mem = draw(agent_memory_strategy())
            state["agent_memories"][role] = mem.model_dump()

    return state


@settings(max_examples=100)
@given(state=state_with_populated_memories())
def test_state_round_trip_with_memory(state):
    """to_pydantic → from_pydantic must preserve agent_memories and structured_memory_enabled.

    **Validates: Requirements 9.2**
    """
    pydantic_model = to_pydantic(state)
    restored = from_pydantic(pydantic_model)

    # The two memory-related fields must survive the round-trip exactly
    assert restored["structured_memory_enabled"] == state["structured_memory_enabled"]
    assert restored["agent_memories"] == state["agent_memories"]


# ---------------------------------------------------------------------------
# Feature: structured-agent-memory
# Property 8: Stall detector equivalence
# **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 8.3**
#
# For any negotiation state where agent_memories data is consistent with the
# history data (i.e., the memory was correctly extracted from the same
# history): detect_stall shall produce identical StallDiagnosis results
# regardless of whether structured_memory_enabled is True or False.
#
# Key consistency constraint: _get_prices_by_role in the history-parsing path
# only includes prices > 0. So agent_memories[role]["my_offers"] must contain
# exactly the positive prices from that role's history entries, in order.
# ---------------------------------------------------------------------------

from app.orchestrator.stall_detector import (
    _MIN_TURNS_FOR_DETECTION,
    detect_stall,
)

# Positive price strategy — history path only keeps prices > 0
_positive_price = st.floats(
    min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False
)


@st.composite
def consistent_negotiation_state(draw):
    """Generate a NegotiationState where agent_memories is consistent with history.

    Builds history entries for exactly 2 negotiator roles, then derives
    agent_memories from that same history so both code paths see identical
    price data. Ensures turn_count >= _MIN_TURNS_FOR_DETECTION so stall
    detection actually runs.
    """
    role_a = "RoleA"
    role_b = "RoleB"
    roles = [role_a, role_b]

    # Generate between _MIN_TURNS_FOR_DETECTION and 12 turns worth of
    # negotiator entries (alternating roles)
    n_entries = draw(
        st.integers(
            min_value=_MIN_TURNS_FOR_DETECTION * 2,
            max_value=12,
        )
    )

    history = []
    prices_by_role: dict[str, list[float]] = {role_a: [], role_b: []}

    for i in range(n_entries):
        role = roles[i % 2]
        price = draw(_positive_price)
        msg = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "Zs")),
                min_size=1,
                max_size=30,
            )
        )
        history.append(
            {
                "role": role,
                "agent_type": "negotiator",
                "content": {
                    "proposed_price": price,
                    "public_message": msg,
                    "inner_thought": "thinking",
                },
            }
        )
        # History path only keeps price > 0 — our prices are always > 0
        prices_by_role[role].append(price)

    # Build agent_memories consistent with history (only positive prices)
    agent_memories = {}
    for role in roles:
        agent_memories[role] = AgentMemory(
            my_offers=list(prices_by_role[role]),
        ).model_dump()

    # turn_count must be >= _MIN_TURNS_FOR_DETECTION
    turn_count = draw(
        st.integers(
            min_value=_MIN_TURNS_FOR_DETECTION,
            max_value=max(_MIN_TURNS_FOR_DETECTION, n_entries),
        )
    )

    agreement_threshold = draw(
        st.floats(min_value=100.0, max_value=1e7, allow_nan=False, allow_infinity=False)
    )

    state = {
        "turn_count": turn_count,
        "current_offer": 0.0,
        "history": history,
        "agreement_threshold": agreement_threshold,
        "agent_memories": agent_memories,
        # structured_memory_enabled will be toggled by the test
    }
    return state


@settings(max_examples=100)
@given(state=consistent_negotiation_state())
def test_stall_detector_equivalence(state: dict):
    """detect_stall must produce identical results with memory enabled vs disabled.

    Given a state where agent_memories is consistent with history (my_offers
    for each role matches the positive prices extracted from history for that
    role), the StallDiagnosis.to_dict() output must be identical regardless
    of the structured_memory_enabled flag.

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 8.3**
    """
    # Run with structured memory DISABLED (history-parsing path)
    state_disabled = {**state, "structured_memory_enabled": False}
    result_disabled = detect_stall(state_disabled)

    # Run with structured memory ENABLED (agent_memories path)
    state_enabled = {**state, "structured_memory_enabled": True}
    result_enabled = detect_stall(state_enabled)

    # Both paths must produce identical diagnosis
    assert result_enabled.to_dict() == result_disabled.to_dict(), (
        f"Stall detector divergence!\n"
        f"  enabled:  {result_enabled.to_dict()}\n"
        f"  disabled: {result_disabled.to_dict()}"
    )
