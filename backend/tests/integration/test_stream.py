"""Integration tests for GET /api/v1/negotiation/stream/{session_id}."""

import json

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.db import get_profile_client, get_session_store
from app.exceptions import SessionNotFoundError
from app.main import app
from app.middleware import get_event_buffer, get_sse_tracker
from app.middleware.event_buffer import SSEEventBuffer
from app.middleware.sse_limiter import SSEConnectionTracker
from app.scenarios.router import get_scenario_registry


class TestStreamNotFound:
    async def test_404_unknown_session(self, test_client, mock_db):
        mock_db.get_session_doc.side_effect = SessionNotFoundError("unknown-id")
        resp = await test_client.get(
            "/api/v1/negotiation/stream/unknown-id",
            params={"email": "user@test.com"},
        )
        assert resp.status_code == 404
        assert "unknown-id" in resp.json()["detail"]


class TestStreamRateLimited:
    async def test_429_limit_exceeded(self, test_client, mock_db, mock_tracker):
        mock_db.get_session_doc.return_value = {
            "session_id": "s1",
            "scenario_id": "sc1",
            "owner_email": "user@test.com",
        }
        mock_tracker.acquire = AsyncMock(return_value=False)
        resp = await test_client.get(
            "/api/v1/negotiation/stream/s1",
            params={"email": "user@test.com"},
        )
        assert resp.status_code == 429
        assert "limit" in resp.json()["detail"].lower()


class TestStreamForbidden:
    async def test_403_email_mismatch(self, test_client, mock_db):
        mock_db.get_session_doc.return_value = {
            "session_id": "s1",
            "scenario_id": "sc1",
            "owner_email": "owner@test.com",
        }
        with patch("app.routers.negotiation.settings") as mock_settings:
            mock_settings.RUN_MODE = "cloud"
            resp = await test_client.get(
                "/api/v1/negotiation/stream/s1",
                params={"email": "intruder@test.com"},
            )
        assert resp.status_code == 403


class TestStreamSuccess:
    @pytest.mark.slow
    async def test_successful_stream_returns_event_stream(
        self, test_client, mock_db, mock_tracker
    ):
        mock_db.get_session_doc.return_value = {
            "session_id": "s1",
            "scenario_id": "sc1",
            "owner_email": "user@test.com",
        }
        mock_tracker.acquire = AsyncMock(return_value=True)
        resp = await test_client.get(
            "/api/v1/negotiation/stream/s1",
            params={"email": "user@test.com"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        # Body should contain SSE-formatted events
        body = resp.text
        assert "data: " in body
        assert "\n\n" in body


@pytest.mark.integration
class TestStreamEventReplay:
    """Test event replay via Last-Event-ID (reconnection support)."""

    async def test_replay_returns_only_events_after_last_event_id(
        self, mock_db, mock_registry, mock_profile_client, valid_scenario_dict,
    ):
        """Pre-populate buffer with 5 events, mark terminal, request with
        last_event_id=2 → only events 3, 4, 5 are returned."""
        session_id = "replay-session"

        # Build a real event buffer and populate it
        event_buffer = SSEEventBuffer()
        event_data = []
        for i in range(1, 6):
            payload = json.dumps({"event_type": "agent_message", "seq": i})
            event_data.append(payload)
            is_terminal = i == 5
            await event_buffer.append(session_id, payload, is_terminal=is_terminal)

        mock_db.get_session_doc.return_value = {
            "session_id": session_id,
            "scenario_id": "test-scenario",
            "owner_email": "user@test.com",
        }

        mock_tracker = MagicMock(spec=SSEConnectionTracker)
        mock_tracker.acquire = AsyncMock(return_value=True)
        mock_tracker.release = AsyncMock()

        app.dependency_overrides[get_session_store] = lambda: mock_db
        app.dependency_overrides[get_sse_tracker] = lambda: mock_tracker
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        app.dependency_overrides[get_event_buffer] = lambda: event_buffer
        app.dependency_overrides[get_profile_client] = lambda: mock_profile_client

        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    f"/api/v1/negotiation/stream/{session_id}",
                    params={"email": "user@test.com", "last_event_id": 2},
                )

            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")

            body = resp.text
            # Parse SSE events from the body
            sse_events = _parse_sse_events(body)

            # Should have exactly 3 events (IDs 3, 4, 5)
            assert len(sse_events) == 3

            # Verify event IDs are 3, 4, 5
            assert [e["id"] for e in sse_events] == [3, 4, 5]

            # Verify the data payloads match what was buffered
            for i, evt in enumerate(sse_events):
                parsed = json.loads(evt["data"])
                assert parsed["seq"] == i + 3  # seq 3, 4, 5
        finally:
            app.dependency_overrides.clear()

    async def test_replay_with_last_event_id_zero_returns_all(
        self, mock_db, mock_registry, mock_profile_client,
    ):
        """last_event_id=0 on a terminal session → all events replayed."""
        session_id = "replay-all-session"

        event_buffer = SSEEventBuffer()
        for i in range(1, 4):
            payload = json.dumps({"event_type": "agent_thought", "seq": i})
            await event_buffer.append(session_id, payload, is_terminal=(i == 3))

        mock_db.get_session_doc.return_value = {
            "session_id": session_id,
            "scenario_id": "test-scenario",
            "owner_email": "user@test.com",
        }

        mock_tracker = MagicMock(spec=SSEConnectionTracker)
        mock_tracker.acquire = AsyncMock(return_value=True)
        mock_tracker.release = AsyncMock()

        app.dependency_overrides[get_session_store] = lambda: mock_db
        app.dependency_overrides[get_sse_tracker] = lambda: mock_tracker
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        app.dependency_overrides[get_event_buffer] = lambda: event_buffer
        app.dependency_overrides[get_profile_client] = lambda: mock_profile_client

        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.get(
                    f"/api/v1/negotiation/stream/{session_id}",
                    params={"email": "user@test.com", "last_event_id": 0},
                )

            assert resp.status_code == 200
            sse_events = _parse_sse_events(resp.text)
            assert len(sse_events) == 3
            assert [e["id"] for e in sse_events] == [1, 2, 3]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.integration
class TestStreamSSEContent:
    """Test that SSE content contains expected event types for a completed negotiation."""

    async def test_completed_negotiation_contains_expected_event_types(
        self, mock_db, mock_registry, mock_profile_client,
    ):
        """Mock run_negotiation to yield snapshots producing agent_thought,
        agent_message, and negotiation_complete events. Verify all appear in
        the SSE stream."""
        session_id = "content-session"

        mock_db.get_session_doc.return_value = {
            "session_id": session_id,
            "scenario_id": "test-scenario",
            "owner_email": "user@test.com",
        }

        mock_tracker = MagicMock(spec=SSEConnectionTracker)
        mock_tracker.acquire = AsyncMock(return_value=True)
        mock_tracker.release = AsyncMock()

        event_buffer = SSEEventBuffer()

        app.dependency_overrides[get_session_store] = lambda: mock_db
        app.dependency_overrides[get_sse_tracker] = lambda: mock_tracker
        app.dependency_overrides[get_scenario_registry] = lambda: mock_registry
        app.dependency_overrides[get_event_buffer] = lambda: event_buffer
        app.dependency_overrides[get_profile_client] = lambda: mock_profile_client

        # Craft snapshots that _snapshot_to_events will convert to known event types
        snapshots = [
            # Snapshot 1: negotiator turn → agent_thought + agent_message
            {
                "agent_node": {
                    "history": [{
                        "role": "Buyer",
                        "agent_type": "negotiator",
                        "turn_number": 1,
                        "content": {
                            "inner_thought": "I should start low.",
                            "public_message": "I offer $500k.",
                            "proposed_price": 500000.0,
                        },
                    }],
                    "turn_count": 1,
                    "deal_status": "Negotiating",
                    "current_offer": 500000.0,
                    "warning_count": 0,
                    "total_tokens_used": 100,
                    "agent_calls": [],
                    "agent_states": {},
                }
            },
            # Snapshot 2: regulator → agent_thought + agent_message with status
            {
                "regulator_node": {
                    "history": [{
                        "role": "Regulator",
                        "agent_type": "regulator",
                        "turn_number": 1,
                        "content": {
                            "reasoning": "Offer is within range.",
                            "public_message": "No compliance issues.",
                            "status": "CLEAR",
                        },
                    }],
                    "turn_count": 1,
                    "deal_status": "Negotiating",
                    "warning_count": 0,
                    "total_tokens_used": 200,
                    "agent_calls": [],
                    "agent_states": {},
                }
            },
            # Snapshot 3: dispatcher terminal → negotiation_complete
            {
                "dispatcher": {
                    "history": [],
                    "deal_status": "Agreed",
                    "turn_count": 1,
                    "current_offer": 500000.0,
                    "warning_count": 0,
                    "total_tokens_used": 200,
                    "agent_calls": [],
                    "agent_states": {},
                }
            },
        ]

        async def _mock_run_negotiation(*args, **kwargs):
            for snap in snapshots:
                yield snap

        try:
            with patch("app.routers.negotiation.run_negotiation", _mock_run_negotiation), \
                 patch("app.routers.negotiation.run_evaluation", return_value=_aiter_empty()):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    resp = await client.get(
                        f"/api/v1/negotiation/stream/{session_id}",
                        params={"email": "user@test.com"},
                    )

            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")

            body = resp.text
            sse_events = _parse_sse_events(body)

            # Extract event types from parsed data
            event_types = []
            for evt in sse_events:
                parsed = json.loads(evt["data"])
                event_types.append(parsed["event_type"])

            # Verify all expected event types are present
            assert "agent_thought" in event_types, f"Missing agent_thought in {event_types}"
            assert "agent_message" in event_types, f"Missing agent_message in {event_types}"
            assert "negotiation_complete" in event_types, f"Missing negotiation_complete in {event_types}"

            # Verify negotiation_complete has deal_status = Agreed
            complete_events = [
                json.loads(e["data"]) for e in sse_events
                if json.loads(e["data"])["event_type"] == "negotiation_complete"
            ]
            assert len(complete_events) == 1
            assert complete_events[0]["deal_status"] == "Agreed"

            # Verify agent_thought appears before agent_message for the same agent
            thought_idx = event_types.index("agent_thought")
            message_idx = event_types.index("agent_message")
            assert thought_idx < message_idx, "agent_thought must precede agent_message"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_sse_events(body: str) -> list[dict]:
    """Parse SSE-formatted text into a list of dicts with 'id' and 'data' keys."""
    events = []
    current: dict = {}
    for line in body.split("\n"):
        if line.startswith("id: "):
            current["id"] = int(line[4:])
        elif line.startswith("data: "):
            current["data"] = line[6:]
        elif line == "" and current:
            events.append(current)
            current = {}
    # Catch trailing event without final blank line
    if current and "data" in current:
        events.append(current)
    return events


async def _aiter_empty():
    """Async generator that yields nothing — used to mock run_evaluation."""
    return
    yield  # noqa: unreachable — makes this an async generator
