"""Property-based tests for the Scenario Config Engine.

Uses hypothesis to verify universal invariants across generated inputs.
"""

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.scenarios.exceptions import ScenarioParseError
from app.scenarios.loader import load_scenario_from_file


# ---------------------------------------------------------------------------
# Feature: 040_a2a-scenario-config-engine
# Property 8: Non-JSON content raises ScenarioParseError
# **Validates: Requirements 2.4**
#
# For any string that is not valid JSON, writing it to a file and calling
# load_scenario_from_file() shall raise a ScenarioParseError containing
# the file path.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(content=st.text(min_size=1))
def test_non_json_content_raises_parse_error(content, tmp_path_factory):
    """Non-JSON file content must always raise ScenarioParseError with file path."""
    # Filter out strings that happen to be valid JSON
    try:
        json.loads(content)
        assume(False)
    except (json.JSONDecodeError, ValueError):
        pass

    tmp_dir = tmp_path_factory.mktemp("prop8")
    f = tmp_dir / "bad.scenario.json"
    f.write_text(content, encoding="utf-8")

    try:
        load_scenario_from_file(f)
        assert False, "Expected ScenarioParseError"
    except ScenarioParseError as e:
        assert str(f) in str(e)

# ---------------------------------------------------------------------------
# Imports for Property 7
# ---------------------------------------------------------------------------
from app.scenarios.exceptions import ScenarioNotFoundError
from app.scenarios.registry import ScenarioRegistry


# ---------------------------------------------------------------------------
# Helpers for Property 7
# ---------------------------------------------------------------------------

def _build_scenario_dict(scenario_id: str) -> dict:
    """Build a minimal valid ArenaScenario dict with the given id."""
    return {
        "id": scenario_id,
        "name": f"Scenario {scenario_id}",
        "description": f"Description for {scenario_id}",
        "agents": [
            {
                "role": "Buyer",
                "name": "Alice",
                "type": "negotiator",
                "persona_prompt": "You are a buyer.",
                "goals": ["Buy low"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "assertive",
                "output_fields": ["offer"],
                "model_id": "gemini-3-flash-preview",
            },
            {
                "role": "Seller",
                "name": "Bob",
                "type": "negotiator",
                "persona_prompt": "You are a seller.",
                "goals": ["Sell high"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "firm",
                "output_fields": ["offer"],
                "model_id": "gemini-3-flash-preview",
            },
        ],
        "toggles": [
            {
                "id": "toggle_1",
                "label": "Secret info",
                "target_agent_role": "Buyer",
                "hidden_context_payload": {"secret": "value"},
            }
        ],
        "negotiation_params": {
            "max_turns": 10,
            "agreement_threshold": 1000.0,
            "turn_order": ["Buyer", "Seller"],
        },
        "outcome_receipt": {
            "equivalent_human_time": "~2 weeks",
            "process_label": "Negotiation",
        },
    }


# ---------------------------------------------------------------------------
# Feature: 040_a2a-scenario-config-engine
# Property 7: Registry get/list consistency
# **Validates: Requirements 4.4, 4.5, 4.6**
#
# For any set of valid ArenaScenario objects registered in a ScenarioRegistry:
# (a) list_scenarios() returns exactly one entry per registered scenario
#     with matching id, name, and description,
# (b) get_scenario(id) returns the original ArenaScenario object for each id,
# (c) get_scenario(unknown_id) raises ScenarioNotFoundError.
# ---------------------------------------------------------------------------

# Strategy: unique alphanumeric IDs (letters + digits), 1-5 items
_scenario_ids_strategy = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=20,
    ),
    min_size=1,
    max_size=5,
    unique=True,
)


@settings(max_examples=100)
@given(scenario_ids=_scenario_ids_strategy)
def test_registry_get_list_consistency(scenario_ids, tmp_path_factory):
    """Registry list/get must be consistent with the loaded scenario files."""
    tmp_dir = tmp_path_factory.mktemp("prop7")

    # Write each scenario to a temp file
    for sid in scenario_ids:
        data = _build_scenario_dict(sid)
        fpath = tmp_dir / f"{sid}.scenario.json"
        fpath.write_text(json.dumps(data), encoding="utf-8")

    # Create registry from the temp directory
    registry = ScenarioRegistry(scenarios_dir=str(tmp_dir))

    # (a) list_scenarios() returns exactly the right ids with correct fields
    listed = registry.list_scenarios()
    listed_ids = {entry["id"] for entry in listed}
    assert listed_ids == set(scenario_ids)

    for entry in listed:
        assert set(entry.keys()) == {"id", "name", "description", "difficulty", "category", "tags", "available"}
        sid = entry["id"]
        assert entry["name"] == f"Scenario {sid}"
        assert entry["description"] == f"Description for {sid}"

    # (b) get_scenario(id) returns the correct ArenaScenario for each id
    for sid in scenario_ids:
        scenario = registry.get_scenario(sid)
        assert scenario.id == sid
        assert scenario.name == f"Scenario {sid}"
        assert scenario.description == f"Description for {sid}"
        assert len(scenario.agents) == 2
        assert len(scenario.toggles) == 1

    # (c) get_scenario with unknown id raises ScenarioNotFoundError
    try:
        registry.get_scenario("nonexistent_id_xyz")
        assert False, "Expected ScenarioNotFoundError"
    except ScenarioNotFoundError as e:
        assert e.scenario_id == "nonexistent_id_xyz"


# ---------------------------------------------------------------------------
# Imports for Properties 5 and 6
# ---------------------------------------------------------------------------
from app.scenarios.exceptions import InvalidToggleError
from app.scenarios.models import ArenaScenario
from app.scenarios.toggle_injector import build_hidden_context


# ---------------------------------------------------------------------------
# Helpers for Properties 5 and 6
# ---------------------------------------------------------------------------

def _make_agent(role: str, agent_type: str = "negotiator") -> dict:
    """Build a minimal valid AgentDefinition dict."""
    return {
        "role": role,
        "name": f"Agent_{role}",
        "type": agent_type,
        "persona_prompt": f"You are {role}.",
        "goals": [f"Goal for {role}"],
        "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
        "tone": "neutral",
        "output_fields": ["offer"],
        "model_id": "gemini-3-flash-preview",
    }


def _make_toggle(toggle_id: str, target_role: str, payload: dict) -> dict:
    """Build a minimal valid ToggleDefinition dict."""
    return {
        "id": toggle_id,
        "label": f"Toggle {toggle_id}",
        "target_agent_role": target_role,
        "hidden_context_payload": payload,
    }


# Fixed scenario with 3 agents and 5 toggles (some sharing roles, some unique)
_PROP5_AGENTS = [
    _make_agent("Alpha", "negotiator"),
    _make_agent("Beta", "negotiator"),
    _make_agent("Gamma", "regulator"),
]

_PROP5_TOGGLES = [
    _make_toggle("t_alpha_1", "Alpha", {"intel": "secret_a1"}),
    _make_toggle("t_alpha_2", "Alpha", {"leverage": "patent"}),
    _make_toggle("t_beta_1", "Beta", {"pressure": "deadline"}),
    _make_toggle("t_gamma_1", "Gamma", {"strictness": "max"}),
    _make_toggle("t_gamma_2", "Gamma", {"audit": True}),
]

_PROP5_SCENARIO_DICT = {
    "id": "prop5-scenario",
    "name": "Property 5 Test Scenario",
    "description": "Scenario for toggle injection property test",
    "agents": _PROP5_AGENTS,
    "toggles": _PROP5_TOGGLES,
    "negotiation_params": {
        "max_turns": 10,
        "agreement_threshold": 1000.0,
        "turn_order": ["Alpha", "Beta", "Gamma"],
    },
    "outcome_receipt": {
        "equivalent_human_time": "~1 week",
        "process_label": "Property Test",
    },
}

_PROP5_SCENARIO = ArenaScenario.model_validate(_PROP5_SCENARIO_DICT)
_PROP5_TOGGLE_IDS = [t.id for t in _PROP5_SCENARIO.toggles]


# ---------------------------------------------------------------------------
# Feature: 040_a2a-scenario-config-engine
# Property 5: Toggle injection produces correct hidden context
# **Validates: Requirements 5.1, 5.2, 5.3, 10.3**
#
# For any valid ArenaScenario and any subset of its toggle identifiers,
# build_hidden_context(scenario, toggle_ids) shall return a dictionary where:
# (a) every key is a target_agent_role from an activated toggle,
# (b) the value for each role key contains all key-value pairs from the
#     hidden_context_payload of every activated toggle targeting that role,
# (c) no keys from non-activated toggles appear.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    active_subset=st.lists(
        st.sampled_from(_PROP5_TOGGLE_IDS),
        min_size=0,
        max_size=len(_PROP5_TOGGLE_IDS),
        unique=True,
    )
)
def test_toggle_injection_produces_correct_hidden_context(active_subset):
    """Toggle injection must produce exactly the right role keys with merged payloads."""
    scenario = _PROP5_SCENARIO
    toggle_map = {t.id: t for t in scenario.toggles}

    result = build_hidden_context(scenario, active_subset)

    # Build expected output independently
    expected: dict[str, dict] = {}
    for tid in active_subset:
        toggle = toggle_map[tid]
        role = toggle.target_agent_role
        if role not in expected:
            expected[role] = {}
        expected[role].update(toggle.hidden_context_payload)

    # (a) Every key in result is a target_agent_role from an activated toggle
    activated_roles = {toggle_map[tid].target_agent_role for tid in active_subset}
    assert set(result.keys()) == activated_roles, (
        f"Result keys {set(result.keys())} != activated roles {activated_roles}"
    )

    # (b) Values contain all merged payloads
    for role, payload in expected.items():
        for key, value in payload.items():
            assert key in result[role], (
                f"Missing key '{key}' in result['{role}']"
            )
            assert result[role][key] == value, (
                f"result['{role}']['{key}'] = {result[role][key]} != expected {value}"
            )

    # (c) No keys from non-activated toggles appear
    non_activated_ids = set(_PROP5_TOGGLE_IDS) - set(active_subset)
    non_activated_only_roles = set()
    for tid in non_activated_ids:
        role = toggle_map[tid].target_agent_role
        if role not in activated_roles:
            non_activated_only_roles.add(role)
    for role in non_activated_only_roles:
        assert role not in result, (
            f"Role '{role}' from non-activated toggle should not appear in result"
        )


# ---------------------------------------------------------------------------
# Feature: 040_a2a-scenario-config-engine
# Property 6: Invalid toggle identifiers raise InvalidToggleError
# **Validates: Requirements 5.6**
#
# For any valid ArenaScenario and any toggle identifier string that does not
# match any ToggleDefinition.id in the scenario, build_hidden_context(scenario,
# [invalid_id]) shall raise an InvalidToggleError containing the invalid
# toggle id and the scenario id.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(invalid_id=st.text(min_size=1, max_size=50))
def test_invalid_toggle_identifiers_raise_error(invalid_id):
    """Any toggle id not in the scenario must raise InvalidToggleError."""
    scenario = _PROP5_SCENARIO
    valid_ids = {t.id for t in scenario.toggles}

    # Skip if the random string happens to match a valid toggle id
    assume(invalid_id not in valid_ids)

    try:
        build_hidden_context(scenario, [invalid_id])
        assert False, f"Expected InvalidToggleError for toggle id '{invalid_id}'"
    except InvalidToggleError as e:
        assert e.toggle_id == invalid_id
        assert e.scenario_id == scenario.id


# ---------------------------------------------------------------------------
# Imports for Properties 1, 2, 3, 4
# ---------------------------------------------------------------------------
from pydantic import ValidationError

from app.scenarios.loader import load_scenario_from_dict
from app.scenarios.pretty_printer import pretty_print


# ---------------------------------------------------------------------------
# Hypothesis strategy for generating random valid ArenaScenario instances
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip())


@st.composite
def arena_scenario_strategy(draw):
    """Generate a random valid ArenaScenario instance."""
    # Generate 2-4 unique roles
    num_agents = draw(st.integers(min_value=2, max_value=4))
    roles = draw(
        st.lists(_safe_text, min_size=num_agents, max_size=num_agents, unique=True)
    )

    # Ensure at least one negotiator
    agent_types = draw(
        st.lists(
            st.sampled_from(["negotiator", "regulator", "observer"]),
            min_size=num_agents,
            max_size=num_agents,
        )
    )
    agent_types[0] = "negotiator"

    agents = []
    for role, atype in zip(roles, agent_types):
        min_val = draw(
            st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False)
        )
        max_val = draw(
            st.floats(
                min_value=min_val, max_value=min_val + 1000,
                allow_nan=False, allow_infinity=False,
            )
        )
        target = draw(
            st.floats(
                min_value=min_val, max_value=max_val,
                allow_nan=False, allow_infinity=False,
            )
        )
        agents.append(
            {
                "role": role,
                "name": f"Agent_{role}",
                "type": atype,
                "persona_prompt": f"You are {role}.",
                "goals": [f"Goal for {role}"],
                "budget": {"min": min_val, "max": max_val, "target": target},
                "tone": "neutral",
                "output_fields": ["offer"],
                "model_id": "gemini-3-flash-preview",
            }
        )

    # Generate 1-3 toggles targeting valid roles
    num_toggles = draw(st.integers(min_value=1, max_value=3))
    toggles = []
    for i in range(num_toggles):
        target_role = draw(st.sampled_from(roles))
        toggles.append(
            {
                "id": f"toggle_{i}",
                "label": f"Toggle {i}",
                "target_agent_role": target_role,
                "hidden_context_payload": {"key": f"value_{i}"},
            }
        )

    # turn_order references valid roles
    turn_order = draw(
        st.lists(st.sampled_from(roles), min_size=1, max_size=len(roles) * 2)
    )

    return ArenaScenario.model_validate(
        {
            "id": draw(_safe_text),
            "name": draw(_safe_text),
            "description": draw(_safe_text),
            "agents": agents,
            "toggles": toggles,
            "negotiation_params": {
                "max_turns": draw(st.integers(min_value=1, max_value=100)),
                "agreement_threshold": draw(
                    st.floats(
                        min_value=0.01, max_value=1e6,
                        allow_nan=False, allow_infinity=False,
                    )
                ),
                "turn_order": turn_order,
            },
            "outcome_receipt": {
                "equivalent_human_time": draw(_safe_text),
                "process_label": draw(_safe_text),
            },
        }
    )


# ---------------------------------------------------------------------------
# Feature: 040_a2a-scenario-config-engine
# Property 1: ArenaScenario round-trip serialization
# **Validates: Requirements 3.1, 3.2, 3.3**
#
# For any valid ArenaScenario object, serializing it via pretty_print() and
# then parsing the resulting JSON string back via
# load_scenario_from_dict(json.loads(output)) shall produce an ArenaScenario
# object equal to the original.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(scenario=arena_scenario_strategy())
def test_arena_scenario_round_trip_serialization(scenario):
    """Serializing and deserializing any valid ArenaScenario must produce an equal object."""
    json_str = pretty_print(scenario)
    parsed = json.loads(json_str)
    restored = load_scenario_from_dict(parsed)
    assert restored == scenario


# ---------------------------------------------------------------------------
# Feature: 040_a2a-scenario-config-engine
# Property 2: Schema rejects scenarios with missing required fields
# **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.2**
#
# For any valid ArenaScenario dict, removing any single required top-level
# field shall cause ArenaScenario.model_validate() to raise a ValidationError.
# ---------------------------------------------------------------------------

_REQUIRED_TOP_LEVEL_FIELDS = [
    "id", "name", "description", "agents", "toggles",
    "negotiation_params", "outcome_receipt",
]


@settings(max_examples=100)
@given(
    scenario=arena_scenario_strategy(),
    field=st.sampled_from(_REQUIRED_TOP_LEVEL_FIELDS),
)
def test_schema_rejects_missing_required_fields(scenario, field):
    """Removing any required top-level field must raise ValidationError."""
    data = json.loads(scenario.model_dump_json())
    del data[field]
    with pytest.raises(ValidationError):
        ArenaScenario.model_validate(data)


# ---------------------------------------------------------------------------
# Feature: 040_a2a-scenario-config-engine
# Property 3: Cross-reference validation rejects invalid toggle targets
# **Validates: Requirements 1.9, 2.5**
#
# For any valid ArenaScenario dict, if any ToggleDefinition.target_agent_role
# is changed to a string that does not match any AgentDefinition.role in the
# same scenario, ArenaScenario.model_validate() shall raise a ValidationError.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    scenario=arena_scenario_strategy(),
    bad_role=_safe_text,
)
def test_cross_reference_rejects_invalid_toggle_targets(scenario, bad_role):
    """Replacing a toggle target_agent_role with an invalid role must raise ValidationError."""
    agent_roles = {a.role for a in scenario.agents}
    assume(bad_role not in agent_roles)

    data = json.loads(scenario.model_dump_json())
    # Replace the first toggle's target_agent_role with the invalid role
    data["toggles"][0]["target_agent_role"] = bad_role

    with pytest.raises(ValidationError):
        ArenaScenario.model_validate(data)


# ---------------------------------------------------------------------------
# Feature: 040_a2a-scenario-config-engine
# Property 4: Unique agent roles constraint
# **Validates: Requirements 2.6**
#
# For any scenario dict containing two or more AgentDefinition objects with
# the same role value, ArenaScenario.model_validate() shall raise a
# ValidationError.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(scenario=arena_scenario_strategy())
def test_duplicate_agent_roles_rejected(scenario):
    """Duplicating an agent role must raise ValidationError."""
    data = json.loads(scenario.model_dump_json())

    # Duplicate the first agent's role onto the second agent
    data["agents"][1]["role"] = data["agents"][0]["role"]

    with pytest.raises(ValidationError):
        ArenaScenario.model_validate(data)
