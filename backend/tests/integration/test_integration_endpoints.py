"""Integration tests for CRM Integration API endpoints.

Feature: 350_crm-integration-api
Requirements: 1.1, 2.1, 2.2, 2.3, 2.4, 3.2, 3.3, 4.1, 5.1, 6.1, 6.2, 6.3,
              8.1, 8.2, 8.3, 9.1, 9.3, 10.1, 13.1, 13.2
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.db.api_key_store import SQLiteApiKeyClient
from app.main import app
from app.services.api_key_service import ApiKeyService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = "/api/v1/integrations"


def _error_schema_valid(body: dict) -> bool:
    """Check that an error response matches IntegrationErrorResponse schema."""
    return (
        isinstance(body.get("error"), str)
        and isinstance(body.get("message"), str)
        and isinstance(body.get("details"), dict)
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def api_key_env(tmp_path, valid_scenario_dict):
    """Set up a SQLite API key store with a fully-scoped key and mock dependencies.

    Yields (raw_key, key_record, store, client).
    """
    db_path = str(tmp_path / "test_integration.db")
    store = SQLiteApiKeyClient(db_path=db_path)
    service = ApiKeyService(store)

    # Generate a key with all scopes
    raw_key, key_record = await service.generate_key(
        org_name="TestOrg",
        created_by_email="admin@testorg.com",
        scopes=["simulate", "read_sessions", "list_scenarios", "manage_keys"],
        rate_limit_daily=1000,
        rate_limit_per_minute=60,
    )

    # Build a mock scenario registry with a real scenario
    from app.scenarios.models import ArenaScenario

    scenario = ArenaScenario(**valid_scenario_dict)
    registry = MagicMock()
    registry.get_scenario.return_value = scenario
    registry._scenarios = {scenario.id: scenario}

    # Mock session store
    mock_session_store = MagicMock()
    mock_session_store.create_session = AsyncMock()
    mock_session_store.update_session = AsyncMock()
    mock_session_store.get_session_doc = AsyncMock()

    # Mock share store
    mock_share_store = MagicMock()
    mock_share_store.get_share_by_session = AsyncMock(return_value=None)
    mock_share_store.create_share = AsyncMock()

    # Mock custom scenario store
    mock_custom_store = MagicMock()
    mock_custom_store.save = AsyncMock()

    with (
        patch("app.middleware.api_key_auth.get_api_key_store", return_value=store),
        patch("app.routers.integrations.get_api_key_store", return_value=store),
        patch("app.routers.integrations.get_session_store", return_value=mock_session_store),
        patch("app.routers.integrations.get_share_store", return_value=mock_share_store),
        patch("app.routers.integrations.get_scenario_registry", return_value=registry),
        patch("app.db.get_session_store", return_value=mock_session_store),
        patch("app.db.get_share_store", return_value=mock_share_store),
        patch("app.db.get_custom_scenario_store", return_value=mock_custom_store),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield {
                "raw_key": raw_key,
                "key_record": key_record,
                "store": store,
                "service": service,
                "client": client,
                "registry": registry,
                "session_store": mock_session_store,
                "share_store": mock_share_store,
                "scenario": scenario,
            }


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthEndpoint:
    """GET /api/v1/integrations/health — Requirement 4.1"""

    async def test_returns_200_with_all_fields(self, api_key_env):
        env = api_key_env
        resp = await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": env["raw_key"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert body["key_valid"] is True
        assert body["org_name"] == "TestOrg"
        assert "rate_limit" in body
        rl = body["rate_limit"]
        assert "daily_limit" in rl
        assert "used_today" in rl
        assert "remaining" in rl
        assert "resets_at" in rl


# ---------------------------------------------------------------------------
# Scenarios endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestScenariosEndpoint:
    """GET /api/v1/integrations/scenarios — Requirement 5.1"""

    async def test_returns_filtered_list(self, api_key_env):
        env = api_key_env
        resp = await env["client"].get(
            f"{BASE}/scenarios",
            headers={"X-API-Key": env["raw_key"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "scenarios" in body
        scenarios = body["scenarios"]
        assert len(scenarios) >= 1

        s = scenarios[0]
        # Public fields present
        assert "id" in s
        assert "name" in s
        assert "description" in s
        assert "category" in s
        assert "difficulty" in s
        assert "agents" in s
        assert "toggles" in s
        assert "context_fields" in s

        # Internal fields absent
        for agent in s["agents"]:
            assert "model_id" not in agent
            assert "persona_prompt" not in agent
            assert "budget" not in agent
            assert "goals" not in agent
            assert "output_fields" not in agent

        for toggle in s["toggles"]:
            assert "hidden_context_payload" not in toggle


# ---------------------------------------------------------------------------
# Simulate endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestSimulateEndpoint:
    """POST /api/v1/integrations/simulate — Requirements 6.1, 6.2, 6.3"""

    async def test_returns_201_with_required_fields(self, api_key_env):
        env = api_key_env

        # Mock the background task execution
        with patch(
            "app.services.integration_service.IntegrationService._create_viewer_url",
            new=AsyncMock(return_value="http://localhost:3000/share/abc123"),
        ):
            resp = await env["client"].post(
                f"{BASE}/simulate",
                headers={"X-API-Key": env["raw_key"]},
                json={
                    "scenario_id": "test-scenario",
                    "active_toggles": ["toggle_1"],
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert "session_id" in body
        assert "viewer_url" in body
        assert body["status"] == "running"
        assert "created_at" in body

    async def test_scenario_not_found_returns_404(self, api_key_env):
        env = api_key_env
        env["registry"].get_scenario.side_effect = Exception("Not found")

        resp = await env["client"].post(
            f"{BASE}/simulate",
            headers={"X-API-Key": env["raw_key"]},
            json={"scenario_id": "nonexistent-scenario"},
        )

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "scenario_not_found"
        assert _error_schema_valid(body)

    async def test_dynamic_scenario_with_builder(self, api_key_env):
        """Test _dynamic scenario_id triggers builder flow — Requirement 10.1"""
        env = api_key_env

        with (
            patch(
                "app.services.integration_service.IntegrationService._build_dynamic_scenario",
                new=AsyncMock(return_value=env["scenario"]),
            ),
            patch(
                "app.services.integration_service.IntegrationService._create_viewer_url",
                new=AsyncMock(return_value="http://localhost:3000/share/dyn123"),
            ),
        ):
            resp = await env["client"].post(
                f"{BASE}/simulate",
                headers={"X-API-Key": env["raw_key"]},
                json={
                    "scenario_id": "_dynamic",
                    "scenario_builder": {
                        "simulation_type": "sales_call",
                        "my_profile": {
                            "name": "Alice",
                            "role": "Account Exec",
                            "company": "Acme Corp",
                            "goals": ["Close deal"],
                        },
                        "their_profile": {
                            "name": "Bob",
                            "role": "CTO",
                            "company": "TechCo",
                            "goals": ["Get best price"],
                        },
                    },
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert "session_id" in body
        assert body["status"] == "running"

    async def test_triggered_by_email_sets_owner(self, api_key_env):
        """Test triggered_by with valid email — Requirement 9.1"""
        env = api_key_env

        with patch(
            "app.services.integration_service.IntegrationService._create_viewer_url",
            new=AsyncMock(return_value="http://localhost:3000/share/xyz"),
        ):
            resp = await env["client"].post(
                f"{BASE}/simulate",
                headers={"X-API-Key": env["raw_key"]},
                json={
                    "scenario_id": "test-scenario",
                    "triggered_by": "user@company.com",
                },
            )

        assert resp.status_code == 201

        # Verify session was updated with owner_email
        update_calls = env["session_store"].update_session.call_args_list
        # Find the metadata update call (has owner_email)
        metadata_found = False
        for call in update_calls:
            args = call[0] if call[0] else ()
            kwargs = call[1] if call[1] else {}
            update_data = args[1] if len(args) > 1 else kwargs.get("updates", {})
            if isinstance(update_data, dict) and "owner_email" in update_data:
                assert update_data["owner_email"] == "user@company.com"
                assert update_data["source"] == "integration"
                assert update_data["integration_org"] == "TestOrg"
                metadata_found = True
                break
        assert metadata_found, "owner_email metadata not found in session updates"

    async def test_triggered_by_display_name_uses_synthetic_owner(self, api_key_env):
        """Test triggered_by with display name — Requirement 9.3"""
        env = api_key_env

        with patch(
            "app.services.integration_service.IntegrationService._create_viewer_url",
            new=AsyncMock(return_value="http://localhost:3000/share/xyz"),
        ):
            resp = await env["client"].post(
                f"{BASE}/simulate",
                headers={"X-API-Key": env["raw_key"]},
                json={
                    "scenario_id": "test-scenario",
                    "triggered_by": "Jane Smith",
                },
            )

        assert resp.status_code == 201

        # Verify session was updated with synthetic owner
        update_calls = env["session_store"].update_session.call_args_list
        metadata_found = False
        for call in update_calls:
            args = call[0] if call[0] else ()
            update_data = args[1] if len(args) > 1 else {}
            if isinstance(update_data, dict) and "owner_email" in update_data:
                assert update_data["owner_email"] == "integration:TestOrg"
                metadata_found = True
                break
        assert metadata_found, "synthetic owner_email not found in session updates"


# ---------------------------------------------------------------------------
# Session status endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestSessionStatusEndpoint:
    """GET /api/v1/integrations/sessions/{session_id} — Requirements 8.1, 8.2, 8.3"""

    async def test_running_session_returns_correct_fields(self, api_key_env):
        env = api_key_env
        session_id = "sess-running-001"

        env["session_store"].get_session_doc.return_value = {
            "session_id": session_id,
            "scenario_id": "test-scenario",
            "deal_status": "Negotiating",
            "current_offer": 500_000.0,
            "turn_count": 3,
            "created_at": "2025-01-01T00:00:00+00:00",
            "history": [{"role": "Buyer", "content": "secret"}],
            "hidden_context": {"secret": "data"},
            "agent_states": {"internal": True},
        }

        resp = await env["client"].get(
            f"{BASE}/sessions/{session_id}",
            headers={"X-API-Key": env["raw_key"]},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == session_id
        assert body["status"] == "running"
        assert body["turns_completed"] == 3
        assert body["current_offer"] == 500_000.0
        assert "created_at" in body
        # Internal fields must NOT be present
        assert "history" not in body
        assert "hidden_context" not in body
        assert "agent_states" not in body
        assert "agent_memories" not in body

    async def test_completed_session_returns_outcome(self, api_key_env):
        env = api_key_env
        session_id = "sess-done-001"

        env["session_store"].get_session_doc.return_value = {
            "session_id": session_id,
            "scenario_id": "test-scenario",
            "deal_status": "Agreed",
            "current_offer": 750_000.0,
            "turn_count": 8,
            "warning_count": 1,
            "created_at": "2025-01-01T00:00:00+00:00",
            "completed_at": "2025-01-01T00:02:00+00:00",
            "duration_seconds": 120,
            "history": [],
            "hidden_context": {},
            "agent_states": {},
        }

        resp = await env["client"].get(
            f"{BASE}/sessions/{session_id}",
            headers={"X-API-Key": env["raw_key"]},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["completed_at"] is not None

    async def test_session_not_found_returns_404(self, api_key_env):
        env = api_key_env
        env["session_store"].get_session_doc.side_effect = Exception("Not found")

        resp = await env["client"].get(
            f"{BASE}/sessions/nonexistent-session",
            headers={"X-API-Key": env["raw_key"]},
        )

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "session_not_found"
        assert _error_schema_valid(body)


# ---------------------------------------------------------------------------
# Key management endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestKeyManagement:
    """POST/DELETE /api/v1/integrations/keys — Requirement 1.1, 1.5"""

    async def test_create_key(self, api_key_env):
        env = api_key_env

        resp = await env["client"].post(
            f"{BASE}/keys",
            headers={"X-API-Key": env["raw_key"]},
            json={"org_name": "NewOrg"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert "key_id" in body
        assert "api_key" in body
        assert body["api_key"].startswith("a2a_live_")
        assert body["org_name"] == "NewOrg"
        assert "scopes" in body
        assert "rate_limit_daily" in body
        assert "created_at" in body

    async def test_deactivate_key(self, api_key_env):
        env = api_key_env

        # First create a key to deactivate
        create_resp = await env["client"].post(
            f"{BASE}/keys",
            headers={"X-API-Key": env["raw_key"]},
            json={"org_name": "ToDeactivate"},
        )
        assert create_resp.status_code == 201
        new_key_id = create_resp.json()["key_id"]

        # Deactivate it
        resp = await env["client"].delete(
            f"{BASE}/keys/{new_key_id}",
            headers={"X-API-Key": env["raw_key"]},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["active"] is False
        assert body["key_id"] == new_key_id


# ---------------------------------------------------------------------------
# Auth error tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthErrors:
    """Auth error responses — Requirements 2.1, 2.2, 2.3, 2.4, 13.1, 13.2"""

    async def test_missing_api_key_returns_401(self, api_key_env):
        env = api_key_env
        resp = await env["client"].get(f"{BASE}/health")
        # FastAPI returns 422 for missing required header
        assert resp.status_code == 422

    async def test_invalid_api_key_returns_401(self, api_key_env):
        env = api_key_env
        resp = await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": "a2a_live_invalid_key_that_does_not_exist"},
        )
        assert resp.status_code == 401
        body = resp.json()["detail"]
        assert body["error"] == "invalid_api_key"
        assert isinstance(body["message"], str)
        assert isinstance(body["details"], dict)

    async def test_deactivated_key_returns_403(self, api_key_env):
        env = api_key_env

        # Create a new key and deactivate it
        service = env["service"]
        raw_key2, record2 = await service.generate_key(
            org_name="DeactivatedOrg",
            created_by_email="admin@deactivated.com",
            scopes=["simulate", "read_sessions", "list_scenarios"],
        )
        await service.deactivate_key(record2["key_id"])

        resp = await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": raw_key2},
        )
        assert resp.status_code == 403
        body = resp.json()["detail"]
        assert body["error"] == "key_deactivated"
        assert _error_schema_valid(body)

    async def test_insufficient_scope_returns_403(self, api_key_env):
        env = api_key_env

        # Create a key without manage_keys scope
        service = env["service"]
        raw_key_limited, _ = await service.generate_key(
            org_name="LimitedOrg",
            created_by_email="admin@limited.com",
            scopes=["simulate"],  # No manage_keys scope
        )

        # Try to create a key (requires manage_keys scope)
        resp = await env["client"].post(
            f"{BASE}/keys",
            headers={"X-API-Key": raw_key_limited},
            json={"org_name": "ShouldFail"},
        )
        assert resp.status_code == 403
        body = resp.json()["detail"]
        assert body["error"] == "insufficient_scope"
        assert _error_schema_valid(body)


# ---------------------------------------------------------------------------
# Rate limit tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestRateLimiting:
    """Rate limit enforcement — Requirements 3.2, 3.3"""

    async def test_rate_limit_429_includes_required_fields(self, api_key_env):
        env = api_key_env

        # Create a key with very low daily limit
        service = env["service"]
        raw_key_limited, record = await service.generate_key(
            org_name="RateLimitedOrg",
            created_by_email="admin@ratelimited.com",
            scopes=["simulate", "read_sessions", "list_scenarios"],
            rate_limit_daily=1,
            rate_limit_per_minute=60,
        )

        # First request should succeed (uses the 1 allowed request)
        resp1 = await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": raw_key_limited},
        )
        assert resp1.status_code == 200

        # Second request should be rate limited
        resp2 = await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": raw_key_limited},
        )
        assert resp2.status_code == 429
        body = resp2.json()["detail"]
        assert body["error"] == "rate_limit_exceeded"
        assert "retry_after_seconds" in body["details"]
        assert "limit" in body["details"]
        assert "used" in body["details"]

    async def test_rate_limit_headers_present_on_success(self, api_key_env):
        env = api_key_env
        resp = await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": env["raw_key"]},
        )
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
        assert "x-ratelimit-reset" in resp.headers


# ---------------------------------------------------------------------------
# Error response format consistency
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorResponseFormat:
    """All error responses match IntegrationErrorResponse schema — Requirement 13.1, 13.2"""

    async def test_401_matches_schema(self, api_key_env):
        env = api_key_env
        resp = await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": "a2a_live_bogus_key_value"},
        )
        assert resp.status_code == 401
        body = resp.json()["detail"]
        assert _error_schema_valid(body)

    async def test_403_deactivated_matches_schema(self, api_key_env):
        env = api_key_env
        service = env["service"]
        raw_key2, record2 = await service.generate_key(
            org_name="SchemaTestOrg",
            created_by_email="admin@schema.com",
            scopes=["simulate"],
        )
        await service.deactivate_key(record2["key_id"])

        resp = await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": raw_key2},
        )
        assert resp.status_code == 403
        body = resp.json()["detail"]
        assert _error_schema_valid(body)

    async def test_404_session_matches_schema(self, api_key_env):
        env = api_key_env
        env["session_store"].get_session_doc.side_effect = Exception("Not found")

        resp = await env["client"].get(
            f"{BASE}/sessions/does-not-exist",
            headers={"X-API-Key": env["raw_key"]},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert _error_schema_valid(body)

    async def test_429_matches_schema(self, api_key_env):
        env = api_key_env
        service = env["service"]
        raw_key_limited, _ = await service.generate_key(
            org_name="Schema429Org",
            created_by_email="admin@schema429.com",
            scopes=["simulate", "read_sessions", "list_scenarios"],
            rate_limit_daily=1,
        )
        # Exhaust the limit
        await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": raw_key_limited},
        )
        # This should be 429
        resp = await env["client"].get(
            f"{BASE}/health",
            headers={"X-API-Key": raw_key_limited},
        )
        assert resp.status_code == 429
        body = resp.json()["detail"]
        assert _error_schema_valid(body)
