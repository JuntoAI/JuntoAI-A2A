"""Pydantic V2 response models for the negotiation history endpoint.

Requirements: 2.1, 2.2, 2.3
"""

from pydantic import BaseModel, Field


class SessionHistoryItem(BaseModel):
    """A single completed negotiation session summary.

    Requirement 2.1: session_id, scenario_id, scenario_name, deal_status,
    total_tokens_used (ge=0), token_cost (ge=1), created_at, completed_at (optional).
    """

    session_id: str
    scenario_id: str
    scenario_name: str
    deal_status: str
    total_tokens_used: int = Field(ge=0)
    token_cost: int = Field(ge=1)
    created_at: str
    completed_at: str | None = None


class DayGroup(BaseModel):
    """Sessions grouped by UTC calendar day.

    Requirement 2.2: date (YYYY-MM-DD), total_token_cost (ge=0), sessions list.
    """

    date: str
    total_token_cost: int = Field(ge=0)
    sessions: list[SessionHistoryItem]


class SessionHistoryResponse(BaseModel):
    """Top-level history endpoint response.

    Requirement 2.3: days list, total_token_cost (ge=0), period_days (ge=1).
    """

    days: list[DayGroup]
    total_token_cost: int = Field(ge=0)
    period_days: int = Field(ge=1)
