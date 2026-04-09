"""Health check router."""

from fastapi import APIRouter, Depends, Request

from app.config import settings
from app.middleware import get_sse_tracker
from app.middleware.sse_limiter import SSEConnectionTracker
from app.models.health import DeployReadinessResponse, HealthResponse
from app.orchestrator.available_models import AVAILABLE_MODELS

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Return application health status and version."""
    allowed = getattr(request.app.state, "allowed_models", None)

    if allowed is None:
        return HealthResponse(status="ok", version=settings.APP_VERSION)

    total_registered = len(AVAILABLE_MODELS)
    total_available = len(allowed.model_ids)
    unavailable = [
        r.model_id for r in allowed.probe_results if not r.available
    ]
    status = "degraded" if total_available == 0 else "ok"

    return HealthResponse(
        status=status,
        version=settings.APP_VERSION,
        models={
            "total_registered": total_registered,
            "total_available": total_available,
        },
        unavailable_models=unavailable,
    )


@router.get("/deploy-readiness", response_model=DeployReadinessResponse)
async def deploy_readiness(
    tracker: SSEConnectionTracker = Depends(get_sse_tracker),
) -> DeployReadinessResponse:
    """Check if the service is safe to deploy (no active simulations)."""
    active = tracker.total_active_connections
    ready = active == 0
    message = (
        "No active simulations — safe to deploy"
        if ready
        else f"{active} simulation(s) in progress — deploy blocked"
    )
    return DeployReadinessResponse(
        ready_to_deploy=ready,
        active_simulations=active,
        message=message,
    )
