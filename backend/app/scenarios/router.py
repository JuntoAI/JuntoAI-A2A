"""FastAPI router for scenario endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_custom_scenario_store
from app.scenarios.exceptions import ScenarioNotFoundError
from app.scenarios.loader import load_scenario_from_dict
from app.scenarios.registry import ScenarioRegistry

logger = logging.getLogger(__name__)

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
    persona: str | None = Query(default=None, description="Filter by persona tag"),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
) -> list[dict]:
    return registry.list_scenarios(email=email, persona=persona)


@router.get("/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    email: str | None = Query(default=None, description="User email for access filtering"),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
    custom_store=Depends(get_custom_scenario_store),
):
    # 1. Try built-in registry first
    try:
        scenario = registry.get_scenario(scenario_id, email=email)
        return scenario.model_dump()
    except ScenarioNotFoundError:
        pass

    # 2. Fallback: look up in user's custom scenarios
    if email:
        normalized_email = email.strip().lower()
        try:
            custom_doc = await custom_store.get(normalized_email, scenario_id)
            if custom_doc and custom_doc.get("scenario_json"):
                scenario = load_scenario_from_dict(custom_doc["scenario_json"])
                return scenario.model_dump()
        except Exception as exc:
            logger.error(
                "Custom scenario lookup failed: email=%s scenario_id=%s error=%s",
                normalized_email, scenario_id, exc,
                exc_info=True,
            )

    raise HTTPException(
        status_code=404,
        detail={"scenario_id": scenario_id, "error": "Scenario not found"},
    )
