"""Tests for GET /api/v1/models endpoint.

Validates that the endpoint returns models from app.state.allowed_models
(the verified-working models from the startup availability probe).
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.main import app
from app.orchestrator.availability_checker import AllowedModels, ProbeResult
from app.orchestrator.available_models import AVAILABLE_MODELS, ModelEntry


def _make_allowed(entries: tuple[ModelEntry, ...]) -> AllowedModels:
    """Build an AllowedModels snapshot from the given entries."""
    return AllowedModels(
        entries=entries,
        model_ids=frozenset(e.model_id for e in entries),
        probe_results=tuple(
            ProbeResult(
                model_id=e.model_id,
                family=e.family,
                available=True,
                error=None,
                latency_ms=50.0,
            )
            for e in entries
        ),
        probed_at="2025-01-01T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_models_endpoint_returns_allowed_models():
    """GET /api/v1/models returns entries from app.state.allowed_models."""
    allowed = _make_allowed(AVAILABLE_MODELS)
    with patch.object(app.state, "allowed_models", allowed, create=True):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/models")

    assert resp.status_code == 200
    body = resp.json()

    assert len(body) == len(AVAILABLE_MODELS)
    for item, expected in zip(body, AVAILABLE_MODELS):
        assert item["model_id"] == expected.model_id
        assert item["family"] == expected.family
        assert item["label"] == expected.label


@pytest.mark.asyncio
async def test_models_endpoint_no_duplicates():
    """No duplicate model_ids in the response."""
    allowed = _make_allowed(AVAILABLE_MODELS)
    with patch.object(app.state, "allowed_models", allowed, create=True):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/models")

    body = resp.json()
    model_ids = [item["model_id"] for item in body]
    assert len(model_ids) == len(set(model_ids))


@pytest.mark.asyncio
async def test_models_endpoint_structure():
    """Every item has model_id, family, and label fields."""
    allowed = _make_allowed(AVAILABLE_MODELS)
    with patch.object(app.state, "allowed_models", allowed, create=True):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/models")

    for item in resp.json():
        assert "model_id" in item
        assert "family" in item
        assert "label" in item
        assert isinstance(item["model_id"], str)
        assert isinstance(item["family"], str)
        assert isinstance(item["label"], str)


@pytest.mark.asyncio
async def test_models_endpoint_returns_subset_when_some_unavailable():
    """Endpoint returns only the models in allowed_models, not the full registry."""
    subset = AVAILABLE_MODELS[:2]  # Only first two models "passed" probes
    allowed = _make_allowed(subset)
    with patch.object(app.state, "allowed_models", allowed, create=True):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/models")

    body = resp.json()
    assert len(body) == 2
    assert body[0]["model_id"] == subset[0].model_id
    assert body[1]["model_id"] == subset[1].model_id


@pytest.mark.asyncio
async def test_models_endpoint_empty_when_no_allowed_models_attr():
    """Endpoint returns [] when app.state has no allowed_models (fallback)."""
    # Temporarily remove allowed_models from app.state if it exists
    had_attr = hasattr(app.state, "allowed_models")
    if had_attr:
        saved = app.state.allowed_models
        del app.state.allowed_models
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/models")

        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        if had_attr:
            app.state.allowed_models = saved


@pytest.mark.asyncio
async def test_models_endpoint_empty_when_all_probes_fail():
    """Endpoint returns [] when allowed_models has empty entries (degraded mode)."""
    allowed = _make_allowed(())
    with patch.object(app.state, "allowed_models", allowed, create=True):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/models")

    assert resp.status_code == 200
    assert resp.json() == []
