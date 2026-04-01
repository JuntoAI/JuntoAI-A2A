"""Pydantic V2 models for Arena Scenario configuration.

Defines the complete schema for scenario JSON files: Budget, AgentDefinition,
ToggleDefinition, NegotiationParams, OutcomeReceipt, and ArenaScenario.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Budget(BaseModel):
    """Financial constraints for an agent."""

    min: float = Field(..., ge=0, description="Minimum acceptable value")
    max: float = Field(..., ge=0, description="Maximum budget ceiling")
    target: float = Field(..., ge=0, description="Target/ideal value")

    @model_validator(mode="after")
    def min_le_max(self) -> Budget:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must be <= max ({self.max})")
        return self


class AgentDefinition(BaseModel):
    """A single AI agent's configuration within a scenario."""

    role: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: Literal["negotiator", "regulator", "observer"] = Field(
        ..., description="Agent type for output schema selection"
    )
    persona_prompt: str = Field(..., min_length=1)
    goals: list[str] = Field(..., min_length=1)
    budget: Budget
    tone: str = Field(..., min_length=1)
    output_fields: list[str] = Field(..., min_length=1)
    model_id: str = Field(..., min_length=1)
    fallback_model_id: str | None = Field(default=None)


class ToggleDefinition(BaseModel):
    """An investor-facing information toggle."""

    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    target_agent_role: str = Field(..., min_length=1)
    hidden_context_payload: dict = Field(..., min_length=1)


class NegotiationParams(BaseModel):
    """Turn limits, agreement threshold, and execution order."""

    max_turns: int = Field(..., gt=0)
    agreement_threshold: float = Field(..., gt=0)
    turn_order: list[str] = Field(
        ..., min_length=1, description="Agent role execution sequence per cycle"
    )


class OutcomeReceipt(BaseModel):
    """Post-negotiation display metadata."""

    equivalent_human_time: str = Field(..., min_length=1)
    process_label: str = Field(..., min_length=1)


class ArenaScenario(BaseModel):
    """Complete negotiation scenario definition."""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    agents: list[AgentDefinition] = Field(..., min_length=2)
    toggles: list[ToggleDefinition] = Field(..., min_length=1)
    negotiation_params: NegotiationParams
    outcome_receipt: OutcomeReceipt

    @model_validator(mode="after")
    def validate_cross_references(self) -> ArenaScenario:
        agent_roles = {a.role for a in self.agents}

        # Unique roles
        if len(agent_roles) != len(self.agents):
            roles = [a.role for a in self.agents]
            dupes = [r for r in roles if roles.count(r) > 1]
            raise ValueError(f"Duplicate agent roles: {set(dupes)}")

        # Toggle target_agent_role references valid role
        for toggle in self.toggles:
            if toggle.target_agent_role not in agent_roles:
                raise ValueError(
                    f"Toggle '{toggle.id}' targets role "
                    f"'{toggle.target_agent_role}' "
                    f"which is not in agents: {agent_roles}"
                )

        # turn_order entries reference valid agent roles
        for role in self.negotiation_params.turn_order:
            if role not in agent_roles:
                raise ValueError(
                    f"turn_order entry '{role}' "
                    f"is not a valid agent role: {agent_roles}"
                )

        # At least 1 agent must be a negotiator
        if not any(a.type == "negotiator" for a in self.agents):
            raise ValueError(
                "At least one agent must have type 'negotiator'"
            )

        return self
