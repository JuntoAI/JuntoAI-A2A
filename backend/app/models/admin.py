"""Pydantic V2 models for the admin dashboard API.

Defines request/response models, query parameter models, and enums
for the admin endpoints (user management, simulation oversight,
overview metrics, and data export).
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# --- Enums ---


class UserStatus(str, Enum):
    """Operational status of a user account in the waitlist collection."""

    active = "active"
    suspended = "suspended"
    banned = "banned"


# --- Request Models ---


class AdminLoginRequest(BaseModel):
    """Request body for POST /api/v1/admin/login."""

    password: str = Field(..., min_length=1)


class TokenAdjustRequest(BaseModel):
    """Request body for PATCH /api/v1/admin/users/{email}/tokens."""

    token_balance: int = Field(..., ge=0)


class StatusChangeRequest(BaseModel):
    """Request body for PATCH /api/v1/admin/users/{email}/status."""

    user_status: UserStatus


class BroadcastEmailRequest(BaseModel):
    """Request body for POST /api/v1/admin/broadcast."""

    subject: str = Field(..., min_length=1, max_length=200)
    body_text: str = Field(..., min_length=1, max_length=50000)


class BroadcastEmailResponse(BaseModel):
    """Response body for POST /api/v1/admin/broadcast."""

    total_users: int
    sent: int
    failed: int
    errors: list[str] = Field(default_factory=list)


# --- Response Models ---


class ScenarioAnalytics(BaseModel):
    """Per-scenario run count and average token usage."""

    scenario_id: str
    run_count: int
    avg_tokens_used: float


class ModelPerformance(BaseModel):
    """Per-model latency, token usage, and error metrics."""

    model_id: str
    avg_latency_ms: float
    avg_input_tokens: float
    avg_output_tokens: float
    error_count: int
    total_calls: int


class RecentSimulation(BaseModel):
    """Summary of a recent simulation for the overview feed."""

    session_id: str
    scenario_id: str
    deal_status: str
    turn_count: int
    total_tokens_used: int
    owner_email: str | None = None
    created_at: str | None = None


class OverviewResponse(BaseModel):
    """Response body for GET /api/v1/admin/overview."""

    total_users: int
    simulations_today: int
    active_sse_connections: int
    ai_tokens_today: int
    scenario_analytics: list[ScenarioAnalytics]
    model_performance: list[ModelPerformance]
    recent_simulations: list[RecentSimulation]


class UserListItem(BaseModel):
    """Single user entry in the paginated user list."""

    email: str
    signed_up_at: str | None = None
    last_login: str | None = None
    token_balance: int = 0
    last_reset_date: str | None = None
    tier: int = 1
    user_status: str = "active"


class UserListResponse(BaseModel):
    """Response body for GET /api/v1/admin/users."""

    users: list[UserListItem]
    next_cursor: str | None = None
    total_count: int | None = None


class SimulationListItem(BaseModel):
    """Single simulation entry in the paginated simulation list."""

    session_id: str
    scenario_id: str
    owner_email: str | None = None
    deal_status: str
    turn_count: int = 0
    max_turns: int = 15
    total_tokens_used: int = 0
    active_toggles: list[str] = Field(default_factory=list)
    model_overrides: dict[str, str] = Field(default_factory=dict)
    created_at: str | None = None


class SimulationListResponse(BaseModel):
    """Response body for GET /api/v1/admin/simulations."""

    simulations: list[SimulationListItem]
    next_cursor: str | None = None


# --- Query Parameter Models ---


class UserListParams(BaseModel):
    """Query parameters for GET /api/v1/admin/users."""

    cursor: str | None = None
    page_size: int = Field(default=50, ge=1, le=200)
    tier: int | None = Field(default=None, ge=1, le=3)
    status: UserStatus | None = None


class SimulationListParams(BaseModel):
    """Query parameters for GET /api/v1/admin/simulations."""

    cursor: str | None = None
    page_size: int = Field(default=50, ge=1, le=200)
    scenario_id: str | None = None
    deal_status: str | None = None
    owner_email: str | None = None
    order: Literal["asc", "desc"] = "desc"
