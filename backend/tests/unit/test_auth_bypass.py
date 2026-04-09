"""Property-based tests for auth gate bypass in local mode.

# Feature: 080_a2a-local-battle-arena, Property 6: Local mode accepts any email value
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st

from app.db import get_profile_client, get_session_store
from app.db.base import SessionStore
from app.main import app
from app.middleware import get_event_buffer, get_sse_tracker
from app.middleware.event_buffer import SSEEventBuffer
from app.middleware.sse_limiter import SSEConnectionTracker
from app.orchestrator.availability_checker import AllowedModels
from app.scenarios.router import get_scenario_registry


def _empty_allowed_models() -> AllowedModels:
    """Return an empty AllowedModels for mocking the lifespan probe."""
    return AllowedModels(
        entries=(),
        model_ids=frozenset(),
        probe_results=(),
        probed_at="2025-01-01T00:00:00+00:00",
    )


def _make_mock_db(session_id: str = "test-session") -> SessionStore:
    """Create a mock SessionStore that returns a valid session doc."""
    db = MagicMock(spec=SessionStore)
    db.get_session_doc = AsyncMock(return_value={
        "session_id": session_id,
        "scenario_id": "test-scenario",
        # No owner_email — local mode doesn't store it
    })
    db.get_session = AsyncMock()
    db.create_session = AsyncMock()
    db.update_session = AsyncMock()
    return db


def _make_mock_tracker() -> SSEConnectionTracker:
    """Create a mock SSE tracker that always allows connections."""
    tracker = MagicMock(spec=SSEConnectionTracker)
    tracker.acquire = AsyncMock(return_value=True)
    tracker.release = AsyncMock()
    return tracker


def _make_mock_event_buffer() -> SSEEventBuffer:
    """Create a mock event buffer."""
    buf = MagicMock(spec=SSEEventBuffer)
    buf.append = AsyncMock(return_value=1)
    buf.replay_after = AsyncMock(return_value=[])
    buf.is_session_terminal = AsyncMock(return_value=False)
    return buf


def _make_mock_registry():
    """Create a mock ScenarioRegistry that returns a valid scenario."""
    from app.scenarios.models import ArenaScenario
    from app.scenarios.registry import ScenarioRegistry

    scenario_dict = {
        "id": "test-scenario",
        "name": "Test",
        "description": "Test scenario",
        "agents": [
            {
                "role": "Buyer", "name": "Alice", "type": "negotiator",
                "persona_prompt": "You are a buyer.", "goals": ["Buy low"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "assertive", "output_fields": ["offer"],
                "model_id": "gemini-2.5-flash",
            },
            {
                "role": "Seller", "name": "Bob", "type": "negotiator",
                "persona_prompt": "You are a seller.", "goals": ["Sell high"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "firm", "output_fields": ["offer"],
                "model_id": "gemini-2.5-flash",
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
            "equivalent_human_time": "~1 week",
            "process_label": "Test",
        },
    }
    registry = MagicMock(spec=ScenarioRegistry)
    registry.get_scenario.return_value = ArenaScenario(**scenario_dict)
    return registry


@given(
    email=st.text(min_size=1),
)
@hypothesis_settings(max_examples=100)
def test_local_mode_accepts_any_email(email: str):
    """**Validates: Requirements 5.3**

    For any non-empty string (including unicode), RUN_MODE=local does not
    reject based on email — the auth gate is completely bypassed.

    We test the stream_negotiation endpoint because it takes email as a
    query parameter and performs the email ownership check. In local mode,
    this check must be skipped entirely, so no 403 is ever returned.
    """
    mock_db = _make_mock_db()
    mock_tracker = _make_mock_tracker()
    mock_registry = _make_mock_registry()
    mock_buffer = _make_mock_event_buffer()

    # Mock profile client for stream_negotiation dependency
    mock_pc = MagicMock()
    mock_pc.get_profile = AsyncMock(return_value=None)
    mock_pc._db = MagicMock()

    app.dependency_overrides[get_session_store] = lambda: mock_db
    app.dependency_overrides[get_sse_tracker] = lambda: mock_tracker
    app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
    app.dependency_overrides[get_event_buffer] = lambda: mock_buffer
    app.dependency_overrides[get_profile_client] = lambda: mock_pc

    try:
        with patch("app.routers.negotiation.settings") as mock_settings, \
             patch("app.routers.negotiation.run_negotiation") as mock_run, \
             patch(
                 "app.main.AvailabilityChecker.probe_all",
                 new_callable=AsyncMock,
                 return_value=_empty_allowed_models(),
             ):
            mock_settings.RUN_MODE = "local"
            # run_negotiation yields nothing — stream ends immediately
            mock_run.return_value = aiter_empty()

            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get(
                    f"/api/v1/negotiation/stream/test-session",
                    params={"email": email},
                )
            # Must NOT be 403 (email rejection). 200 = stream started OK.
            assert resp.status_code != 403, (
                f"Local mode rejected email {email!r} with 403"
            )
    finally:
        app.dependency_overrides.clear()


async def _aiter_empty():
    """Async generator that yields nothing."""
    return
    yield  # noqa: unreachable — makes this an async generator


def aiter_empty():
    """Return an empty async iterator for mocking run_negotiation."""
    return _aiter_empty()
