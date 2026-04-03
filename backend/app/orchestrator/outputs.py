"""Pydantic V2 output models for parsing LLM agent responses."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class NegotiatorOutput(BaseModel):
    """Structured output from a negotiator agent."""

    inner_thought: str
    public_message: str
    proposed_price: float
    extra_fields: dict[str, Any] = {}


class RegulatorOutput(BaseModel):
    """Structured output from a regulator agent."""

    status: Literal["CLEAR", "WARNING", "BLOCKED"]
    reasoning: str


class ObserverOutput(BaseModel):
    """Structured output from an observer agent."""

    observation: str
    recommendation: str = ""


class AgentMemory(BaseModel):
    """Structured per-agent memory for tracking negotiation state across turns."""

    my_offers: list[float] = Field(default_factory=list)
    their_offers: list[float] = Field(default_factory=list)
    concessions_made: list[str] = Field(default_factory=list)
    concessions_received: list[str] = Field(default_factory=list)
    open_items: list[str] = Field(default_factory=list)
    tactics_used: list[str] = Field(default_factory=list)
    red_lines_stated: list[str] = Field(default_factory=list)
    compliance_status: dict[str, str] = Field(default_factory=dict)
    turn_count: int = 0
