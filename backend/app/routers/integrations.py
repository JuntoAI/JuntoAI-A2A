"""Integration API router — all /integrations/* endpoints.

Provides endpoints for external CRM systems to interact with the A2A
negotiation engine: health checks, scenario listing, simulation triggering,
session polling, and API key management.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import get_api_key_store, get_session_store, get_share_store
from app.middleware.api_key_auth import require_scope, validate_api_key
from app.models.integrations import (
    CreateKeyRequest,
    CreateKeyResponse,
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


def _add_rate_limit_headers(response: Response, key_record: dict) -> None:
    """Attach X-RateLimit-* headers to a response from key_record rate info."""
    rate_info = key_record.get("_rate_info", {})
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
        share_service=None,  # Uses internal import in the service
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
    key_record: dict = Depends(validate_api_key),
) -> HealthResponse:
    """Health check endpoint — validates API key and returns rate limit status."""
    _add_rate_limit_headers(response, key_record)

    rate_info = key_record.get("_rate_info", {})

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        key_valid=True,
        org_name=key_record.get("org_name", ""),
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
    key_record: dict = Depends(require_scope("list_scenarios")),
) -> ScenarioListResponse:
    """List available scenarios with filtered public fields."""
    _add_rate_limit_headers(response, key_record)

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
    key_record: dict = Depends(require_scope("simulate")),
) -> SimulateResponse:
    """Trigger an async negotiation simulation."""
    _add_rate_limit_headers(response, key_record)

    service = _build_integration_service()

    try:
        result = await service.create_simulation(
            request=request,
            key_record=key_record,
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
    key_record: dict = Depends(require_scope("read_sessions")),
) -> SessionStatusResponse:
    """Poll the status of a simulation session."""
    _add_rate_limit_headers(response, key_record)

    service = _build_integration_service()

    try:
        result = await service.get_session_status(session_id, key_record)
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


# ---------------------------------------------------------------------------
# POST /integrations/keys — generate new API key
# ---------------------------------------------------------------------------


@integrations_router.post(
    "/keys",
    response_model=CreateKeyResponse,
    status_code=201,
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        429: {"model": IntegrationErrorResponse},
    },
)
async def create_api_key(
    request: CreateKeyRequest,
    response: Response,
    key_record: dict = Depends(require_scope("manage_keys")),
) -> CreateKeyResponse:
    """Generate a new API key for an organization."""
    _add_rate_limit_headers(response, key_record)

    store = get_api_key_store()
    service = ApiKeyService(store)

    raw_key, new_key_record = await service.generate_key(
        org_name=request.org_name,
        created_by_email=key_record.get("created_by_email", ""),
        scopes=request.scopes,
        rate_limit_daily=request.rate_limit_daily,
        rate_limit_per_minute=request.rate_limit_per_minute,
    )

    # Store raw key on the record for potential webhook use downstream
    new_key_record["_raw_key"] = raw_key

    return CreateKeyResponse(
        key_id=new_key_record["key_id"],
        api_key=raw_key,
        org_name=new_key_record["org_name"],
        scopes=new_key_record["scopes"],
        rate_limit_daily=new_key_record["rate_limit_daily"],
        created_at=new_key_record["created_at"],
    )


# ---------------------------------------------------------------------------
# DELETE /integrations/keys/{key_id} — deactivate API key
# ---------------------------------------------------------------------------


@integrations_router.delete(
    "/keys/{key_id}",
    status_code=200,
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
        429: {"model": IntegrationErrorResponse},
    },
)
async def deactivate_api_key(
    key_id: str,
    response: Response,
    key_record: dict = Depends(require_scope("manage_keys")),
) -> JSONResponse:
    """Deactivate an API key (soft-delete)."""
    _add_rate_limit_headers(response, key_record)

    store = get_api_key_store()
    service = ApiKeyService(store)

    # Verify the key exists
    existing = await store.get_key_by_id(key_id)
    if existing is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": "key_not_found",
                "message": f"API key '{key_id}' not found.",
                "details": {},
            },
        )

    await service.deactivate_key(key_id)

    return JSONResponse(
        status_code=200,
        content={
            "key_id": key_id,
            "active": False,
            "message": "API key deactivated successfully.",
        },
    )
