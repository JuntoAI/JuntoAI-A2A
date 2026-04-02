"""Property-based tests for GET /api/v1/models endpoint.

Uses hypothesis to verify the available models endpoint returns the correct
deduplicated, filtered union of model_ids from all loaded scenarios.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.main import app
from app.orchestrator import model_router
from app.scenarios.models import AgentDefinition, ArenaScenario
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Known family prefixes that exist in MODEL_FAMILIES
_KNOWN_PREFIXES = sorted(model_router.MODEL_FAMILIES.keys())

# Model IDs with a known family prefix (will pass the filter)
_known_model_id = st.sampled_from(_KNOWN_PREFIXES).flatmap(
    lambda prefix: st.from_regex(
        rf"^{prefix}-[a-z0-9]{{1,20}}$", fullmatch=True
    )
)

# Model IDs with an unknown family prefix (will be filtered out)
_unknown_model_id = st.from_regex(
    r"^unknown-[a-z0-9]{1,20}$", fullmatch=True
)

# Any model ID — mix of known and unknown
_any_model_id = st.one_of(_known_model_id, _unknown_model_id)

# Optional fallback model ID (None or a model ID)
_optional_model_id = st.one_of(st.none(), _any_model_id)


def _agent_strategy():
    """Strategy for generating a minimal AgentDefinition-compatible dict."""
    return st.fixed_dictionaries({
        "model_id": _any_model_id,
        "fallback_model_id": _optional_model_id,
        "role": st.from_regex(r"^[A-Z][a-z]{2,10}$", fullmatch=True),
    })


def _scenario_strategy():
    """Strategy for generating a list of agent configs per scenario."""
    return st.lists(
        _agent_strategy(),
        min_size=1,
        max_size=5,
    )


# A list of scenarios, each being a list of agent dicts
_scenarios_strategy = st.lists(
    _scenario_strategy(),
    min_size=0,
    max_size=4,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_mock_registry(scenarios_data: list[list[dict]]) -> MagicMock:
    """Build a mock ScenarioRegistry with ._scenarios populated from raw data."""
    registry = MagicMock(spec=ScenarioRegistry)
    mock_scenarios = {}

    for i, agents_data in enumerate(scenarios_data):
        scenario_id = f"scenario-{i}"
        scenario = MagicMock(spec=ArenaScenario)
        scenario.id = scenario_id

        mock_agents = []
        for agent_data in agents_data:
            agent = MagicMock(spec=AgentDefinition)
            agent.model_id = agent_data["model_id"]
            agent.fallback_model_id = agent_data["fallback_model_id"]
            agent.role = agent_data["role"]
            mock_agents.append(agent)

        scenario.agents = mock_agents
        mock_scenarios[scenario_id] = scenario

    registry._scenarios = mock_scenarios
    return registry


def _compute_expected(scenarios_data: list[list[dict]]) -> list[dict[str, str]]:
    """Compute the expected endpoint response from raw scenario data."""
    seen: set[str] = set()
    for agents_data in scenarios_data:
        for agent_data in agents_data:
            seen.add(agent_data["model_id"])
            if agent_data["fallback_model_id"]:
                seen.add(agent_data["fallback_model_id"])

    results = []
    for mid in sorted(seen):
        prefix = mid.split("-", 1)[0] if "-" in mid else mid
        if prefix in model_router.MODEL_FAMILIES:
            results.append({"model_id": mid, "family": prefix})

    return results


# ---------------------------------------------------------------------------
# Feature: agent-advanced-config
# Property 7: Available models endpoint returns correct filtered union
# **Validates: Requirements 9.2, 9.3, 9.4**
#
# For any set of loaded scenarios in the ScenarioRegistry, the GET /api/v1/models
# endpoint should return the deduplicated union of all model_id and
# fallback_model_id values across all agents, filtered to include only those
# whose family prefix exists in MODEL_FAMILIES. Each returned object should
# contain both model_id and family fields.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(scenarios_data=_scenarios_strategy)
@pytest.mark.asyncio
async def test_models_endpoint_returns_correct_filtered_union(scenarios_data):
    """Feature: agent-advanced-config, Property 7: Available models endpoint returns correct filtered union"""
    mock_registry = _build_mock_registry(scenarios_data)
    app.dependency_overrides[get_scenario_registry] = lambda: mock_registry

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/models")

        assert resp.status_code == 200
        body = resp.json()

        expected = _compute_expected(scenarios_data)

        # Core property: response matches expected deduplicated filtered union
        assert body == expected

        # Structural properties: every item has model_id and family
        for item in body:
            assert "model_id" in item
            assert "family" in item
            assert isinstance(item["model_id"], str)
            assert isinstance(item["family"], str)

        # Deduplication: no duplicate model_ids
        model_ids = [item["model_id"] for item in body]
        assert len(model_ids) == len(set(model_ids))

        # Filter property: every returned family is in MODEL_FAMILIES
        for item in body:
            assert item["family"] in model_router.MODEL_FAMILIES

        # Family correctness: family matches the prefix of model_id
        for item in body:
            expected_prefix = item["model_id"].split("-", 1)[0]
            assert item["family"] == expected_prefix

        # Completeness: no valid model_id was dropped
        all_model_ids = set()
        for agents_data in scenarios_data:
            for agent_data in agents_data:
                all_model_ids.add(agent_data["model_id"])
                if agent_data["fallback_model_id"]:
                    all_model_ids.add(agent_data["fallback_model_id"])

        returned_ids = {item["model_id"] for item in body}
        for mid in all_model_ids:
            prefix = mid.split("-", 1)[0] if "-" in mid else mid
            if prefix in model_router.MODEL_FAMILIES:
                assert mid in returned_ids, (
                    f"Valid model '{mid}' missing from response"
                )

        # Exclusion: no unknown-family model_id leaked through
        for mid in all_model_ids:
            prefix = mid.split("-", 1)[0] if "-" in mid else mid
            if prefix not in model_router.MODEL_FAMILIES:
                assert mid not in returned_ids, (
                    f"Invalid model '{mid}' should not be in response"
                )

    finally:
        app.dependency_overrides.pop(get_scenario_registry, None)
