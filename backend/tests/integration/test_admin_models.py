"""Integration tests for GET /api/v1/admin/models.

Validates: Requirements 9.4, 9.5
"""

import os
from unittest.mock import patch

import httpx
import pytest
from itsdangerous import URLSafeTimedSerializer

from app.orchestrator.availability_checker import AllowedModels, ProbeResult
from app.orchestrator.available_models import ModelEntry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "test-admin-secret"
BASE_URL = "http://testserver"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_cookie(password: str = ADMIN_PASSWORD) -> str:
    """Create a properly signed admin_session cookie."""
    s = URLSafeTimedSerializer(password)
    return s.dumps("admin")


def _build_app_with_admin(password: str = ADMIN_PASSWORD):
    """Build a fresh FastAPI app with admin routes registered (cloud mode)."""
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


def _make_allowed_models(
    probe_results: list[ProbeResult] | None = None,
    probed_at: str = "2025-01-15T10:30:00Z",
) -> AllowedModels:
    """Build an AllowedModels instance from probe results."""
    if probe_results is None:
        probe_results = [
            ProbeResult("gemini-3-flash-preview", "gemini", True, None, 234.5),
            ProbeResult("claude-sonnet-4", "claude", False, "TimeoutError: probe exceeded 15s", 15000.0),
        ]
    passing_ids = frozenset(r.model_id for r in probe_results if r.available)
    # Build entries from passing probes only
    entries = tuple(
        ModelEntry(r.model_id, r.family, r.model_id)
        for r in probe_results
        if r.available
    )
    return AllowedModels(
        entries=entries,
        model_ids=passing_ids,
        probe_results=tuple(probe_results),
        probed_at=probed_at,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_instance():
    """Provide a fresh app with admin routes registered."""
    return _build_app_with_admin()


# ---------------------------------------------------------------------------
# Auth gating (Req 9.4)
# ---------------------------------------------------------------------------


class TestAdminModelsAuth:
    """Verify the /admin/models endpoint requires authentication."""

    async def test_missing_cookie_returns_401(self, app_instance):
        """Req 9.4: No admin_session cookie → 401 Unauthorized."""
        app_instance.state.allowed_models = _make_allowed_models()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url=BASE_URL,
        ) as client:
            resp = await client.get("/api/v1/admin/models")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"

    async def test_invalid_cookie_returns_401(self, app_instance):
        """Req 9.4: Tampered cookie → 401 Unauthorized."""
        app_instance.state.allowed_models = _make_allowed_models()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url=BASE_URL,
        ) as client:
            resp = await client.get(
                "/api/v1/admin/models",
                cookies={"admin_session": "garbage-token"},
            )
        assert resp.status_code == 401

    async def test_valid_cookie_returns_200(self, app_instance):
        """Req 9.4: Valid admin_session cookie → 200 with model data."""
        app_instance.state.allowed_models = _make_allowed_models()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url=BASE_URL,
        ) as client:
            resp = await client.get(
                "/api/v1/admin/models",
                cookies={"admin_session": _make_valid_cookie()},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 503 when probes not yet available (Req 9.5)
# ---------------------------------------------------------------------------


class TestAdminModelsNotReady:
    """Verify 503 when allowed_models is not set on app.state."""

    async def test_returns_503_when_allowed_models_not_set(self, app_instance):
        """Req 9.5: Probes not completed → 503."""
        # Ensure allowed_models is NOT set
        if hasattr(app_instance.state, "allowed_models"):
            del app_instance.state.allowed_models
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url=BASE_URL,
        ) as client:
            resp = await client.get(
                "/api/v1/admin/models",
                cookies={"admin_session": _make_valid_cookie()},
            )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Probe results not yet available"


# ---------------------------------------------------------------------------
# Response shape with mock probe results (Req 9.1, 9.2, 9.3)
# ---------------------------------------------------------------------------


class TestAdminModelsResponseShape:
    """Verify the response shape matches the design doc."""

    async def test_response_contains_summary_counts(self, app_instance):
        """Req 9.3: Response includes total_registered, total_available, total_unavailable."""
        probes = [
            ProbeResult("gemini-3-flash-preview", "gemini", True, None, 200.0),
            ProbeResult("gemini-3.1-pro-preview", "gemini", True, None, 350.0),
            ProbeResult("claude-sonnet-4", "claude", False, "ConnectionError: refused", 100.0),
        ]
        app_instance.state.allowed_models = _make_allowed_models(probes)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url=BASE_URL,
        ) as client:
            resp = await client.get(
                "/api/v1/admin/models",
                cookies={"admin_session": _make_valid_cookie()},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_registered"] == 3
        assert data["total_available"] == 2
        assert data["total_unavailable"] == 1
        assert data["probed_at"] == "2025-01-15T10:30:00Z"

    async def test_response_model_entries_shape(self, app_instance):
        """Req 9.1, 9.2: Each model entry has model_id, family, label, status, error, latency_ms."""
        probes = [
            ProbeResult("gemini-3-flash-preview", "gemini", True, None, 234.5),
            ProbeResult("claude-sonnet-4", "claude", False, "TimeoutError: probe exceeded 15s", 15000.0),
        ]
        app_instance.state.allowed_models = _make_allowed_models(probes)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url=BASE_URL,
        ) as client:
            resp = await client.get(
                "/api/v1/admin/models",
                cookies={"admin_session": _make_valid_cookie()},
            )

        data = resp.json()
        models = data["models"]
        assert len(models) == 2

        available_model = next(m for m in models if m["model_id"] == "gemini-3-flash-preview")
        assert available_model["family"] == "gemini"
        assert available_model["status"] == "available"
        assert available_model["error"] is None
        assert available_model["latency_ms"] == pytest.approx(234.5)
        assert "label" in available_model

        unavailable_model = next(m for m in models if m["model_id"] == "claude-sonnet-4")
        assert unavailable_model["family"] == "claude"
        assert unavailable_model["status"] == "unavailable"
        assert unavailable_model["error"] == "TimeoutError: probe exceeded 15s"
        assert unavailable_model["latency_ms"] == pytest.approx(15000.0)

    async def test_all_models_unavailable_degraded(self, app_instance):
        """Req 9.6: When all probes fail, all models shown as unavailable."""
        probes = [
            ProbeResult("gemini-3-flash-preview", "gemini", False, "ConnectionError", 50.0),
            ProbeResult("claude-sonnet-4", "claude", False, "TimeoutError", 15000.0),
        ]
        app_instance.state.allowed_models = _make_allowed_models(probes)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url=BASE_URL,
        ) as client:
            resp = await client.get(
                "/api/v1/admin/models",
                cookies={"admin_session": _make_valid_cookie()},
            )

        data = resp.json()
        assert data["total_available"] == 0
        assert data["total_unavailable"] == 2
        assert all(m["status"] == "unavailable" for m in data["models"])
        assert all(m["error"] is not None for m in data["models"])
