"""Property-based tests for POST /api/v1/negotiation/start endpoint.

Uses hypothesis to verify:
- P3: Invalid model override rejection (HTTP 422)
- P4: Unknown agent role keys are silently ignored (filtered from stored state)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db import get_firestore_client
from app.main import app
from app.orchestrator import model_router
from app.scenarios.models import AgentDefinition, ArenaScenario
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_KNOWN_PREFIXES = sorted(model_router.MODEL_FAMILIES.keys())

# Valid model IDs that exist in the mock scenario
_SCENARIO_MODEL_IDS = ["gemini-3-flash-preview"]

# Model IDs with a known family prefix (pass the family filter but NOT in scenario)
_known_but_absent_model_id = st.sampled_from(_KNOWN_PREFIXES).flatmap(
    lambda prefix: st.from_regex(
        rf"^{prefix}-nonexistent[a-z0-9]{{1,10}}$", fullmatch=True
    )
)

# Model IDs with an unknown family prefix (will never be in available models)
_unknown_family_model_id = st.from_regex(
    r"^xyzfake-[a-z0-9]{1,15}$", fullmatch=True
)

# Any invalid model ID — either unknown family or known family but not in scenario
_invalid_model_id = st.one_of(_known_but_absent_model_id, _unknown_family_model_id)

# Role strings that do NOT match the scenario's agent roles ("Buyer", "Seller")
_unknown_role = st.from_regex(r"^Unknown[A-Z][a-z]{2,10}$", fullmatch=True)

# Short prompt strings (within 500 char limit)
_short_prompt = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
)

# Valid known model ID from the scenario
_valid_model_id = st.just("gemini-3-flash-preview")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SCENARIO_DICT = {
    "id": "test-scenario",
    "name": "Test Scenario",
    "description": "A test scenario",
    "agents": [
        {
            "role": "Buyer", "name": "Alice", "type": "negotiator",
            "persona_prompt": "You are a buyer.", "goals": ["Buy low"],
            "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
            "tone": "assertive", "output_fields": ["offer"],
            "model_id": "gemini-3-flash-preview",
        },
        {
            "role": "Seller", "name": "Bob", "type": "negotiator",
            "persona_prompt": "You are a seller.", "goals": ["Sell high"],
            "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
            "tone": "firm", "output_fields": ["offer"],
            "model_id": "gemini-3-flash-preview",
        },
    ],
    "toggles": [{
        "id": "toggle_1", "label": "Secret info",
        "target_agent_role": "Buyer",
        "hidden_context_payload": {"secret": "value"},
    }],
    "negotiation_params": {
        "max_turns": 10, "agreement_threshold": 1000.0,
        "turn_order": ["Buyer", "Seller"],
    },
    "outcome_receipt": {
        "equivalent_human_time": "~2 weeks",
        "process_label": "Acquisition",
    },
}

_SCENARIO = ArenaScenario(**_VALID_SCENARIO_DICT)
_AGENT_ROLES = {a.role for a in _SCENARIO.agents}  # {"Buyer", "Seller"}


def _build_mock_registry() -> MagicMock:
    """Build a mock ScenarioRegistry with the test scenario."""
    registry = MagicMock(spec=ScenarioRegistry)
    registry.get_scenario.return_value = _SCENARIO
    registry._scenarios = {"test-scenario": _SCENARIO}
    return registry


def _build_mock_db():
    """Build a mock FirestoreSessionClient that captures doc_ref.set calls."""
    db = MagicMock()

    # Track what gets stored
    stored_data = {}
    doc_ref = MagicMock()
    doc_ref.set = AsyncMock(side_effect=lambda data: stored_data.update(data))
    db._collection = MagicMock()
    db._collection.document = MagicMock(return_value=doc_ref)

    # Mock waitlist lookup for token balance
    waitlist_doc = MagicMock()
    waitlist_doc.exists = True
    waitlist_doc.to_dict.return_value = {"token_balance": 100}
    waitlist_ref = MagicMock()
    waitlist_ref.get = AsyncMock(return_value=waitlist_doc)
    db._db = MagicMock()
    db._db.collection.return_value = MagicMock()
    db._db.collection.return_value.document.return_value = waitlist_ref

    return db, stored_data



# ---------------------------------------------------------------------------
# Feature: agent-advanced-config
# Property 3: Invalid model override rejection
# **Validates: Requirements 11.2**
#
# For any model_id string that is not present in the available models list
# (derived from loaded scenarios filtered by MODEL_FAMILIES), the backend
# should return HTTP 422 when that model_id is used as a value in
# model_overrides.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    invalid_mid=_invalid_model_id,
    role=st.sampled_from(sorted(_AGENT_ROLES)),
)
@pytest.mark.asyncio
async def test_invalid_model_override_returns_422(invalid_mid, role):
    """Feature: agent-advanced-config, Property 3: Invalid model override rejection"""
    mock_registry = _build_mock_registry()
    mock_db, _ = _build_mock_db()

    app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
    app.dependency_overrides[get_firestore_client] = lambda: mock_db

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/negotiation/start",
                json={
                    "email": "test@example.com",
                    "scenario_id": "test-scenario",
                    "active_toggles": [],
                    "model_overrides": {role: invalid_mid},
                },
            )

        # Core property: invalid model_id → HTTP 422
        assert resp.status_code == 422, (
            f"Expected 422 for invalid model_id '{invalid_mid}', "
            f"got {resp.status_code}: {resp.text}"
        )

        # Response should mention the invalid model_id
        body = resp.json()
        assert "detail" in body
        assert invalid_mid in body["detail"]
    finally:
        app.dependency_overrides.pop(get_scenario_registry, None)
        app.dependency_overrides.pop(get_firestore_client, None)


# ---------------------------------------------------------------------------
# Feature: agent-advanced-config
# Property 4: Unknown agent role keys are silently ignored
# **Validates: Requirements 6.3, 11.3**
#
# For any custom_prompts or model_overrides key that does not match any
# agent role in the selected scenario, the backend should process the
# request successfully, ignoring the unrecognized keys — the stored state
# should contain only keys matching valid agent roles.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    unknown_roles=st.lists(_unknown_role, min_size=1, max_size=5, unique=True),
    prompts=st.lists(_short_prompt, min_size=1, max_size=5),
)
@pytest.mark.asyncio
async def test_unknown_role_keys_filtered_from_stored_state(unknown_roles, prompts):
    """Feature: agent-advanced-config, Property 4: Unknown agent role keys are silently ignored"""
    mock_registry = _build_mock_registry()
    mock_db, stored_data = _build_mock_db()

    app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
    app.dependency_overrides[get_firestore_client] = lambda: mock_db

    try:
        # Build custom_prompts and model_overrides with unknown role keys
        # Pad prompts list to match unknown_roles length
        padded_prompts = (prompts * ((len(unknown_roles) // len(prompts)) + 1))[:len(unknown_roles)]
        unknown_custom_prompts = dict(zip(unknown_roles, padded_prompts))
        unknown_model_overrides = {r: "gemini-3-flash-preview" for r in unknown_roles}

        # Also include one valid role to ensure the request succeeds
        custom_prompts = {**unknown_custom_prompts, "Buyer": "Be aggressive"}
        model_overrides = {**unknown_model_overrides, "Buyer": "gemini-3-flash-preview"}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/negotiation/start",
                json={
                    "email": "test@example.com",
                    "scenario_id": "test-scenario",
                    "active_toggles": [],
                    "custom_prompts": custom_prompts,
                    "model_overrides": model_overrides,
                },
            )

        # Request should succeed (unknown keys silently ignored)
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )

        # Core property: stored state should only contain valid agent role keys
        stored_custom_prompts = stored_data.get("custom_prompts", {})
        stored_model_overrides = stored_data.get("model_overrides", {})

        # No unknown role key should appear in stored state
        for unknown_role in unknown_roles:
            assert unknown_role not in stored_custom_prompts, (
                f"Unknown role '{unknown_role}' should not be in stored custom_prompts"
            )
            assert unknown_role not in stored_model_overrides, (
                f"Unknown role '{unknown_role}' should not be in stored model_overrides"
            )

        # All stored keys must be valid agent roles
        for key in stored_custom_prompts:
            assert key in _AGENT_ROLES, (
                f"Stored custom_prompts key '{key}' is not a valid agent role"
            )
        for key in stored_model_overrides:
            assert key in _AGENT_ROLES, (
                f"Stored model_overrides key '{key}' is not a valid agent role"
            )

        # The valid role we included should be present
        assert stored_custom_prompts.get("Buyer") == "Be aggressive"
        assert stored_model_overrides.get("Buyer") == "gemini-3-flash-preview"
    finally:
        app.dependency_overrides.pop(get_scenario_registry, None)
        app.dependency_overrides.pop(get_firestore_client, None)
