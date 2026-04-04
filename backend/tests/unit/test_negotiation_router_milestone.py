"""Unit tests for negotiation router milestone_summaries_enabled toggle.

Tests:
- Request with milestone_summaries_enabled=True forces structured_memory_enabled=True
- Request without milestone_summaries_enabled defaults to False
- The field is persisted to Firestore
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.db import get_session_store
from app.main import app
from app.scenarios.models import ArenaScenario
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry

# ---------------------------------------------------------------------------
# Fixtures
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


def _build_mock_registry() -> MagicMock:
    registry = MagicMock(spec=ScenarioRegistry)
    registry.get_scenario.return_value = _SCENARIO
    registry._scenarios = {"test-scenario": _SCENARIO}
    return registry


def _build_mock_db():
    """Build a mock DB that captures persisted data."""
    db = MagicMock()
    stored_data: dict = {}

    async def _capture_create(state):
        stored_data.update(state.model_dump())

    db.create_session = AsyncMock(side_effect=_capture_create)

    # Cloud-mode mocks (not used in local mode tests, but needed to avoid errors)
    doc_ref = MagicMock()
    doc_ref.set = AsyncMock(side_effect=lambda data: stored_data.update(data))
    db._collection = MagicMock()
    db._collection.document = MagicMock(return_value=doc_ref)

    waitlist_doc = MagicMock()
    waitlist_doc.exists = True
    waitlist_doc.to_dict.return_value = {"token_balance": 100}
    waitlist_ref = MagicMock()
    waitlist_ref.get = AsyncMock(return_value=waitlist_doc)
    db._db = MagicMock()
    db._db.collection.return_value = MagicMock()
    db._db.collection.return_value.document.return_value = waitlist_ref

    return db, stored_data


async def _post_start(payload: dict) -> tuple[httpx.Response, dict]:
    """Helper: POST /negotiation/start with mocked deps, return response + stored data."""
    mock_registry = _build_mock_registry()
    mock_db, stored_data = _build_mock_db()

    app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
    app.dependency_overrides[get_session_store] = lambda: mock_db

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post("/api/v1/negotiation/start", json=payload)
        return resp, stored_data
    finally:
        app.dependency_overrides.pop(get_scenario_registry, None)
        app.dependency_overrides.pop(get_session_store, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_milestone_enabled_forces_structured_memory():
    """milestone_summaries_enabled=True must force structured_memory_enabled=True,
    even when structured_memory_enabled is explicitly False in the request."""
    resp, stored = await _post_start({
        "email": "test@example.com",
        "scenario_id": "test-scenario",
        "structured_memory_enabled": False,
        "milestone_summaries_enabled": True,
    })

    assert resp.status_code == 200
    assert stored["milestone_summaries_enabled"] is True
    assert stored["structured_memory_enabled"] is True


@pytest.mark.asyncio
async def test_milestone_enabled_preserves_structured_memory_when_already_true():
    """When both flags are True, both should remain True."""
    resp, stored = await _post_start({
        "email": "test@example.com",
        "scenario_id": "test-scenario",
        "structured_memory_enabled": True,
        "milestone_summaries_enabled": True,
    })

    assert resp.status_code == 200
    assert stored["milestone_summaries_enabled"] is True
    assert stored["structured_memory_enabled"] is True


@pytest.mark.asyncio
async def test_milestone_defaults_to_false():
    """Omitting milestone_summaries_enabled should default to False."""
    resp, stored = await _post_start({
        "email": "test@example.com",
        "scenario_id": "test-scenario",
    })

    assert resp.status_code == 200
    assert stored["milestone_summaries_enabled"] is False


@pytest.mark.asyncio
async def test_milestone_false_does_not_force_structured_memory():
    """milestone_summaries_enabled=False should not alter structured_memory_enabled."""
    resp, stored = await _post_start({
        "email": "test@example.com",
        "scenario_id": "test-scenario",
        "structured_memory_enabled": False,
        "milestone_summaries_enabled": False,
    })

    assert resp.status_code == 200
    assert stored["milestone_summaries_enabled"] is False
    assert stored["structured_memory_enabled"] is False


@pytest.mark.asyncio
async def test_milestone_field_persisted_to_firestore():
    """The milestone_summaries_enabled field must appear in persisted data."""
    resp, stored = await _post_start({
        "email": "test@example.com",
        "scenario_id": "test-scenario",
        "milestone_summaries_enabled": True,
    })

    assert resp.status_code == 200
    # Field must exist in the persisted document
    assert "milestone_summaries_enabled" in stored
    assert stored["milestone_summaries_enabled"] is True
    # Milestone-related fields from NegotiationStateModel defaults should also be present
    assert "milestone_summaries" in stored
    assert "sliding_window_size" in stored
    assert "milestone_interval" in stored
