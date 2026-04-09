"""Property-based tests for the PUT /builder/scenarios/{id} validation gate.

# Feature: 320_scenario-management, Property 4: Validation gate accepts valid scenarios and rejects invalid ones

For any dict that passes ArenaScenario.model_validate(), the PUT endpoint
should accept it with 200. For any dict that fails ArenaScenario.model_validate(),
the PUT endpoint should reject it with 422 and return a non-empty list of
validation errors. Additionally, scenario names must be between 1 and 100
characters — names outside this range should be rejected.

**Validates: Requirements 3.2, 4.3, 4.4, 5.2, 5.4**
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.builder.scenario_store import SQLiteCustomScenarioStore
from app.db import get_custom_scenario_store
from app.main import app
from app.orchestrator.available_models import VALID_MODEL_IDS
from app.scenarios.models import ArenaScenario

# ---------------------------------------------------------------------------
# Strategies — reuse patterns from test_scenario_update.py
# ---------------------------------------------------------------------------

_model_ids = st.sampled_from(sorted(VALID_MODEL_IDS))
_tones = st.sampled_from(["assertive", "firm", "friendly", "aggressive", "calm"])
_difficulties = st.sampled_from(["beginner", "intermediate", "advanced", "fun"])
_price_units = st.sampled_from(["total", "hourly", "monthly", "annual"])
_value_formats = st.sampled_from(["currency", "time_from_22", "percent", "number"])
_safe_text = st.characters(whitelist_categories=("L", "N", "Zs"))


@st.composite
def valid_budget(draw):
    a = draw(st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
    b = draw(st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
    lo, hi = min(a, b), max(a, b)
    target = draw(st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
    return {"min": lo, "max": hi, "target": target}


@st.composite
def valid_agent(draw, role: str, agent_type: str):
    return {
        "role": role,
        "name": draw(st.text(min_size=1, max_size=20, alphabet=_safe_text)),
        "type": agent_type,
        "persona_prompt": draw(st.text(min_size=1, max_size=50, alphabet=_safe_text)),
        "goals": [draw(st.text(min_size=1, max_size=30, alphabet=_safe_text))],
        "budget": draw(valid_budget()),
        "tone": draw(_tones),
        "output_fields": ["offer"],
        "model_id": draw(_model_ids),
    }


@st.composite
def valid_scenario_dict(draw):
    """Generate a valid ArenaScenario dict (name 1-100 chars)."""
    buyer = draw(valid_agent("Buyer", "negotiator"))
    seller = draw(valid_agent("Seller", "negotiator"))
    return {
        "id": draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N")))),
        "name": draw(st.text(min_size=1, max_size=100, alphabet=_safe_text)),
        "description": draw(st.text(min_size=1, max_size=100, alphabet=_safe_text)),
        "difficulty": draw(_difficulties),
        "agents": [buyer, seller],
        "toggles": [{
            "id": "toggle_1",
            "label": "Secret info",
            "target_agent_role": "Buyer",
            "hidden_context_payload": {"secret": "value"},
        }],
        "negotiation_params": {
            "max_turns": draw(st.integers(min_value=1, max_value=50)),
            "agreement_threshold": draw(st.floats(min_value=0.01, max_value=1e8, allow_nan=False, allow_infinity=False)),
            "turn_order": ["Buyer", "Seller"],
            "price_unit": draw(_price_units),
            "value_format": draw(_value_formats),
        },
        "outcome_receipt": {
            "equivalent_human_time": draw(st.text(min_size=1, max_size=30, alphabet=_safe_text)),
            "process_label": draw(st.text(min_size=1, max_size=30, alphabet=_safe_text)),
        },
    }


@st.composite
def invalid_scenario_dict(draw):
    """Generate a dict that will fail ArenaScenario validation.

    Picks one of several corruption strategies to ensure Pydantic rejects it.
    """
    strategy = draw(st.sampled_from([
        "missing_name",
        "empty_name",
        "missing_agents",
        "no_negotiator",
        "bad_model_id",
        "missing_toggles",
        "bad_turn_order",
        "missing_description",
        "negative_max_turns",
    ]))

    # Start from a valid base and corrupt it
    base = draw(valid_scenario_dict())

    if strategy == "missing_name":
        del base["name"]
    elif strategy == "empty_name":
        base["name"] = ""
    elif strategy == "missing_agents":
        base["agents"] = []
    elif strategy == "no_negotiator":
        # Make all agents observers — violates "at least 1 negotiator"
        for agent in base["agents"]:
            agent["type"] = "observer"
    elif strategy == "bad_model_id":
        base["agents"][0]["model_id"] = "nonexistent-model-9999"
    elif strategy == "missing_toggles":
        base["toggles"] = []
    elif strategy == "bad_turn_order":
        base["negotiation_params"]["turn_order"] = ["NonExistentRole"]
    elif strategy == "missing_description":
        del base["description"]
    elif strategy == "negative_max_turns":
        base["negotiation_params"]["max_turns"] = 0

    return base


# ---------------------------------------------------------------------------
# Feature: 320_scenario-management
# Property 4: Validation gate accepts valid scenarios and rejects invalid ones
# **Validates: Requirements 3.2, 4.3, 4.4, 5.2, 5.4**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(scenario=valid_scenario_dict())
async def test_valid_scenario_accepted(scenario: dict):
    """Valid ArenaScenario dicts should be accepted by the PUT endpoint with 200."""

    # Double-check the generated dict actually passes Pydantic validation
    ArenaScenario.model_validate(scenario)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "prop4_valid.db")
        store = SQLiteCustomScenarioStore(db_path)

        # Seed a scenario so we have a scenario_id to PUT against
        seed_scenario = ArenaScenario.model_validate(scenario)
        email = "prop4@test.com"
        scenario_id = await store.save(email, seed_scenario)

        app.dependency_overrides[get_custom_scenario_store] = lambda: store
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.put(
                    f"/api/v1/builder/scenarios/{scenario_id}",
                    params={"email": email},
                    json={"scenario_json": scenario},
                )
            assert resp.status_code == 200, (
                f"Expected 200 for valid scenario, got {resp.status_code}: {resp.text}"
            )
            body = resp.json()
            assert "scenario_id" in body
            assert "name" in body
        finally:
            app.dependency_overrides.pop(get_custom_scenario_store, None)


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(scenario=invalid_scenario_dict())
async def test_invalid_scenario_rejected(scenario: dict):
    """Invalid scenario dicts should be rejected with 422 and a non-empty errors list."""

    # Confirm the generated dict actually fails Pydantic validation
    try:
        ArenaScenario.model_validate(scenario)
        # If validation passes, this particular mutation didn't break it — skip
        pytest.skip("Generated dict unexpectedly passed validation")
    except Exception:
        pass  # Good — it's invalid as expected

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "prop4_invalid.db")
        store = SQLiteCustomScenarioStore(db_path)

        # Seed a valid scenario so we have a scenario_id to PUT against
        seed = {
            "id": "seed",
            "name": "Seed Scenario",
            "description": "A seed",
            "agents": [
                {
                    "role": "Buyer", "name": "A", "type": "negotiator",
                    "persona_prompt": "Buy", "goals": ["Buy"],
                    "budget": {"min": 0, "max": 100, "target": 50},
                    "tone": "firm", "output_fields": ["offer"],
                    "model_id": sorted(VALID_MODEL_IDS)[0],
                },
                {
                    "role": "Seller", "name": "B", "type": "negotiator",
                    "persona_prompt": "Sell", "goals": ["Sell"],
                    "budget": {"min": 0, "max": 100, "target": 50},
                    "tone": "firm", "output_fields": ["offer"],
                    "model_id": sorted(VALID_MODEL_IDS)[0],
                },
            ],
            "toggles": [{
                "id": "t1", "label": "Info",
                "target_agent_role": "Buyer",
                "hidden_context_payload": {"k": "v"},
            }],
            "negotiation_params": {
                "max_turns": 5, "agreement_threshold": 100,
                "turn_order": ["Buyer", "Seller"],
            },
            "outcome_receipt": {
                "equivalent_human_time": "1h",
                "process_label": "Test",
            },
        }
        seed_model = ArenaScenario.model_validate(seed)
        email = "prop4@test.com"
        scenario_id = await store.save(email, seed_model)

        app.dependency_overrides[get_custom_scenario_store] = lambda: store
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.put(
                    f"/api/v1/builder/scenarios/{scenario_id}",
                    params={"email": email},
                    json={"scenario_json": scenario},
                )
            assert resp.status_code == 422, (
                f"Expected 422 for invalid scenario, got {resp.status_code}: {resp.text}"
            )
            body = resp.json()
            assert "errors" in body, f"Response missing 'errors' key: {body}"
            assert len(body["errors"]) > 0, f"Errors list should be non-empty: {body}"
        finally:
            app.dependency_overrides.pop(get_custom_scenario_store, None)
