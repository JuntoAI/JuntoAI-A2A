"""Available models endpoint — returns deduplicated LLM models from all scenarios."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.orchestrator import model_router
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry

router = APIRouter()


@router.get("/models")
async def list_available_models(
    registry: ScenarioRegistry = Depends(get_scenario_registry),
) -> list[dict[str, str]]:
    """Return deduplicated list of available models from all loaded scenarios."""
    seen: set[str] = set()

    for scenario in registry._scenarios.values():
        for agent in scenario.agents:
            seen.add(agent.model_id)
            if agent.fallback_model_id:
                seen.add(agent.fallback_model_id)

    results: list[dict[str, str]] = []
    for mid in sorted(seen):
        prefix = mid.split("-", 1)[0] if "-" in mid else mid
        if prefix in model_router.MODEL_FAMILIES:
            results.append({"model_id": mid, "family": prefix})

    return results
