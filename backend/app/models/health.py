"""Health check response model."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response schema for the GET /health endpoint."""

    status: str
    version: str
    models: dict | None = None
    unavailable_models: list[str] | None = None


class DeployReadinessResponse(BaseModel):
    """Response schema for the GET /deploy-readiness endpoint."""

    ready_to_deploy: bool
    active_simulations: int
    message: str
