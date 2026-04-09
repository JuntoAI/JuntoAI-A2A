"""Unit tests for PUT /builder/scenarios/{scenario_id} endpoint.

# Feature: 320_scenario-management
# Requirements: 5.1, 5.2, 5.3, 5.4, 5.5

Tests cover:
- Valid update returns 200 with {scenario_id, name, updated_at}
- 404 when scenario not found or not owned
- 422 when scenario_json fails ArenaScenario validation
- 401 when email is missing or empty
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import pytest

from app.builder.scenario_store import SQLiteCustomScenarioStore
from app.db import get_custom_scenario_store
from app.main import app
from app.scenarios.models import ArenaScenario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_scenario_dict() -> dict:
    """Minimal valid ArenaScenario dict."""
    return {
        "id": "update-test",
        "name": "Update Test Scenario",
        "description": "For PUT endpoint testing",
        "agents": [
            {
                "role": "Buyer",
                "name": "Alice",
                "type": "negotiator",
                "persona_prompt": "You are a buyer.",
                "goals": ["Buy low"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "assertive",
                "output_fields": ["proposed_price"],
                "model_id": "gemini-2.5-flash",
            },
            {
                "role": "Seller",
                "name": "Bob",
                "type": "negotiator",
                "persona_prompt": "You are a seller.",
                "goals": ["Sell high"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "firm",
                "output_fields": ["proposed_price"],
                "model_id": "gemini-2.5-flash",
            },
        ],
        "toggles": [
            {
                "id": "t1",
                "label": "Secret",
                "target_agent_role": "Buyer",
                "hidden_context_payload": {"info": "secret"},
            }
        ],
        "negotiation_params": {
            "max_turns": 10,
            "agreement_threshold": 1000.0,
            "turn_order": ["Buyer", "Seller"],
        },
        "outcome_receipt": {
            "equivalent_human_time": "~1 week",
            "process_label": "Test",
        },
    }


EMAIL = "update-test@example.com"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_put_valid_update_returns_200():
    """PUT with valid scenario_json returns 200 with scenario_id, name, updated_at."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "update.db")
        store = SQLiteCustomScenarioStore(db_path)

        # Seed a scenario
        scenario = ArenaScenario.model_validate(_valid_scenario_dict())
        scenario_id = await store.save(EMAIL, scenario)

        # Prepare updated payload (rename)
        updated = _valid_scenario_dict()
        updated["name"] = "Renamed Scenario"

        app.dependency_overrides[get_custom_scenario_store] = lambda: store
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.put(
                    f"/api/v1/builder/scenarios/{scenario_id}",
                    params={"email": EMAIL},
                    json={"scenario_json": updated},
                )

            assert resp.status_code == 200
            body = resp.json()
            assert body["scenario_id"] == scenario_id
            assert body["name"] == "Renamed Scenario"
            assert "updated_at" in body
            assert body["updated_at"] is not None
        finally:
            app.dependency_overrides.pop(get_custom_scenario_store, None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_put_nonexistent_scenario_returns_404():
    """PUT for a scenario_id that doesn't exist returns 404."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "update404.db")
        store = SQLiteCustomScenarioStore(db_path)

        app.dependency_overrides[get_custom_scenario_store] = lambda: store
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.put(
                    "/api/v1/builder/scenarios/nonexistent-id",
                    params={"email": EMAIL},
                    json={"scenario_json": _valid_scenario_dict()},
                )

            assert resp.status_code == 404
            body = resp.json()
            assert "detail" in body
        finally:
            app.dependency_overrides.pop(get_custom_scenario_store, None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_put_invalid_scenario_json_returns_422():
    """PUT with invalid scenario_json returns 422 with non-empty errors list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "update422.db")
        store = SQLiteCustomScenarioStore(db_path)

        # Seed a valid scenario so the ID exists
        scenario = ArenaScenario.model_validate(_valid_scenario_dict())
        scenario_id = await store.save(EMAIL, scenario)

        # Send invalid payload (missing required fields)
        invalid_json = {"id": "bad", "name": "Bad"}

        app.dependency_overrides[get_custom_scenario_store] = lambda: store
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.put(
                    f"/api/v1/builder/scenarios/{scenario_id}",
                    params={"email": EMAIL},
                    json={"scenario_json": invalid_json},
                )

            assert resp.status_code == 422
            body = resp.json()
            assert "errors" in body
            assert len(body["errors"]) > 0
            # Each error should have loc and msg
            for err in body["errors"]:
                assert "loc" in err
                assert "msg" in err
        finally:
            app.dependency_overrides.pop(get_custom_scenario_store, None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_put_missing_email_returns_401():
    """PUT without email query param returns 401."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "update401.db")
        store = SQLiteCustomScenarioStore(db_path)

        app.dependency_overrides[get_custom_scenario_store] = lambda: store
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.put(
                    "/api/v1/builder/scenarios/some-id",
                    params={"email": ""},
                    json={"scenario_json": _valid_scenario_dict()},
                )

            assert resp.status_code == 401
            body = resp.json()
            assert "detail" in body
        finally:
            app.dependency_overrides.pop(get_custom_scenario_store, None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_put_empty_email_returns_401():
    """PUT with empty string email returns 401."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "update401b.db")
        store = SQLiteCustomScenarioStore(db_path)

        app.dependency_overrides[get_custom_scenario_store] = lambda: store
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                # No email param at all
                resp = await client.put(
                    "/api/v1/builder/scenarios/some-id",
                    json={"scenario_json": _valid_scenario_dict()},
                )

            assert resp.status_code == 401
        finally:
            app.dependency_overrides.pop(get_custom_scenario_store, None)
