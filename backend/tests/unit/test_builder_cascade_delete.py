"""Unit tests for enhanced DELETE /builder/scenarios/{scenario_id} with cascade.

# Feature: 320_scenario-management
# Requirements: 1.1, 1.2, 1.3, 1.4, 1.5

Tests cover:
- Cascade with 0 sessions — DELETE succeeds, deleted_sessions_count=0
- Cascade with 1 session — DELETE succeeds, deleted_sessions_count=1
- Cascade with N sessions (3) — DELETE succeeds, deleted_sessions_count=3
- 404 scenario not found — store.get returns None
- 500 on session deletion failure — delete_session raises exception mid-cascade
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.db import get_custom_scenario_store, get_session_store
from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_store():
    store = MagicMock()
    store.get = AsyncMock(
        return_value={"scenario_id": "sc-1", "scenario_json": {}}
    )
    store.delete = AsyncMock(return_value=True)
    return store


@pytest.fixture()
def mock_session_store():
    ss = MagicMock()
    ss.list_sessions_by_scenario = AsyncMock(return_value=[])
    ss.delete_session = AsyncMock()
    return ss


# ---------------------------------------------------------------------------
# Tests — Enhanced DELETE with cascade
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cascade_delete_zero_sessions(mock_store, mock_session_store):
    """DELETE succeeds with deleted_sessions_count=0 when no sessions exist."""
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.delete(
                "/api/v1/builder/scenarios/sc-1",
                params={"email": "user@example.com"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scenario_id"] == "sc-1"
        assert body["deleted_sessions_count"] == 0
        mock_store.delete.assert_awaited_once_with("user@example.com", "sc-1")
        mock_session_store.delete_session.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cascade_delete_one_session(mock_store, mock_session_store):
    """DELETE succeeds with deleted_sessions_count=1 when one session exists."""
    mock_session_store.list_sessions_by_scenario = AsyncMock(
        return_value=[{"session_id": "sess-1"}]
    )
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.delete(
                "/api/v1/builder/scenarios/sc-1",
                params={"email": "user@example.com"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scenario_id"] == "sc-1"
        assert body["deleted_sessions_count"] == 1
        mock_session_store.delete_session.assert_awaited_once_with("sess-1")
        mock_store.delete.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cascade_delete_n_sessions(mock_store, mock_session_store):
    """DELETE succeeds with deleted_sessions_count=3 when three sessions exist."""
    mock_session_store.list_sessions_by_scenario = AsyncMock(
        return_value=[
            {"session_id": "sess-1"},
            {"session_id": "sess-2"},
            {"session_id": "sess-3"},
        ]
    )
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.delete(
                "/api/v1/builder/scenarios/sc-1",
                params={"email": "user@example.com"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scenario_id"] == "sc-1"
        assert body["deleted_sessions_count"] == 3
        assert mock_session_store.delete_session.await_count == 3
        mock_store.delete.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cascade_delete_scenario_not_found(mock_session_store):
    """DELETE returns 404 when scenario does not exist or is not owned."""
    store = MagicMock()
    store.get = AsyncMock(return_value=None)
    app.dependency_overrides[get_custom_scenario_store] = lambda: store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.delete(
                "/api/v1/builder/scenarios/nonexistent",
                params={"email": "user@example.com"},
            )
        assert resp.status_code == 404
        assert "detail" in resp.json()
        # Session store should never be called if scenario doesn't exist
        mock_session_store.list_sessions_by_scenario.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cascade_delete_session_failure_returns_500(
    mock_store, mock_session_store
):
    """DELETE returns 500 when delete_session raises an exception mid-cascade."""
    mock_session_store.list_sessions_by_scenario = AsyncMock(
        return_value=[
            {"session_id": "sess-1"},
            {"session_id": "sess-2"},
            {"session_id": "sess-3"},
        ]
    )
    # First call succeeds, second raises
    mock_session_store.delete_session = AsyncMock(
        side_effect=[None, RuntimeError("Firestore unavailable"), None]
    )
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.delete(
                "/api/v1/builder/scenarios/sc-1",
                params={"email": "user@example.com"},
            )
        assert resp.status_code == 500
        body = resp.json()
        assert "sess-2" in body["detail"]
        # Scenario should NOT be deleted when cascade fails
        mock_store.delete.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
