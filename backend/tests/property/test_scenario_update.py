"""Property-based tests for SQLiteCustomScenarioStore update round-trip.

# Feature: 320_scenario-management, Property 3: Scenario update round-trip preserves data

For any valid ArenaScenario dict, if it is submitted via store.update() for an
existing custom scenario, then retrieving that scenario via store.get() should
return a scenario_json that is equivalent to the submitted dict, and the
updated_at timestamp should be >= the previous updated_at.

**Validates: Requirements 3.1, 4.6, 5.3, 5.6**
"""

from __future__ import annotations

import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.builder.scenario_store import SQLiteCustomScenarioStore
from app.orchestrator.available_models import VALID_MODEL_IDS
from app.scenarios.models import ArenaScenario

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_model_ids = st.sampled_from(sorted(VALID_MODEL_IDS))
_agent_types = st.sampled_from(["negotiator", "regulator", "observer"])
_tones = st.sampled_from(["assertive", "firm", "friendly", "aggressive", "calm"])
_difficulties = st.sampled_from(["beginner", "intermediate", "advanced", "fun"])
_price_units = st.sampled_from(["total", "hourly", "monthly", "annual"])
_value_formats = st.sampled_from(["currency", "time_from_22", "percent", "number"])


@st.composite
def valid_budget(draw):
    """Generate a valid Budget dict where min <= max."""
    a = draw(st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
    b = draw(st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
    lo, hi = min(a, b), max(a, b)
    target = draw(st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
    return {"min": lo, "max": hi, "target": target}


@st.composite
def valid_agent(draw, role: str, agent_type: str):
    """Generate a valid AgentDefinition dict for a given role and type."""
    return {
        "role": role,
        "name": draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N", "Zs")))),
        "type": agent_type,
        "persona_prompt": draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Zs")))),
        "goals": [draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Zs"))))],
        "budget": draw(valid_budget()),
        "tone": draw(_tones),
        "output_fields": ["offer"],
        "model_id": draw(_model_ids),
    }


@st.composite
def valid_scenario_dict(draw):
    """Generate a valid ArenaScenario dict that passes Pydantic validation.

    Always produces exactly 2 negotiator agents (Buyer, Seller) to satisfy
    cross-reference constraints (turn_order, toggle targets, >=1 negotiator).
    """
    buyer = draw(valid_agent("Buyer", "negotiator"))
    seller = draw(valid_agent("Seller", "negotiator"))
    agents = [buyer, seller]

    scenario_name = draw(st.text(min_size=1, max_size=80, alphabet=st.characters(whitelist_categories=("L", "N", "Zs"))))
    description = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "Zs"))))

    return {
        "id": draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N")))),
        "name": scenario_name,
        "description": description,
        "difficulty": draw(_difficulties),
        "agents": agents,
        "toggles": [
            {
                "id": "toggle_1",
                "label": "Secret info",
                "target_agent_role": "Buyer",
                "hidden_context_payload": {"secret": "value"},
            }
        ],
        "negotiation_params": {
            "max_turns": draw(st.integers(min_value=1, max_value=50)),
            "agreement_threshold": draw(st.floats(min_value=0.01, max_value=1e8, allow_nan=False, allow_infinity=False)),
            "turn_order": ["Buyer", "Seller"],
            "price_unit": draw(_price_units),
            "value_format": draw(_value_formats),
        },
        "outcome_receipt": {
            "equivalent_human_time": draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Zs")))),
            "process_label": draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Zs")))),
        },
    }


# ---------------------------------------------------------------------------
# Feature: 320_scenario-management
# Property 3: Scenario update round-trip preserves data
# **Validates: Requirements 3.1, 4.6, 5.3, 5.6**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    initial_scenario=valid_scenario_dict(),
    updated_scenario=valid_scenario_dict(),
)
async def test_scenario_update_round_trip_preserves_data(
    initial_scenario: dict,
    updated_scenario: dict,
):
    """Saving a scenario, updating it, then getting it back should return
    the updated scenario_json exactly, and updated_at should be >= the
    previous updated_at."""

    # Validate both dicts pass ArenaScenario validation
    initial_model = ArenaScenario(**initial_scenario)
    updated_model = ArenaScenario(**updated_scenario)

    email = "test@example.com"

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "prop3.db")
        store = SQLiteCustomScenarioStore(db_path)

        # 1. Save the initial scenario
        scenario_id = await store.save(email, initial_model)

        # 2. Get the saved scenario and record its updated_at
        saved = await store.get(email, scenario_id)
        assert saved is not None
        previous_updated_at = saved["updated_at"]

        # Small sleep to ensure timestamp monotonicity is observable
        time.sleep(0.01)

        # 3. Update with the new scenario dict
        updated_dict = updated_model.model_dump()
        result = await store.update(email, scenario_id, updated_dict)
        assert result is True

        # 4. Get the updated scenario
        retrieved = await store.get(email, scenario_id)
        assert retrieved is not None

        # 5. Verify round-trip equivalence: retrieved scenario_json == submitted dict
        assert retrieved["scenario_json"] == updated_dict, (
            f"Round-trip mismatch.\n"
            f"  Submitted: {updated_dict}\n"
            f"  Retrieved: {retrieved['scenario_json']}"
        )

        # 6. Verify updated_at monotonicity
        assert retrieved["updated_at"] >= previous_updated_at, (
            f"updated_at did not advance.\n"
            f"  Previous: {previous_updated_at}\n"
            f"  Current:  {retrieved['updated_at']}"
        )
