"""Pydantic V2 models for the CRM Integration API."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings


class CRMContext(BaseModel):
    """CRM context fields for simulation personalization."""

    contact_name: str | None = None
    company: str | None = None
    role: str | None = None
    industry: str | None = None
    deal_value: float | None = Field(None, ge=0)
    deal_stage: str | None = None
    pain_points: list[str] | None = None
    competing_vendors: list[str] | None = None
    budget_approved: bool | None = None
    custom_fields: dict[str, Any] | None = None


class MyProfileInput(BaseModel):
    """CRM user's persona for dynamic scenario building."""

    name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    company: str = Field(..., min_length=1)
    goals: list[str] = Field(..., min_length=1)
    constraints: list[str] = Field(default_factory=list)
    tone: str | None = None


class TheirProfileInput(BaseModel):
    """Contact's persona for dynamic scenario building."""

    name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    company: str = Field(..., min_length=1)
    industry: str | None = None
    goals: list[str] = Field(..., min_length=1)
    constraints: list[str] = Field(default_factory=list)
    tone: str | None = None


class DealContextInput(BaseModel):
    """Deal-specific data for dynamic scenario building."""

    value: float | None = Field(None, ge=0)
    stage: str | None = None
    competing_vendors: list[str] | None = None
    deadline: str | None = None
    key_terms: list[str] | None = None


class RegulatorInput(BaseModel):
    """Regulator/observer agent definition for dynamic scenario building."""

    name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    rules: list[str] = Field(..., min_length=1)


class ScenarioBuilderInput(BaseModel):
    """Structured input for dynamic scenario generation via BuilderLLMAgent."""

    simulation_type: str = Field(..., min_length=1)
    my_profile: MyProfileInput
    their_profile: TheirProfileInput
    deal_context: DealContextInput | None = None
    regulator: RegulatorInput | None = None
    additional_instructions: str | None = None


class SimulateRequest(BaseModel):
    """Request body for POST /api/v1/integrations/simulate."""

    scenario_id: str = Field(..., min_length=1)
    active_toggles: list[str] | None = None
    context: CRMContext | None = None
    callback_url: str | None = None
    triggered_by: str | None = None
    scenario_builder: ScenarioBuilderInput | None = None

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, v: str | None) -> str | None:
        """Validate callback_url is HTTPS (or HTTP in local mode)."""
        if v is None:
            return v
        if settings.RUN_MODE == "local":
            if not v.startswith(("https://", "http://")):
                raise ValueError("callback_url must start with https:// or http://")
        else:
            if not v.startswith("https://"):
                raise ValueError("callback_url must start with https://")
        return v

    @model_validator(mode="after")
    def validate_dynamic_scenario(self) -> "SimulateRequest":
        """Enforce mutual exclusion between _dynamic scenario_id and scenario_builder."""
        if self.scenario_id == "_dynamic" and self.scenario_builder is None:
            raise ValueError(
                "scenario_builder is required when scenario_id is '_dynamic'"
            )
        if self.scenario_id != "_dynamic" and self.scenario_builder is not None:
            raise ValueError(
                "scenario_builder is forbidden when scenario_id is not '_dynamic'"
            )
        return self


class SimulateResponse(BaseModel):
    """Response body for POST /api/v1/integrations/simulate."""

    session_id: str
    status: str = "running"
    viewer_url: str
    estimated_duration_seconds: int = 120
    created_at: str


class ParticipantSummary(BaseModel):
    """Summary of a single negotiation participant in session outcome."""

    role: str
    name: str
    agent_type: str
    summary: str


class EvaluationScores(BaseModel):
    """Evaluation dimension scores from the post-negotiation evaluator."""

    fairness: int = Field(..., ge=1, le=10)
    mutual_respect: int = Field(..., ge=1, le=10)
    value_creation: int = Field(..., ge=1, le=10)
    satisfaction: int = Field(..., ge=1, le=10)
    overall_score: int = Field(..., ge=1, le=10)


class SessionOutcome(BaseModel):
    """Outcome data for a completed negotiation session."""

    deal_status: Literal["Agreed", "Blocked", "Failed"]
    summary: str
    final_offer: float
    turns_completed: int
    warning_count: int
    duration_seconds: int
    participant_summaries: list[ParticipantSummary]
    evaluation_scores: EvaluationScores | None = None


class SessionStatusResponse(BaseModel):
    """Response body for GET /api/v1/integrations/sessions/{session_id}."""

    session_id: str
    scenario_id: str
    scenario_name: str
    status: str
    viewer_url: str
    turns_completed: int
    current_offer: float | None = None
    created_at: str
    completed_at: str | None = None
    outcome: SessionOutcome | None = None


class ScenarioAgent(BaseModel):
    """Public agent info for scenario listing (no internal fields)."""

    role: str
    name: str
    type: str


class ScenarioToggle(BaseModel):
    """Public toggle info for scenario listing (no hidden_context_payload)."""

    id: str
    label: str
    target_agent_role: str


class ScenarioContextFields(BaseModel):
    """Context field definitions for a scenario."""

    required: list[str]
    optional: list[str]


class ScenarioListItem(BaseModel):
    """A single scenario in the integration scenarios list."""

    id: str
    name: str
    description: str
    category: str
    difficulty: str
    agents: list[ScenarioAgent]
    toggles: list[ScenarioToggle]
    context_fields: ScenarioContextFields


class ScenarioListResponse(BaseModel):
    """Response body for GET /api/v1/integrations/scenarios."""

    scenarios: list[ScenarioListItem]


class RateLimitInfo(BaseModel):
    """Rate limit status included in health check response."""

    daily_limit: int
    used_today: int
    remaining: int
    resets_at: str


class HealthResponse(BaseModel):
    """Response body for GET /api/v1/integrations/health."""

    status: str = "ok"
    version: str
    key_valid: bool = True
    org_name: str
    rate_limit: RateLimitInfo


class WebhookPayload(BaseModel):
    """Payload sent to callback_url on simulation completion."""

    event: str = "simulation.completed"
    session_id: str
    scenario_id: str
    status: str
    outcome: dict[str, Any]
    viewer_url: str
    timestamp: str


class IntegrationErrorResponse(BaseModel):
    """Consistent error response format for all Integration API errors."""

    error: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
