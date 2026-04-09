"""Available models endpoint — returns only verified-working LLM models."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/models")
async def list_available_models(request: Request) -> list[dict[str, str]]:
    """Return models that passed the startup availability probe."""
    if hasattr(request.app.state, "allowed_models"):
        entries = request.app.state.allowed_models.entries
    else:
        entries = ()

    return [
        {"model_id": m.model_id, "family": m.family, "label": m.label}
        for m in entries
    ]
