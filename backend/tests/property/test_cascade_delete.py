"""Property-based tests for cascade delete of custom scenarios.

# Feature: 320_scenario-management, Property 2: Cascade delete removes all connected sessions and returns correct count

For any custom scenario with N connected sessions (where N >= 0), after a
successful cascade delete, list_sessions_by_scenario for that scenario should
return an empty list, the scenario should no longer exist in the
CustomScenarioStore, and the API response deleted_sessions_count should equal N.

**Validates: Requirements 1.2, 1.3**
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import httpx
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.builder.scenario_store import SQLiteCustomScenarioStore
from app.db import get_custom_scenario_store, get_session_store
from app.db.sqlite_client import SQLiteSessionClient
from app.main import app
from app.orchestrator.available_models import VALID_MODEL_IDS
from app.scenarios.models import ArenaScenario

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_model_id = sorted(VALID_MODEL_IDS)[0]
_email = "cascade@test.com"

# Minimal valid scenario dict — kept static to avoid unnecessary generation
# complexity; the property under test is about cascade delete, not scenario shape.
_SEED_SCENARIO = {
    "id": "cascade-seed",
    "name": "Cascade Test Scenario",
    "description": "A scenario for cascade delete testing",
    "difficulty": "beginner",
    "agents": [
        {
            "role": "Buyer",
            "name": "B",
            "type": "negotiator",
            "persona_prompt": "Buy",
            "goals": ["Buy"],
            "budget": {"min": 0, "max": 100, "target": 50},
            "tone": "firm",
            "output_fields": ["offer"],
            "model_id": _model_id,
        },
        {
            "role": "Seller",
            "name": "S",
            "type": "negotiator",
            "persona_prompt": "Sell",
            "goals": ["Sell"],
            "budget": {"min": 0, "max": 100, "target": 50},
            "tone": "firm",
            "output_fields": ["offer"],
            "model_id": _model_id,
        },
    ],
    "toggles": [
        {
            "id": "t1",
            "label": "Info",
            "target_agent_role": "Buyer",
            "hidden_context_payload": {"k": "v"},
        }
    ],
    "negotiation_params": {
        "max_turns": 5,
        "agreement_threshold": 100,
        "turn_order": ["Buyer", "Seller"],
    },
    "outcome_receipt": {
        "equivalent_human_time": "1h",
        "process_label": "Test",
    },
}


@st.composite
def session_count(draw):
    """Generate a number of sessions between 0 and 10."""
    return draw(st.integers(min_value=0, max_value=10))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_session(
    client: SQLiteSessionClient,
    session_id: str,
    scenario_id: str,
    owner_email: str,
) -> None:
    """Insert a minimal session record directly into SQLite."""
    record = {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "owner_email": owner_email,
        "turn_count": 0,
        "max_turns": 10,
        "current_speaker": "Buyer",
        "deal_status": "Negotiating",
        "current_offer": 0.0,
        "history": [],
        "warning_count": 0,
        "hidden_context": {},
        "agreement_threshold": 1000.0,
        "active_toggles": [],
        "turn_order": ["Buyer", "Seller"],
        "turn_order_index": 0,
        "agent_states": {},
    }
    conn = await client._get_connection()
    try:
        ts = "2025-01-01T00:00:00+00:00"
        await conn.execute(
            "INSERT INTO negotiation_sessions (session_id, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, json.dumps(record), ts, ts),
        )
        await conn.commit()
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Feature: 320_scenario-management
# Property 2: Cascade delete removes all connected sessions and returns correct count
# **Validates: Requirements 1.2, 1.3**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.asyncio
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(n_sessions=session_count())
async def test_cascade_delete_removes_all_sessions_and_returns_correct_count(
    n_sessions: int,
):
    """After cascade delete, all connected sessions are gone, the scenario is
    removed, and the response reports the correct deleted_sessions_count."""

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "prop2.db")
        store = SQLiteCustomScenarioStore(db_path)
        session_client = SQLiteSessionClient(db_path)

        # 1. Seed a custom scenario
        scenario_model = ArenaScenario.model_validate(_SEED_SCENARIO)
        scenario_id = await store.save(_email, scenario_model)

        # 2. Insert N sessions linked to this scenario
        for i in range(n_sessions):
            await _insert_session(
                session_client,
                session_id=f"sess-{scenario_id}-{i}",
                scenario_id=scenario_id,
                owner_email=_email,
            )

        # 3. Override dependencies to use our test stores
        app.dependency_overrides[get_custom_scenario_store] = lambda: store
        app.dependency_overrides[get_session_store] = lambda: session_client
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.delete(
                    f"/api/v1/builder/scenarios/{scenario_id}",
                    params={"email": _email},
                )

            # 4. Verify response
            assert resp.status_code == 200, (
                f"Expected 200, got {resp.status_code}: {resp.text}"
            )
            body = resp.json()
            assert body["deleted_sessions_count"] == n_sessions, (
                f"Expected deleted_sessions_count={n_sessions}, got {body['deleted_sessions_count']}"
            )

            # 5. Verify sessions are gone
            remaining = await session_client.list_sessions_by_scenario(
                scenario_id, _email
            )
            assert remaining == [], (
                f"Expected empty session list after cascade delete, got {len(remaining)} sessions"
            )

            # 6. Verify scenario is gone
            scenario_doc = await store.get(_email, scenario_id)
            assert scenario_doc is None, (
                "Scenario should no longer exist after cascade delete"
            )
        finally:
            app.dependency_overrides.pop(get_custom_scenario_store, None)
            app.dependency_overrides.pop(get_session_store, None)
