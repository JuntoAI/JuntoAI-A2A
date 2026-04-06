"""Tests for GET /api/v1/models endpoint.

Validates that the endpoint returns the canonical list of available models
from the available_models registry.
"""

from __future__ import annotations

import httpx
import pytest

from app.main import app
from app.orchestrator.available_models import AVAILABLE_MODELS


@pytest.mark.asyncio
async def test_models_endpoint_returns_canonical_list():
    """GET /api/v1/models returns all entries from AVAILABLE_MODELS."""
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
