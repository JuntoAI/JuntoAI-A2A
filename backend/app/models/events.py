"""SSE event Pydantic models with Literal discriminators."""

from typing import Literal

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


class StreamErrorEvent(BaseModel):
    """SSE event for unexpected errors during streaming."""

    event_type: Literal["error"]
    message: str
