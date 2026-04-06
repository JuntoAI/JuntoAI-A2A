"""Health check report and custom scenario Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.builder.events import HealthCheckFindingEvent


class AgentPromptScore(BaseModel):
    """Per-agent prompt quality evaluation result."""

    role: str
    name: str
    prompt_quality_score: int = Field(ge=0, le=100)
    findings: list[str]


class BudgetOverlapResult(BaseModel):
    """Budget overlap analysis between negotiator agents."""

    overlap_zone: tuple[float, float] | None
    overlap_percentage: float
    target_gap: float
    agreement_threshold: float
    threshold_ratio: float


class StallRiskResult(BaseModel):
    """Stall risk assessment result."""

    stall_risk_score: int = Field(ge=0, le=100)
    risks: list[str]


class HealthCheckReport(BaseModel):
    """Complete health check report with readiness score and findings."""

    readiness_score: int = Field(ge=0, le=100)
    tier: Literal["Ready", "Needs Work", "Not Ready"]
    prompt_quality_scores: list[AgentPromptScore]
    tension_score: int = Field(ge=0, le=100)
    budget_overlap_score: int = Field(ge=0, le=100)
    budget_overlap_detail: BudgetOverlapResult
    toggle_effectiveness_score: int = Field(ge=0, le=100)
    turn_sanity_score: int = Field(ge=0, le=100)
    stall_risk: StallRiskResult
    findings: list[HealthCheckFindingEvent]
    recommendations: list[str]


class CustomScenarioDocument(BaseModel):
    """Stored at profiles/{email}/custom_scenarios/{scenario_id}."""

    scenario_id: str
    scenario_json: dict
    created_at: datetime
    updated_at: datetime
