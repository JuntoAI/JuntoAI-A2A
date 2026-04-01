"""Health check router."""

from fastapi import APIRouter

from app.config import settings
from app.models.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return application health status and version."""
    return HealthResponse(status="ok", version=settings.APP_VERSION)
