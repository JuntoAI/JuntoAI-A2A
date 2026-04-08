"""Pydantic V2 models for the social sharing feature."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ParticipantSummary(BaseModel):
    """Summary of a single negotiation participant."""

    role: str
    name: str
    agent_type: str
    summary: str


class EvaluationScores(BaseModel):
    """High-level evaluation dimension scores from the post-negotiation evaluator."""

    fairness: int = Field(ge=1, le=10)
    mutual_respect: int = Field(ge=1, le=10)
    value_creation: int = Field(ge=1, le=10)
    satisfaction: int = Field(ge=1, le=10)
    overall_score: int = Field(ge=1, le=10)


class PublicMessage(BaseModel):
    """A single public message from the negotiation conversation."""

    agent_name: str
    role: str
    agent_type: str
    message: str
    turn_number: int


class SharePayload(BaseModel):
    """Full persisted share document for a completed negotiation.

    Keyed by share_slug in the shared_negotiations collection/table.
    Contains only public-facing summary data — no raw history,
    hidden context, custom prompts, or model overrides.
    """

    share_slug: str = Field(min_length=8, max_length=8)
    session_id: str
    scenario_id: str = Field(default="")
    scenario_name: str
    scenario_description: str
    deal_status: Literal["Agreed", "Blocked", "Failed"]
    outcome_text: str
    final_offer: float = Field(ge=0)
    turns_completed: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    participant_summaries: list[ParticipantSummary]
    evaluation_scores: EvaluationScores | None = Field(default=None)
    public_conversation: list[PublicMessage] = Field(default_factory=list)
    elapsed_time_ms: int = Field(ge=0)
    share_image_url: str
    created_at: datetime


class SocialPostText(BaseModel):
    """Platform-specific social media post text variants."""

    twitter: str = Field(max_length=280)
    linkedin: str = Field(max_length=3000)
    facebook: str = Field(max_length=3000)


class CreateShareRequest(BaseModel):
    """Request body for POST /api/v1/share."""

    session_id: str = Field(min_length=1)
    email: str = Field(min_length=1)


class CreateShareResponse(BaseModel):
    """Response body for POST /api/v1/share."""

    share_slug: str
    share_url: str
    social_post_text: SocialPostText
    share_image_url: str
