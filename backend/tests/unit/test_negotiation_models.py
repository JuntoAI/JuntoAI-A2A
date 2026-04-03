"""Property-based tests for StartNegotiationRequest serialization and validation.

Uses hypothesis to verify universal invariants across generated inputs.
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.routers.negotiation import StartNegotiationRequest


# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Non-empty printable text for keys/values
_nonempty_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip())

# Custom prompt values: ≤500 chars
_valid_prompt_value = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs", "P")),
    min_size=0,
    max_size=500,
)

# Dict of role → prompt (≤500 chars each)
_valid_custom_prompts = st.dictionaries(
    keys=_nonempty_text,
    values=_valid_prompt_value,
    min_size=0,
    max_size=5,
)

# Dict of role → model_id
_valid_model_overrides = st.dictionaries(
    keys=_nonempty_text,
    values=_nonempty_text,
    min_size=0,
    max_size=5,
)


# ---------------------------------------------------------------------------
# Feature: agent-advanced-config
# Property 1: StartNegotiationRequest round-trip serialization
# **Validates: Requirements 6.1, 11.1, 13.1**
#
# For any valid StartNegotiationRequest containing custom_prompts (each value
# ≤500 chars) and model_overrides, serializing to JSON and deserializing back
# should produce an equivalent model with all fields preserved.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    email=_nonempty_text,
    scenario_id=_nonempty_text,
    active_toggles=st.lists(_nonempty_text, min_size=0, max_size=5),
    custom_prompts=_valid_custom_prompts,
    model_overrides=_valid_model_overrides,
)
def test_start_negotiation_request_round_trip_serialization(
    email, scenario_id, active_toggles, custom_prompts, model_overrides
):
    """Feature: agent-advanced-config, Property 1: StartNegotiationRequest round-trip serialization"""
    original = StartNegotiationRequest(
        email=email,
        scenario_id=scenario_id,
        active_toggles=active_toggles,
        custom_prompts=custom_prompts,
        model_overrides=model_overrides,
    )

    # Serialize to JSON string, then deserialize back
    json_str = original.model_dump_json()
    restored = StartNegotiationRequest.model_validate_json(json_str)

    assert restored == original
    assert restored.email == original.email
    assert restored.scenario_id == original.scenario_id
    assert restored.active_toggles == original.active_toggles
    assert restored.custom_prompts == original.custom_prompts
    assert restored.model_overrides == original.model_overrides


# Also verify that omitting optional fields defaults to empty dicts
@settings(max_examples=100)
@given(
    email=_nonempty_text,
    scenario_id=_nonempty_text,
)
def test_start_negotiation_request_defaults_round_trip(email, scenario_id):
    """Feature: agent-advanced-config, Property 1: Defaults round-trip — omitted fields default to empty dicts."""
    original = StartNegotiationRequest(email=email, scenario_id=scenario_id)

    assert original.custom_prompts == {}
    assert original.model_overrides == {}
    assert original.active_toggles == []

    json_str = original.model_dump_json()
    restored = StartNegotiationRequest.model_validate_json(json_str)
    assert restored == original


# ---------------------------------------------------------------------------
# Feature: agent-advanced-config
# Property 2: Custom prompt length validation rejects oversized prompts
# **Validates: Requirements 6.2**
#
# For any string longer than 500 characters used as a value in custom_prompts,
# the StartNegotiationRequest Pydantic validator should raise a ValidationError.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    oversized_prompt=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
        min_size=501,
        max_size=2000,
    ),
    role=_nonempty_text,
)
def test_custom_prompt_length_validation_rejects_oversized(oversized_prompt, role):
    """Feature: agent-advanced-config, Property 2: Custom prompt length validation rejects oversized prompts"""
    assert len(oversized_prompt) > 500

    with pytest.raises(ValidationError) as exc_info:
        StartNegotiationRequest(
            email="test@example.com",
            scenario_id="test-scenario",
            custom_prompts={role: oversized_prompt},
        )

    # Verify the error message references the character limit
    error_text = str(exc_info.value)
    assert "500" in error_text


# ---------------------------------------------------------------------------
# Shared imports for P10
# ---------------------------------------------------------------------------
from app.models.negotiation import NegotiationStateModel
from app.orchestrator.state import create_initial_state


# ---------------------------------------------------------------------------
# Minimal scenario config factory for create_initial_state
# ---------------------------------------------------------------------------

def _minimal_scenario_config(agent_roles: list[str] | None = None) -> dict:
    """Build a minimal valid scenario config dict with the given agent roles."""
    if not agent_roles:
        agent_roles = ["Buyer"]
    agents = [
        {
            "role": role,
            "name": f"Agent {role}",
            "model_id": "gemini-3-flash-preview",
            "persona": f"You are {role}.",
            "goals": [f"Goal for {role}"],
        }
        for role in agent_roles
    ]
    return {
        "id": "test-scenario",
        "title": "Test Scenario",
        "agents": agents,
        "negotiation_params": {
            "max_turns": 10,
            "agreement_threshold": 5000.0,
        },
    }


# ---------------------------------------------------------------------------
# Feature: agent-advanced-config
# Property 10: State persistence round-trip
# **Validates: Requirements 6.4, 11.4, 13.2, 13.4**
#
# For any valid custom_prompts and model_overrides dicts, storing them in
# NegotiationStateModel, serializing to a Firestore document dict, and
# deserializing back should produce equivalent values. The create_initial_state
# function should include both fields in the returned NegotiationState when
# provided.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    custom_prompts=_valid_custom_prompts,
    model_overrides=_valid_model_overrides,
)
def test_negotiation_state_model_round_trip_preserves_custom_fields(
    custom_prompts, model_overrides
):
    """Feature: agent-advanced-config, Property 10: State persistence round-trip — NegotiationStateModel serialization"""
    model = NegotiationStateModel(
        session_id="sess-001",
        scenario_id="test-scenario",
        custom_prompts=custom_prompts,
        model_overrides=model_overrides,
    )

    # Simulate Firestore round-trip: model → dict → model
    doc_dict = model.model_dump()
    restored = NegotiationStateModel.model_validate(doc_dict)

    assert restored.custom_prompts == custom_prompts
    assert restored.model_overrides == model_overrides

    # Also verify JSON round-trip (API serialization path)
    json_str = model.model_dump_json()
    restored_json = NegotiationStateModel.model_validate_json(json_str)

    assert restored_json.custom_prompts == custom_prompts
    assert restored_json.model_overrides == model_overrides


@settings(max_examples=100)
@given(
    custom_prompts=_valid_custom_prompts,
    model_overrides=_valid_model_overrides,
)
def test_create_initial_state_includes_custom_fields(
    custom_prompts, model_overrides
):
    """Feature: agent-advanced-config, Property 10: State persistence round-trip — create_initial_state includes both fields"""
    scenario_config = _minimal_scenario_config()

    state = create_initial_state(
        session_id="sess-001",
        scenario_config=scenario_config,
        custom_prompts=custom_prompts,
        model_overrides=model_overrides,
    )

    assert state["custom_prompts"] == custom_prompts
    assert state["model_overrides"] == model_overrides


@settings(max_examples=100)
@given(
    custom_prompts=_valid_custom_prompts,
    model_overrides=_valid_model_overrides,
)
def test_state_persistence_full_round_trip(
    custom_prompts, model_overrides
):
    """Feature: agent-advanced-config, Property 10: State persistence round-trip — full cycle through create_initial_state and NegotiationStateModel"""
    scenario_config = _minimal_scenario_config()

    # Step 1: create_initial_state produces a NegotiationState dict
    state = create_initial_state(
        session_id="sess-001",
        scenario_config=scenario_config,
        custom_prompts=custom_prompts,
        model_overrides=model_overrides,
    )

    # Step 2: Persist via NegotiationStateModel (simulates Firestore write)
    persisted = NegotiationStateModel.model_validate(state)

    # Step 3: Restore from persisted dict (simulates Firestore read)
    doc_dict = persisted.model_dump()
    restored = NegotiationStateModel.model_validate(doc_dict)

    # Step 4: Feed back into create_initial_state (simulates stream_negotiation reload)
    reloaded_state = create_initial_state(
        session_id=restored.session_id,
        scenario_config=scenario_config,
        custom_prompts=restored.custom_prompts,
        model_overrides=restored.model_overrides,
    )

    # Assert full round-trip equivalence
    assert reloaded_state["custom_prompts"] == custom_prompts
    assert reloaded_state["model_overrides"] == model_overrides
