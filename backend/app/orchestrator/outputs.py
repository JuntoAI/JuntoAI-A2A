"""Pydantic V2 output models for parsing LLM agent responses."""

from typing import Any, Literal

from pydantic import BaseModel


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
