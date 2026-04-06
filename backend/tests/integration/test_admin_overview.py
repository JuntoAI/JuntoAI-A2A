"""Integration tests for GET /api/v1/admin/overview.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8
"""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from itsdangerous import URLSafeTimedSerializer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "test-admin-secret"
BASE_URL = "http://testserver"
TODAY_STR = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_cookie(password: str = ADMIN_PASSWORD) -> str:
    """Create a properly signed admin_session cookie."""
    s = URLSafeTimedSerializer(password)
    return s.dumps("admin")


def _build_app_with_admin(password: str = ADMIN_PASSWORD):
    """Build a fresh FastAPI app with admin routes registered."""
    import importlib

    with patch.dict(os.environ, {
        "ADMIN_PASSWORD": password,
        "RUN_MODE": "cloud",
        "ENVIRONMENT": "development",
    }):
        import app.config as config_mod
        importlib.reload(config_mod)

        import app.routers.admin as admin_mod
        importlib.reload(admin_mod)

        import app.main as main_mod
        importlib.reload(main_mod)

        return main_mod.app


def _make_firestore_doc(data: dict) -> MagicMock:
    """Create a mock Firestore document snapshot."""
    doc = MagicMock()
    doc.to_dict.return_value = data
    doc.exists = True
    return doc


def _make_async_stream(docs: list[MagicMock]):
    """Create an async iterator that yields mock document snapshots."""
    async def _stream():
        for doc in docs:
            yield doc
    return _stream()


def _make_session_doc(
    session_id: str,
    scenario_id: str = "talent-war",
    deal_status: str = "Agreed",
    turn_count: int = 5,
    total_tokens_used: int = 1000,
    owner_email: str = "user@example.com",
    created_at: str | None = None,
    agent_calls: list[dict] | None = None,
) -> dict:
    """Build a session document dict with sensible defaults."""
    doc = {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "deal_status": deal_status,
        "turn_count": turn_count,
        "total_tokens_used": total_tokens_used,
        "owner_email": owner_email,
        "created_at": created_at or f"{TODAY_STR}T10:00:00+00:00",
    }
    if agent_calls is not None:
        doc["agent_calls"] = agent_calls
    return doc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_instance():
    """Provide a fresh app with admin routes registered."""
    return _build_app_with_admin()


@pytest.fixture()
def mock_firestore_db():
    """Create a mock Firestore AsyncClient."""
    return MagicMock()


@pytest.fixture()
def mock_tracker():
    """Create a mock SSEConnectionTracker."""
    tracker = MagicMock()
    tracker.total_active_connections = 0
    return tracker


# ---------------------------------------------------------------------------
# Test: total_users count (Req 3.1)
# ---------------------------------------------------------------------------


class TestOverviewTotalUsers:
    """Verify total_users reflects the waitlist collection count."""

    async def test_returns_correct_total_users(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.1: total_users = number of docs in waitlist collection."""
        waitlist_docs = [
            _make_firestore_doc({"email": "a@test.com"}),
            _make_firestore_doc({"email": "b@test.com"}),
            _make_firestore_doc({"email": "c@test.com"}),
        ]

        def collection_router(name):
            coll = MagicMock()
            if name == "waitlist":
                coll.stream.return_value = _make_async_stream(waitlist_docs)
            else:
                coll.stream.return_value = _make_async_stream([])
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_users"] == 3


# ---------------------------------------------------------------------------
# Test: simulations_today count (Req 3.2)
# ---------------------------------------------------------------------------


class TestOverviewSimulationsToday:
    """Verify simulations_today only counts sessions with today's UTC date."""

    async def test_counts_only_todays_sessions(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.2: Only sessions with created_at starting with today's date."""
        sessions = [
            _make_session_doc("s1", created_at=f"{TODAY_STR}T08:00:00+00:00"),
            _make_session_doc("s2", created_at=f"{TODAY_STR}T12:00:00+00:00"),
            _make_session_doc("s3", created_at="2020-01-01T00:00:00+00:00"),  # old
        ]
        session_docs = [_make_firestore_doc(s) for s in sessions]

        def collection_router(name):
            coll = MagicMock()
            if name == "waitlist":
                coll.stream.return_value = _make_async_stream([])
            else:
                coll.stream.return_value = _make_async_stream(session_docs)
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        assert resp.json()["simulations_today"] == 2


# ---------------------------------------------------------------------------
# Test: ai_tokens_today (Req 3.4)
# ---------------------------------------------------------------------------


class TestOverviewAiTokensToday:
    """Verify ai_tokens_today sums total_tokens_used for today's sessions only."""

    async def test_sums_tokens_for_today_only(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.4: Sum total_tokens_used across sessions created today."""
        sessions = [
            _make_session_doc("s1", total_tokens_used=500, created_at=f"{TODAY_STR}T08:00:00+00:00"),
            _make_session_doc("s2", total_tokens_used=300, created_at=f"{TODAY_STR}T12:00:00+00:00"),
            _make_session_doc("s3", total_tokens_used=9999, created_at="2020-01-01T00:00:00+00:00"),
        ]
        session_docs = [_make_firestore_doc(s) for s in sessions]

        def collection_router(name):
            coll = MagicMock()
            if name == "waitlist":
                coll.stream.return_value = _make_async_stream([])
            else:
                coll.stream.return_value = _make_async_stream(session_docs)
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        assert resp.json()["ai_tokens_today"] == 800


# ---------------------------------------------------------------------------
# Test: active_sse_connections (Req 3.3)
# ---------------------------------------------------------------------------


class TestOverviewActiveSSE:
    """Verify active_sse_connections comes from the SSE tracker."""

    async def test_returns_tracker_value(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.3: active_sse_connections = tracker.total_active_connections."""
        mock_tracker.total_active_connections = 7

        def collection_router(name):
            coll = MagicMock()
            coll.stream.return_value = _make_async_stream([])
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        assert resp.json()["active_sse_connections"] == 7


# ---------------------------------------------------------------------------
# Test: scenario_analytics (Req 3.5)
# ---------------------------------------------------------------------------


class TestOverviewScenarioAnalytics:
    """Verify scenario analytics: run_count and avg_tokens_used per scenario."""

    async def test_correct_scenario_analytics(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.5: Per-scenario run_count and avg_tokens_used."""
        sessions = [
            _make_session_doc("s1", scenario_id="talent-war", total_tokens_used=100),
            _make_session_doc("s2", scenario_id="talent-war", total_tokens_used=200),
            _make_session_doc("s3", scenario_id="m-and-a", total_tokens_used=600),
        ]
        session_docs = [_make_firestore_doc(s) for s in sessions]

        def collection_router(name):
            coll = MagicMock()
            if name == "waitlist":
                coll.stream.return_value = _make_async_stream([])
            else:
                coll.stream.return_value = _make_async_stream(session_docs)
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        analytics = {a["scenario_id"]: a for a in resp.json()["scenario_analytics"]}

        assert analytics["talent-war"]["run_count"] == 2
        assert analytics["talent-war"]["avg_tokens_used"] == pytest.approx(150.0)
        assert analytics["m-and-a"]["run_count"] == 1
        assert analytics["m-and-a"]["avg_tokens_used"] == pytest.approx(600.0)


# ---------------------------------------------------------------------------
# Test: model_performance (Req 3.6)
# ---------------------------------------------------------------------------


class TestOverviewModelPerformance:
    """Verify model performance metrics from agent_calls telemetry."""

    async def test_correct_model_performance(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.6: avg latency, avg tokens, error count per model."""
        sessions = [
            _make_session_doc("s1", agent_calls=[
                {"model_id": "gemini-flash", "latency_ms": 100, "input_tokens": 50, "output_tokens": 30, "error": False},
                {"model_id": "gemini-flash", "latency_ms": 200, "input_tokens": 60, "output_tokens": 40, "error": True},
                {"model_id": "claude-sonnet", "latency_ms": 300, "input_tokens": 80, "output_tokens": 50, "error": False},
            ]),
            _make_session_doc("s2", agent_calls=[
                {"model_id": "claude-sonnet", "latency_ms": 500, "input_tokens": 120, "output_tokens": 70, "error": True},
            ]),
        ]
        session_docs = [_make_firestore_doc(s) for s in sessions]

        def collection_router(name):
            coll = MagicMock()
            if name == "waitlist":
                coll.stream.return_value = _make_async_stream([])
            else:
                coll.stream.return_value = _make_async_stream(session_docs)
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        perf = {m["model_id"]: m for m in resp.json()["model_performance"]}

        # gemini-flash: 2 calls, avg latency (100+200)/2=150, avg input (50+60)/2=55, avg output (30+40)/2=35, 1 error
        assert perf["gemini-flash"]["total_calls"] == 2
        assert perf["gemini-flash"]["avg_latency_ms"] == pytest.approx(150.0)
        assert perf["gemini-flash"]["avg_input_tokens"] == pytest.approx(55.0)
        assert perf["gemini-flash"]["avg_output_tokens"] == pytest.approx(35.0)
        assert perf["gemini-flash"]["error_count"] == 1

        # claude-sonnet: 2 calls, avg latency (300+500)/2=400, avg input (80+120)/2=100, avg output (50+70)/2=60, 1 error
        assert perf["claude-sonnet"]["total_calls"] == 2
        assert perf["claude-sonnet"]["avg_latency_ms"] == pytest.approx(400.0)
        assert perf["claude-sonnet"]["avg_input_tokens"] == pytest.approx(100.0)
        assert perf["claude-sonnet"]["avg_output_tokens"] == pytest.approx(60.0)
        assert perf["claude-sonnet"]["error_count"] == 1

    async def test_sessions_without_agent_calls_excluded(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.6: Sessions lacking agent_calls are excluded from model perf."""
        sessions = [
            _make_session_doc("s1"),  # no agent_calls key
            _make_session_doc("s2", agent_calls=[
                {"model_id": "gemini-flash", "latency_ms": 100, "input_tokens": 50, "output_tokens": 30, "error": False},
            ]),
        ]
        session_docs = [_make_firestore_doc(s) for s in sessions]

        def collection_router(name):
            coll = MagicMock()
            if name == "waitlist":
                coll.stream.return_value = _make_async_stream([])
            else:
                coll.stream.return_value = _make_async_stream(session_docs)
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        perf = resp.json()["model_performance"]
        assert len(perf) == 1
        assert perf[0]["model_id"] == "gemini-flash"
        assert perf[0]["total_calls"] == 1


# ---------------------------------------------------------------------------
# Test: recent_simulations (Req 3.7)
# ---------------------------------------------------------------------------


class TestOverviewRecentSimulations:
    """Verify recent simulations feed: last 50, ordered by created_at desc."""

    async def test_returns_last_50_ordered_desc(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.7: Last 50 sessions ordered by created_at descending."""
        # Create 55 sessions with sequential timestamps
        sessions = [
            _make_session_doc(
                f"s{i:03d}",
                created_at=f"2025-01-01T{i:02d}:00:00+00:00",
            )
            for i in range(55)
        ]
        session_docs = [_make_firestore_doc(s) for s in sessions]

        def collection_router(name):
            coll = MagicMock()
            if name == "waitlist":
                coll.stream.return_value = _make_async_stream([])
            else:
                coll.stream.return_value = _make_async_stream(session_docs)
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        recent = resp.json()["recent_simulations"]
        assert len(recent) == 50

        # Verify descending order
        timestamps = [r["created_at"] for r in recent]
        assert timestamps == sorted(timestamps, reverse=True)

        # The most recent session should be s054 (hour 54 — but we only have 0-54)
        assert recent[0]["session_id"] == "s054"

    async def test_recent_simulations_fields(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.7: Each entry has session_id, scenario_id, deal_status, turn_count, total_tokens_used, owner_email."""
        sessions = [
            _make_session_doc(
                "sess-abc",
                scenario_id="talent-war",
                deal_status="Agreed",
                turn_count=8,
                total_tokens_used=2500,
                owner_email="admin@test.com",
            ),
        ]
        session_docs = [_make_firestore_doc(s) for s in sessions]

        def collection_router(name):
            coll = MagicMock()
            if name == "waitlist":
                coll.stream.return_value = _make_async_stream([])
            else:
                coll.stream.return_value = _make_async_stream(session_docs)
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        entry = resp.json()["recent_simulations"][0]
        assert entry["session_id"] == "sess-abc"
        assert entry["scenario_id"] == "talent-war"
        assert entry["deal_status"] == "Agreed"
        assert entry["turn_count"] == 8
        assert entry["total_tokens_used"] == 2500
        assert entry["owner_email"] == "admin@test.com"


# ---------------------------------------------------------------------------
# Test: empty collections (Req 3.8)
# ---------------------------------------------------------------------------


class TestOverviewEmptyCollections:
    """Verify overview returns zeros/empty lists when collections are empty."""

    async def test_empty_collections_return_zeros(self, app_instance, mock_firestore_db, mock_tracker):
        """Req 3.8: All metrics zero/empty when no data exists."""
        mock_tracker.total_active_connections = 0

        def collection_router(name):
            coll = MagicMock()
            coll.stream.return_value = _make_async_stream([])
            return coll

        mock_firestore_db.collection.side_effect = collection_router

        with patch("app.db.get_firestore_db", return_value=mock_firestore_db), \
             patch("app.middleware.get_sse_tracker", return_value=mock_tracker):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/overview",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_users"] == 0
        assert data["simulations_today"] == 0
        assert data["active_sse_connections"] == 0
        assert data["ai_tokens_today"] == 0
        assert data["scenario_analytics"] == []
        assert data["model_performance"] == []
        assert data["recent_simulations"] == []
