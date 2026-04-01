"""Health check response model."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response schema for the GET /health endpoint."""

    status: str
    version: str
