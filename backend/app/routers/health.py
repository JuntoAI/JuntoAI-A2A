"""Health check router."""

from fastapi import APIRouter, Depends

from app.config import settings
from app.middleware import get_sse_tracker
from app.middleware.sse_limiter import SSEConnectionTracker
from app.models.health import DeployReadinessResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return application health status and version."""
    return HealthResponse(status="ok", version=settings.APP_VERSION)


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
