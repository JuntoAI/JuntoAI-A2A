"""Shared test fixtures for the JuntoAI A2A backend test suite."""

from datetime import datetime, timezone
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
    waitlist_doc.to_dict.return_value = {
        "token_balance": 100,
        "last_reset_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    waitlist_ref = MagicMock()
    waitlist_ref.get = AsyncMock(return_value=waitlist_doc)
    waitlist_ref.update = AsyncMock()
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
def mock_firestore_async_client():
    """A MagicMock mimicking google.cloud.firestore.AsyncClient.

    Provides the chained call pattern used by FirestoreSessionClient and
    ProfileClient: ``client.collection(...).document(...).get/set/update()``.
    The leaf methods (``.get()``, ``.set()``, ``.update()``) are AsyncMocks
    so they can be awaited in async tests.
    """
    client = MagicMock()

    # Build the chain: collection() → doc_ref, doc_ref.get/set/update are async
    doc_ref = MagicMock()
    doc_ref.get = AsyncMock()
    doc_ref.set = AsyncMock()
    doc_ref.update = AsyncMock()

    collection_ref = MagicMock()
    collection_ref.document.return_value = doc_ref

    client.collection.return_value = collection_ref

    # Expose inner mocks for easy assertion in tests
    client._doc_ref = doc_ref
    client._collection_ref = collection_ref

    return client


@pytest.fixture()
def negotiation_start_payload():
    """A valid StartNegotiationRequest-compatible dict for POST /negotiation/start."""
    return {
        "email": "test@example.com",
        "scenario_id": "test-scenario",
        "active_toggles": ["toggle_1"],
    }


@pytest.fixture()
def sample_history():
    """Multi-turn history array with negotiator, regulator, and observer entries.

    Represents a realistic 2-turn exchange: Buyer proposes → Regulator evaluates
    → Seller counters → Regulator evaluates → Observer comments.
    """
    return [
        {
            "role": "Buyer",
            "agent_type": "negotiator",
            "turn_number": 1,
            "content": {
                "inner_thought": "I should start low to leave room for negotiation.",
                "public_message": "I propose $500,000 for the acquisition.",
                "proposed_price": 500000.0,
            },
        },
        {
            "role": "Regulator",
            "agent_type": "regulator",
            "turn_number": 1,
            "content": {
                "reasoning": "Initial offer is within acceptable range.",
                "public_message": "Offer noted. No compliance issues.",
                "status": "CLEAR",
            },
        },
        {
            "role": "Seller",
            "agent_type": "negotiator",
            "turn_number": 2,
            "content": {
                "inner_thought": "That is too low. I need at least $800k.",
                "public_message": "I counter at $850,000.",
                "proposed_price": 850000.0,
            },
        },
        {
            "role": "Regulator",
            "agent_type": "regulator",
            "turn_number": 2,
            "content": {
                "reasoning": "Counter-offer is reasonable. Monitoring spread.",
                "public_message": "Counter-offer accepted for review.",
                "status": "CLEAR",
            },
        },
        {
            "role": "Analyst",
            "agent_type": "observer",
            "turn_number": 2,
            "content": {
                "observation": "Significant gap between parties. Buyer at $500k, Seller at $850k.",
                "recommendation": "Consider splitting the difference around $675k.",
            },
        },
    ]


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
