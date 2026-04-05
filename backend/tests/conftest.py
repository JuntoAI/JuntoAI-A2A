"""Shared test fixtures for the JuntoAI A2A backend test suite."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.db import get_profile_client, get_session_store
from app.main import app
from app.middleware import get_sse_tracker
from app.middleware.sse_limiter import SSEConnectionTracker
from app.models.negotiation import NegotiationStateModel


@pytest.fixture()
def sample_state_factory():
    """Factory fixture that creates NegotiationStateModel instances with test data."""

    def _create(**overrides):
        defaults = {
            "session_id": "test-session-001",
            "scenario_id": "test-scenario-001",
            "turn_count": 0,
            "max_turns": 15,
            "current_speaker": "Buyer",
            "deal_status": "Negotiating",
            "current_offer": 0.0,
            "history": [],
            "warning_count": 0,
            "hidden_context": {},
            "agreement_threshold": 1000000.0,
            "active_toggles": [],
            "turn_order": [],
            "turn_order_index": 0,
            "agent_states": {},
        }
        defaults.update(overrides)
        return NegotiationStateModel(**defaults)

    return _create


@pytest.fixture()
def sample_state(sample_state_factory):
    """A default NegotiationStateModel instance for tests."""
    return sample_state_factory()


@pytest.fixture()
def mock_db():
    """Mock FirestoreSessionClient with async methods."""
    db = MagicMock()
    db.get_session_doc = AsyncMock()
    db.get_session = AsyncMock()
    db.create_session = AsyncMock()
    db.update_session = AsyncMock()
    return db


@pytest.fixture()
def mock_tracker():
    """Mock SSEConnectionTracker with async methods."""
    tracker = MagicMock(spec=SSEConnectionTracker)
    tracker.acquire = AsyncMock(return_value=True)
    tracker.release = AsyncMock()
    return tracker


@pytest.fixture()
def mock_registry(valid_scenario_dict):
    """Mock ScenarioRegistry that returns a valid scenario for any ID."""
    from app.scenarios.models import ArenaScenario
    from app.scenarios.registry import ScenarioRegistry

    registry = MagicMock(spec=ScenarioRegistry)
    scenario = ArenaScenario(**valid_scenario_dict)
    registry.get_scenario.return_value = scenario
    registry.list_scenarios.return_value = [
        {"id": scenario.id, "name": scenario.name, "description": scenario.description}
    ]
    return registry


@pytest.fixture()
def mock_profile_client():
    """Mock ProfileClient with async methods."""
    pc = MagicMock()
    pc.get_profile = AsyncMock(return_value=None)

    # Mock _db for waitlist access
    waitlist_doc = MagicMock()
    waitlist_doc.exists = True
    waitlist_doc.to_dict.return_value = {"token_balance": 100}
    waitlist_ref = MagicMock()
    waitlist_ref.get = AsyncMock(return_value=waitlist_doc)
    pc._db = MagicMock()
    pc._db.collection.return_value = MagicMock()
    pc._db.collection.return_value.document.return_value = waitlist_ref

    return pc


@pytest.fixture()
async def test_client(mock_db, mock_tracker, mock_registry, mock_profile_client):
    """Async httpx client with dependency overrides for integration tests."""
    from app.scenarios.router import get_scenario_registry

    app.dependency_overrides[get_session_store] = lambda: mock_db
    app.dependency_overrides[get_sse_tracker] = lambda: mock_tracker
    app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
    app.dependency_overrides[get_profile_client] = lambda: mock_profile_client
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


import json

from app.scenarios.models import ArenaScenario


# ---------------------------------------------------------------------------
# Scenario Engine — shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def valid_scenario_dict():
    """Return a minimal valid ArenaScenario dict."""
    return {
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


@pytest.fixture()
def valid_scenario_dir(tmp_path, valid_scenario_dict):
    """Create a temp directory with valid scenario JSON files."""
    for i, sid in enumerate(["alpha", "beta"]):
        data = {**valid_scenario_dict, "id": sid, "name": f"Scenario {sid}"}
        path = tmp_path / f"{sid}.scenario.json"
        path.write_text(json.dumps(data), encoding="utf-8")
    return tmp_path
