"""Negotiation state Pydantic model for session persistence and API serialization."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NegotiationStateModel(BaseModel):
    """Complete state of a negotiation session.

    This is the canonical serialization format for Firestore persistence
    and API responses. The LangGraph TypedDict (spec 030) is the runtime
    format — explicit converters bridge the two.
    """

    model_config = ConfigDict(extra="ignore")

    session_id: str
    scenario_id: str
    turn_count: int = Field(default=0, ge=0)
    max_turns: int = Field(default=15, gt=0)
    current_speaker: str = Field(default="Buyer")
    deal_status: Literal["Negotiating", "Agreed", "Blocked", "Failed"] = Field(
        default="Negotiating"
    )
    current_offer: float = Field(default=0.0, ge=0.0)
    history: list[dict[str, Any]] = Field(default_factory=list)
    warning_count: int = Field(default=0, ge=0)
    hidden_context: dict[str, Any] = Field(default_factory=dict)
    agreement_threshold: float = Field(default=1000000.0, gt=0.0)
    active_toggles: list[str] = Field(default_factory=list)
    turn_order: list[str] = Field(default_factory=list)
    turn_order_index: int = Field(default=0, ge=0)
    agent_states: dict[str, dict[str, Any]] = Field(default_factory=dict)
    total_tokens_used: int = Field(default=0, ge=0)
    custom_prompts: dict[str, str] = Field(default_factory=dict)
    model_overrides: dict[str, str] = Field(default_factory=dict)
    structured_memory_enabled: bool = Field(default=False)
    structured_memory_roles: list[str] = Field(default_factory=list)
    agent_memories: dict[str, dict[str, Any]] = Field(default_factory=dict)
    milestone_summaries_enabled: bool = Field(default=False)
    milestone_summaries: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict
    )
    sliding_window_size: int = Field(default=3, ge=1)
    milestone_interval: int = Field(default=4, ge=2)
    no_memory_roles: list[str] = Field(default_factory=list)
