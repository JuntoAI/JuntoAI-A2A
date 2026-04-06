"""Integration tests for the builder router endpoints.

# Feature: ai-scenario-builder
# Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 7.4, 7.6
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.db import get_custom_scenario_store, get_profile_client
from app.main import app
from app.routers.builder import (
    get_builder_llm_agent,
    get_builder_session_manager,
    get_health_check_analyzer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _valid_scenario_dict():
    """Return a minimal valid ArenaScenario dict."""
    return {
        "id": "test-scenario",
        "name": "Test Scenario",
        "description": "A test scenario for integration testing",
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
                "model_id": "test-model",
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
                "model_id": "test-model",
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


@pytest.fixture()
def mock_profile_client():
    pc = MagicMock()
    pc.get_profile = AsyncMock(
        return_value={"email": "test@example.com", "email_verified": True}
    )
    return pc


@pytest.fixture()
def mock_profile_client_no_profile():
    pc = MagicMock()
    pc.get_profile = AsyncMock(return_value=None)
    return pc


@pytest.fixture()
def mock_store():
    store = MagicMock()
    store.list_by_email = AsyncMock(return_value=[])
    store.delete = AsyncMock(return_value=True)
    store.save = AsyncMock(return_value="saved-scenario-id")
    store.count_by_email = AsyncMock(return_value=0)
    return store


@pytest.fixture()
def mock_session_manager():
    mgr = MagicMock()
    session = MagicMock()
    session.session_id = "test-session"
    session.conversation_history = []
    session.partial_scenario = {}
    mgr.get_session.return_value = session
    mgr.create_session.return_value = session
    mgr.add_message = MagicMock()
    mgr.update_scenario = MagicMock()
    mgr._sessions = {}
    return mgr


@pytest.fixture()
def mock_llm_agent():
    agent = MagicMock()

    from app.builder.events import BuilderCompleteEvent, BuilderTokenEvent

    async def _stream(*args, **kwargs):
        yield BuilderTokenEvent(event_type="builder_token", token="Hello")
        yield BuilderCompleteEvent(event_type="builder_complete")

    agent.stream_response = _stream
    return agent


@pytest.fixture()
def mock_health_analyzer():
    analyzer = MagicMock()

    from app.builder.events import (
        HealthCheckCompleteEvent,
        HealthCheckStartEvent,
    )

    async def _analyze(*args, **kwargs):
        yield HealthCheckStartEvent(event_type="builder_health_check_start")
        yield HealthCheckCompleteEvent(
            event_type="builder_health_check_complete",
            report={"readiness_score": 85, "tier": "Ready"},
        )

    analyzer.analyze = _analyze
    return analyzer


# ---------------------------------------------------------------------------
# POST /builder/chat tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_valid_request_returns_sse_stream(
    mock_profile_client, mock_store, mock_session_manager, mock_llm_agent
):
    """Valid chat request returns SSE stream with token and complete events."""
    app.dependency_overrides[get_profile_client] = lambda: mock_profile_client
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_builder_session_manager] = lambda: mock_session_manager
    app.dependency_overrides[get_builder_llm_agent] = lambda: mock_llm_agent

    try:
        with patch(
            "app.routers.builder._get_token_balance",
            new=AsyncMock(return_value=50),
        ), patch(
            "app.routers.builder._deduct_token",
            new=AsyncMock(),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.post(
                    "/api/v1/builder/chat",
                    json={
                        "email": "test@example.com",
                        "session_id": "s1",
                        "message": "Build me a scenario",
                    },
                )
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers["content-type"]

                # Parse SSE events
                events = _parse_sse_events(resp.text)
                event_types = [e.get("event_type") for e in events]
                assert "builder_token" in event_types
                assert "builder_complete" in event_types
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_missing_email_returns_401():
    """POST /builder/chat with empty email returns 401 or 422."""
    mock_store = MagicMock()
    mock_store.list_by_email = AsyncMock(return_value=[])
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/builder/chat",
                json={"email": "", "session_id": "s1", "message": "hi"},
            )
            assert resp.status_code in (401, 422)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_missing_profile_returns_403(mock_profile_client_no_profile, mock_store):
    """POST /builder/chat with no profile returns 403."""
    app.dependency_overrides[get_profile_client] = lambda: mock_profile_client_no_profile
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        with patch(
            "app.routers.builder._get_token_balance",
            new=AsyncMock(return_value=50),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.post(
                    "/api/v1/builder/chat",
                    json={
                        "email": "noone@example.com",
                        "session_id": "s1",
                        "message": "hi",
                    },
                )
                assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_zero_tokens_returns_429(mock_profile_client, mock_store):
    """POST /builder/chat with zero tokens returns 429."""
    app.dependency_overrides[get_profile_client] = lambda: mock_profile_client
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        with patch(
            "app.routers.builder._get_token_balance",
            new=AsyncMock(return_value=0),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.post(
                    "/api/v1/builder/chat",
                    json={
                        "email": "test@example.com",
                        "session_id": "s1",
                        "message": "hi",
                    },
                )
                assert resp.status_code == 429
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /builder/save tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_valid_scenario(
    mock_profile_client, mock_store, mock_health_analyzer
):
    """Valid scenario saves and returns SSE stream with health check + save events."""
    app.dependency_overrides[get_profile_client] = lambda: mock_profile_client
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_health_check_analyzer] = lambda: mock_health_analyzer

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/builder/save",
                json={
                    "email": "test@example.com",
                    "scenario_json": _valid_scenario_dict(),
                },
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            events = _parse_sse_events(resp.text)
            event_types = [e.get("event_type") for e in events]
            assert "builder_health_check_start" in event_types
            assert "builder_health_check_complete" in event_types
            assert "builder_save_complete" in event_types
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_save_invalid_scenario_returns_422(mock_profile_client, mock_store):
    """Invalid scenario returns 422 with specific errors."""
    app.dependency_overrides[get_profile_client] = lambda: mock_profile_client
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/builder/save",
                json={
                    "email": "test@example.com",
                    "scenario_json": {"id": "bad", "name": "Bad"},
                },
            )
            assert resp.status_code == 422
            body = resp.json()
            assert "errors" in body
            assert len(body["errors"]) >= 1
            # Each error should have loc and msg
            for err in body["errors"]:
                assert "loc" in err
                assert "msg" in err
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_save_missing_profile_returns_403(
    mock_profile_client_no_profile, mock_store
):
    """Save with no profile returns 403."""
    app.dependency_overrides[get_profile_client] = lambda: mock_profile_client_no_profile
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/builder/save",
                json={
                    "email": "noone@example.com",
                    "scenario_json": _valid_scenario_dict(),
                },
            )
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /builder/scenarios tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_scenarios_returns_user_scenarios(mock_store):
    """GET /builder/scenarios returns user's scenarios."""
    mock_store.list_by_email = AsyncMock(
        return_value=[
            {"scenario_id": "s1", "scenario_json": {"name": "Test"}, "created_at": "2024-01-01"},
        ]
    )
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/builder/scenarios",
                params={"email": "test@example.com"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["scenario_id"] == "s1"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_scenarios_empty_for_new_user(mock_store):
    """GET /builder/scenarios returns empty list for new user."""
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/builder/scenarios",
                params={"email": "new@example.com"},
            )
            assert resp.status_code == 200
            assert resp.json() == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_scenarios_missing_email():
    """GET /builder/scenarios without email returns 401."""
    mock_store = MagicMock()
    mock_store.list_by_email = AsyncMock(return_value=[])
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/builder/scenarios",
                params={"email": ""},
            )
            assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# DELETE /builder/scenarios/{id} tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_scenario_success(mock_store):
    """DELETE /builder/scenarios/{id} deletes owned scenario."""
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.delete(
                "/api/v1/builder/scenarios/some-id",
                params={"email": "test@example.com"},
            )
            assert resp.status_code == 200
            assert resp.json()["scenario_id"] == "some-id"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_scenario_not_found(mock_store):
    """DELETE /builder/scenarios/{id} returns 404 for non-existent."""
    mock_store.delete = AsyncMock(return_value=False)
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.delete(
                "/api/v1/builder/scenarios/nonexistent",
                params={"email": "test@example.com"},
            )
            assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_scenario_missing_email():
    """DELETE /builder/scenarios/{id} without email returns 401."""
    mock_store = MagicMock()
    mock_store.delete = AsyncMock(return_value=False)
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.delete(
                "/api/v1/builder/scenarios/some-id",
                params={"email": ""},
            )
            assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Round-trip test: save → retrieve → load_scenario_from_dict → create_initial_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_round_trip_save_retrieve_create_state():
    """Save a scenario, retrieve it, load it, and create initial state."""
    import tempfile

    from app.builder.scenario_store import SQLiteCustomScenarioStore
    from app.orchestrator.state import create_initial_state
    from app.scenarios.loader import load_scenario_from_dict
    from app.scenarios.models import ArenaScenario

    scenario_dict = _valid_scenario_dict()
    scenario = ArenaScenario.model_validate(scenario_dict)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
        email = "roundtrip@example.com"

        # Save
        scenario_id = await store.save(email, scenario)
        assert scenario_id

        # Retrieve
        doc = await store.get(email, scenario_id)
        assert doc is not None

        # Load
        loaded = load_scenario_from_dict(doc["scenario_json"])
        assert loaded.model_dump() == scenario.model_dump()

        # Create initial state
        state = create_initial_state(
            session_id="test-session",
            scenario_config=loaded.model_dump(),
        )
        assert state["session_id"] == "test-session"
        assert state["scenario_id"] == scenario.id
        agent_roles = {a.role for a in scenario.agents}
        for role in state["turn_order"]:
            assert role in agent_roles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sse_events(text: str) -> list[dict]:
    """Parse SSE text into a list of JSON event dicts."""
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        for line in block.split("\n"):
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
    return events
