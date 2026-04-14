"""Integration tests for scenario router endpoints."""

import json
import tempfile
from pathlib import Path

import httpx
import pytest

from app.main import app
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry

# Minimal valid scenario for test fixtures
_TEST_SCENARIO = {
    "id": "test_scenario",
    "name": "Test Scenario",
    "description": "A test scenario for integration tests.",
    "agents": [
        {
            "role": "Buyer",
            "name": "Test Buyer",
            "type": "negotiator",
            "persona_prompt": "You are a buyer.",
            "goals": ["Buy cheap"],
            "budget": {"min": 1000, "max": 5000, "target": 3000},
            "tone": "firm",
            "output_fields": ["offer"],
            "model_id": "gemini-3-flash-preview",
        },
        {
            "role": "Seller",
            "name": "Test Seller",
            "type": "negotiator",
            "persona_prompt": "You are a seller.",
            "goals": ["Sell high"],
            "budget": {"min": 3000, "max": 10000, "target": 7000},
            "tone": "friendly",
            "output_fields": ["offer"],
            "model_id": "claude-3-5-sonnet",
        },
    ],
    "toggles": [
        {
            "id": "secret_info",
            "label": "Reveal secret info",
            "target_agent_role": "Buyer",
            "hidden_context_payload": {"secret": "hidden value"},
        }
    ],
    "negotiation_params": {
        "max_turns": 5,
        "agreement_threshold": 500,
        "turn_order": ["Buyer", "Seller"],
    },
    "outcome_receipt": {
        "equivalent_human_time": "~1 day",
        "process_label": "Test Negotiation",
    },
}


@pytest.fixture()
def test_registry(tmp_path: Path) -> ScenarioRegistry:
    """Create a ScenarioRegistry from a temp directory with one valid scenario."""
    scenario_file = tmp_path / "test.scenario.json"
    scenario_file.write_text(json.dumps(_TEST_SCENARIO))
    return ScenarioRegistry(scenarios_dir=str(tmp_path))


@pytest.fixture()
async def client(test_registry: ScenarioRegistry):
    """Async httpx client with scenario registry dependency override."""
    app.dependency_overrides[get_scenario_registry] = lambda: test_registry
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c
    app.dependency_overrides.pop(get_scenario_registry, None)


class TestListScenarios:
    async def test_returns_200_with_list(self, client):
        resp = await client.get("/api/v1/scenarios")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1

    async def test_list_entry_structure(self, client):
        resp = await client.get("/api/v1/scenarios")
        entry = resp.json()[0]
        assert entry["id"] == "test_scenario"
        assert entry["name"] == "Test Scenario"
        assert entry["description"] == "A test scenario for integration tests."
        # list endpoint should only return summary fields
        assert set(entry.keys()) == {"id", "name", "description", "difficulty", "category", "tags", "available"}


class TestGetScenario:
    async def test_returns_full_scenario(self, client):
        resp = await client.get("/api/v1/scenarios/test_scenario")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "test_scenario"
        assert body["name"] == "Test Scenario"
        assert len(body["agents"]) == 2
        assert len(body["toggles"]) == 1
        assert body["negotiation_params"]["max_turns"] == 5
        assert body["outcome_receipt"]["process_label"] == "Test Negotiation"

    async def test_agents_have_expected_roles(self, client):
        resp = await client.get("/api/v1/scenarios/test_scenario")
        roles = {a["role"] for a in resp.json()["agents"]}
        assert roles == {"Buyer", "Seller"}


class TestGetScenarioNotFound:
    async def test_unknown_id_returns_404(self, client):
        resp = await client.get("/api/v1/scenarios/nonexistent_scenario")
        assert resp.status_code == 404

    async def test_404_error_body(self, client):
        resp = await client.get("/api/v1/scenarios/nonexistent_scenario")
        body = resp.json()
        assert body["detail"]["scenario_id"] == "nonexistent_scenario"
        assert "not found" in body["detail"]["error"].lower()


# ---------------------------------------------------------------------------
# Persona filtering via query param — Requirements 4.3, 4.4, 4.5, 4.6
# ---------------------------------------------------------------------------

_SALES_SCENARIO = {**_TEST_SCENARIO, "id": "sales_scenario", "name": "Sales Scenario", "tags": ["sales"]}
_FOUNDER_SCENARIO = {**_TEST_SCENARIO, "id": "founder_scenario", "name": "Founder Scenario", "tags": ["founder"]}
_GENERAL_SCENARIO = {**_TEST_SCENARIO, "id": "general_scenario", "name": "General Scenario"}


@pytest.fixture()
def persona_registry(tmp_path: Path) -> ScenarioRegistry:
    """Registry with sales, founder, and untagged scenarios."""
    for name, data in [
        ("sales.scenario.json", _SALES_SCENARIO),
        ("founder.scenario.json", _FOUNDER_SCENARIO),
        ("general.scenario.json", _GENERAL_SCENARIO),
    ]:
        (tmp_path / name).write_text(json.dumps(data))
    return ScenarioRegistry(scenarios_dir=str(tmp_path))


@pytest.fixture()
async def persona_client(persona_registry: ScenarioRegistry):
    app.dependency_overrides[get_scenario_registry] = lambda: persona_registry
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c
    app.dependency_overrides.pop(get_scenario_registry, None)


class TestPersonaQueryParam:
    async def test_persona_sales_filters_correctly(self, persona_client):
        resp = await persona_client.get("/api/v1/scenarios?persona=sales")
        assert resp.status_code == 200
        ids = {s["id"] for s in resp.json()}
        assert "sales_scenario" in ids
        assert "general_scenario" in ids
        assert "founder_scenario" not in ids

    async def test_persona_founder_filters_correctly(self, persona_client):
        resp = await persona_client.get("/api/v1/scenarios?persona=founder")
        assert resp.status_code == 200
        ids = {s["id"] for s in resp.json()}
        assert "founder_scenario" in ids
        assert "general_scenario" in ids
        assert "sales_scenario" not in ids

    async def test_no_persona_returns_all(self, persona_client):
        resp = await persona_client.get("/api/v1/scenarios")
        assert resp.status_code == 200
        ids = {s["id"] for s in resp.json()}
        assert ids == {"sales_scenario", "founder_scenario", "general_scenario"}

    async def test_response_includes_tags_field(self, persona_client):
        resp = await persona_client.get("/api/v1/scenarios")
        for entry in resp.json():
            assert "tags" in entry
