"""Pydantic V2 models for LLM usage summary statistics."""

from pydantic import BaseModel, Field


class PersonaUsageStats(BaseModel):
    """Per-persona (agent_role) aggregated usage statistics."""

    agent_role: str
    agent_type: str
    model_id: str
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    call_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    avg_latency_ms: int = Field(ge=0)
    tokens_per_message: int = Field(ge=0)


class ModelUsageStats(BaseModel):
    """Per-model aggregated usage statistics."""

    model_id: str
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    call_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    avg_latency_ms: int = Field(ge=0)
    tokens_per_message: int = Field(ge=0)


class UsageSummary(BaseModel):
    """Session-wide LLM usage summary with per-persona and per-model breakdowns."""

    per_persona: list[PersonaUsageStats] = Field(default_factory=list)
    per_model: list[ModelUsageStats] = Field(default_factory=list)
    total_input_tokens: int = Field(ge=0, default=0)
    total_output_tokens: int = Field(ge=0, default=0)
    total_tokens: int = Field(ge=0, default=0)
    total_calls: int = Field(ge=0, default=0)
    total_errors: int = Field(ge=0, default=0)
    avg_latency_ms: int = Field(ge=0, default=0)
    negotiation_duration_ms: int = Field(ge=0, default=0)
