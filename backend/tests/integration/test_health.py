"""Integration tests for GET /api/v1/health endpoint."""

import httpx
import pytest

from app.main import app


@pytest.fixture()
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


class TestHealthEndpoint:
    async def test_returns_200(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    async def test_response_body(self, client):
        resp = await client.get("/api/v1/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["version"] == "0.1.0"
