"""SSE event Pydantic models with Literal discriminators."""

from typing import Any, Literal

from pydantic import BaseModel


class AgentThoughtEvent(BaseModel):
    """SSE event for an agent's inner thought (Glass Box terminal panel)."""

    event_type: Literal["agent_thought"]
    agent_name: str
    inner_thought: str
    turn_number: int


class AgentMessageEvent(BaseModel):
    """SSE event for an agent's public message (chat panel)."""

    event_type: Literal["agent_message"]
    agent_name: str
    public_message: str
    turn_number: int
    proposed_price: float | None = None
    retention_clause_demanded: bool | None = None
    status: str | None = None


class NegotiationCompleteEvent(BaseModel):
    """SSE event signaling negotiation has reached a terminal state."""

    event_type: Literal["negotiation_complete"]
    session_id: str
    deal_status: str
    final_summary: dict


class NegotiationStallEvent(BaseModel):
    """SSE event when stall detection triggers early termination."""

    event_type: Literal["negotiation_stall"]
    session_id: str
    stall_type: str
    confidence: float
    advice: list[str]
    details: dict


class EvaluationInterviewEvent(BaseModel):
    """SSE event for an individual participant evaluation interview."""

    event_type: Literal["evaluation_interview"]
    agent_name: str
    turn_number: int
    status: Literal["interviewing", "complete"]
    satisfaction_rating: int | None = None
    felt_respected: bool | None = None
    is_win_win: bool | None = None


class EvaluationCompleteEvent(BaseModel):
    """SSE event for the final evaluation report."""

    event_type: Literal["evaluation_complete"]
    dimensions: dict[str, int]
    overall_score: int
    verdict: str
    participant_interviews: list[dict[str, Any]]
    deal_status: str


class StreamErrorEvent(BaseModel):
    """SSE event for unexpected errors during streaming."""

    event_type: Literal["error"]
    message: str
