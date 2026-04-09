"""Unit tests for GET /builder/scenarios/{scenario_id}/sessions/count endpoint.

# Feature: 320_scenario-management
# Requirements: 2.1, 6.1

Tests cover:
- Returns {count: 0} when scenario has no sessions
- Returns {count: N} when scenario has N sessions
- 404 when scenario not found or not owned
- 401 when email is missing or empty
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
    return store


@pytest.fixture()
def mock_session_store():
    ss = MagicMock()
    ss.list_sessions_by_scenario = AsyncMock(return_value=[])
    return ss


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_count_zero(mock_store, mock_session_store):
    """GET sessions/count returns {count: 0} when no sessions exist."""
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/builder/scenarios/sc-1/sessions/count",
                params={"email": "user@example.com"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"count": 0}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_count_multiple(mock_store, mock_session_store):
    """GET sessions/count returns {count: N} when N sessions exist."""
    mock_session_store.list_sessions_by_scenario = AsyncMock(
        return_value=[
            {"session_id": "s1"},
            {"session_id": "s2"},
            {"session_id": "s3"},
        ]
    )
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/builder/scenarios/sc-1/sessions/count",
                params={"email": "user@example.com"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"count": 3}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_count_not_found(mock_session_store):
    """GET sessions/count returns 404 when scenario not found or not owned."""
    store = MagicMock()
    store.get = AsyncMock(return_value=None)
    app.dependency_overrides[get_custom_scenario_store] = lambda: store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/builder/scenarios/nonexistent/sessions/count",
                params={"email": "user@example.com"},
            )
        assert resp.status_code == 404
        assert "detail" in resp.json()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_count_missing_email(mock_store, mock_session_store):
    """GET sessions/count returns 401 when email is empty."""
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/builder/scenarios/sc-1/sessions/count",
                params={"email": ""},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_count_no_email_param(mock_store, mock_session_store):
    """GET sessions/count returns 401 when email param is omitted."""
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/builder/scenarios/sc-1/sessions/count",
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
