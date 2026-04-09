"""FastAPI router for scenario endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.scenarios.exceptions import ScenarioNotFoundError
from app.scenarios.registry import ScenarioRegistry

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

_registry: ScenarioRegistry | None = None


def get_scenario_registry() -> ScenarioRegistry:
    global _registry
    if _registry is None:
        _registry = ScenarioRegistry()
    return _registry


@router.get("")
async def list_scenarios(
    email: str | None = Query(default=None, description="User email for access filtering"),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
) -> list[dict[str, str | bool]]:
    return registry.list_scenarios(email=email)


@router.get("/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    email: str | None = Query(default=None, description="User email for access filtering"),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
):
    try:
        scenario = registry.get_scenario(scenario_id, email=email)
        return scenario.model_dump()
    except ScenarioNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"scenario_id": scenario_id, "error": "Scenario not found"},
        )
