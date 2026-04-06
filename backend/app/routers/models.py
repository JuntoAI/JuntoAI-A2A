"""Available models endpoint — returns the canonical list of supported LLM models."""

from __future__ import annotations

from fastapi import APIRouter

from app.orchestrator.available_models import AVAILABLE_MODELS

router = APIRouter()


@router.get("/models")
async def list_available_models() -> list[dict[str, str]]:
    """Return the canonical list of available models."""
    return [
        {"model_id": m.model_id, "family": m.family, "label": m.label}
        for m in AVAILABLE_MODELS
    ]
