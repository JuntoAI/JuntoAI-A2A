"""Integration API router — all /integrations/* endpoints.

Provides endpoints for external CRM systems to interact with the A2A
negotiation engine: health checks, scenario listing, simulation triggering,
and session polling.

Auth model: X-Integration-Token (org token) + X-User-Email (domain validated).
No scopes — all authenticated orgs get full access.
Rate limiting is per-org (daily + per-minute).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import get_api_key_store, get_session_store, get_share_store
from app.middleware.api_key_auth import validate_integration_auth
from app.models.integrations import (
    HealthResponse,
    IntegrationErrorResponse,
    RateLimitInfo,
    ScenarioListResponse,
    SessionStatusResponse,
    SimulateRequest,
    SimulateResponse,
)
from app.scenarios.router import get_scenario_registry
from app.services.api_key_service import ApiKeyService
from app.services.integration_service import IntegrationError, IntegrationService
from app.services.webhook_dispatcher import WebhookDispatcher

logger = logging.getLogger(__name__)

integrations_router = APIRouter(prefix="/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Helper: attach rate limit headers to response
# ---------------------------------------------------------------------------


def _add_rate_limit_headers(response: Response, org_record: dict) -> None:
    """Attach X-RateLimit-* headers to a response from org rate info."""
    rate_info = org_record.get("_rate_info", {})
    response.headers["X-RateLimit-Limit"] = str(rate_info.get("daily_limit", 0))
    response.headers["X-RateLimit-Remaining"] = str(rate_info.get("remaining", 0))
    response.headers["X-RateLimit-Reset"] = rate_info.get("resets_at", "")


# ---------------------------------------------------------------------------
# Helper: build IntegrationService with DI dependencies
# ---------------------------------------------------------------------------


def _build_integration_service() -> IntegrationService:
    """Construct an IntegrationService with all required dependencies."""
    from app.db import get_custom_scenario_store

    return IntegrationService(
        session_store=get_session_store(),
        share_service=None,
        scenario_registry=get_scenario_registry(),
        api_key_service=ApiKeyService(get_api_key_store()),
        custom_scenario_store=get_custom_scenario_store(),
        webhook_dispatcher=WebhookDispatcher(),
    )


# ---------------------------------------------------------------------------
# GET /integrations/health — health check with rate limit status
# ---------------------------------------------------------------------------


@integrations_router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        429: {"model": IntegrationErrorResponse},
    },
)
async def health_check(
    response: Response,
    org_record: dict = Depends(validate_integration_auth),
) -> HealthResponse:
    """Health check endpoint — validates token + email and returns rate limit status."""
    _add_rate_limit_headers(response, org_record)

    rate_info = org_record.get("_rate_info", {})

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        key_valid=True,
        org_name=org_record.get("org_name", ""),
        rate_limit=RateLimitInfo(
            daily_limit=rate_info.get("daily_limit", 0),
            used_today=rate_info.get("used_today", 0),
            remaining=rate_info.get("remaining", 0),
            resets_at=rate_info.get("resets_at", ""),
        ),
    )


# ---------------------------------------------------------------------------
# GET /integrations/scenarios — list filtered scenarios
# ---------------------------------------------------------------------------


@integrations_router.get(
    "/scenarios",
    response_model=ScenarioListResponse,
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        429: {"model": IntegrationErrorResponse},
    },
)
async def list_scenarios(
    response: Response,
    org_record: dict = Depends(validate_integration_auth),
) -> ScenarioListResponse:
    """List available scenarios with filtered public fields."""
    _add_rate_limit_headers(response, org_record)

    service = _build_integration_service()
    scenarios = service.list_scenarios()

    return ScenarioListResponse(scenarios=scenarios)


# ---------------------------------------------------------------------------
# POST /integrations/simulate — trigger async simulation
# ---------------------------------------------------------------------------


@integrations_router.post(
    "/simulate",
    response_model=SimulateResponse,
    status_code=201,
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
        422: {"model": IntegrationErrorResponse},
        429: {"model": IntegrationErrorResponse},
        500: {"model": IntegrationErrorResponse},
    },
)
async def simulate(
    request: SimulateRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    org_record: dict = Depends(validate_integration_auth),
) -> SimulateResponse:
    """Trigger an async negotiation simulation.

    The user email from X-User-Email is automatically used as triggered_by
    for session ownership and attribution.
    """
    _add_rate_limit_headers(response, org_record)

    # Override triggered_by with the authenticated user email
    user_email = org_record.get("_user_email", "")
    if user_email:
        request = request.model_copy(update={"triggered_by": user_email})

    service = _build_integration_service()

    try:
        result = await service.create_simulation(
            request=request,
            key_record=org_record,
            background_tasks=background_tasks,
        )
        return result
    except IntegrationError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error("Simulation creation failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "simulation_failed",
                "message": "An unexpected error occurred while creating the simulation.",
                "details": {},
            },
        )


# ---------------------------------------------------------------------------
# GET /integrations/sessions/{session_id} — poll session status
# ---------------------------------------------------------------------------


@integrations_router.get(
    "/sessions/{session_id}",
    response_model=SessionStatusResponse,
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
        429: {"model": IntegrationErrorResponse},
    },
)
async def get_session_status(
    session_id: str,
    response: Response,
    org_record: dict = Depends(validate_integration_auth),
) -> SessionStatusResponse:
    """Poll the status of a simulation session."""
    _add_rate_limit_headers(response, org_record)

    service = _build_integration_service()

    try:
        result = await service.get_session_status(session_id, org_record)
        return result
    except IntegrationError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error(
            "Session status retrieval failed for %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "simulation_failed",
                "message": "An unexpected error occurred while retrieving session status.",
                "details": {},
            },
        )
