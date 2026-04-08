"""Share endpoints — create and retrieve shared negotiation payloads."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.exceptions import SessionNotFoundError, ShareNotFoundError
from app.models.share import CreateShareRequest, CreateShareResponse, SharePayload
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry
from app.services import share_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["share"])


@router.post("", response_model=CreateShareResponse)
async def create_share(
    body: CreateShareRequest,
    registry: ScenarioRegistry = Depends(get_scenario_registry),
) -> CreateShareResponse:
    """Create or retrieve a share for a completed negotiation session.

    Validates that the email matches the session owner. Returns the
    existing share if one already exists for the given session_id
    (idempotent).
    """
    try:
        return await share_service.create_or_get_share(
            session_id=body.session_id,
            email=body.email,
            registry=registry,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session {body.session_id} not found")


@router.get("/{share_slug}", response_model=SharePayload)
async def get_share(share_slug: str) -> SharePayload:
    """Retrieve a shared negotiation payload by slug. No auth required."""
    try:
        return await share_service.get_share(share_slug)
    except ShareNotFoundError:
        raise HTTPException(status_code=404, detail=f"Share {share_slug} not found")
