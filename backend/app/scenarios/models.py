"""Pydantic V2 models for Arena Scenario configuration.

Defines the complete schema for scenario JSON files: Budget, AgentDefinition,
ToggleDefinition, NegotiationParams, OutcomeReceipt, and ArenaScenario.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Canonical difficulty ordering — used by registry for sorting
DIFFICULTY_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2, "fun": 3}


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
    price_unit: Literal["total", "hourly", "monthly", "annual"] = Field(
        default="total",
        description="Common price unit for agreement detection. "
        "When agents use different units (e.g. hourly vs total), "
        "set this to the unit the agreement_threshold is expressed in. "
        "Agents whose budget scale differs will have their proposed_price "
        "normalized before convergence checks.",
    )
    normalization_factor: float = Field(
        default=1.0,
        gt=0,
        description="Multiplier to convert the smaller-unit agent's price "
        "to the common unit. E.g. for hourly→total over 480 hours, set 480.",
    )
    value_label: str = Field(
        default="Price",
        description="Display label for the negotiated value in the UI. "
        "E.g. 'Price (€)', 'Curfew Time', 'Belief Score'.",
    )
    value_format: Literal["currency", "time_from_22", "percent", "number"] = Field(
        default="currency",
        description="How to format the proposed_price in the UI. "
        "'currency' → $X, 'time_from_22' → converts minutes-from-10PM to HH:MM, "
        "'percent' → X%, 'number' → plain number.",
    )
    sliding_window_size: int = Field(
        default=3,
        ge=1,
        description="Number of recent raw messages in the sliding window for agent prompts.",
    )
    milestone_interval: int = Field(
        default=4,
        ge=2,
        description="Number of full turn cycles between milestone summary generations.",
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
    difficulty: Literal["beginner", "intermediate", "advanced", "fun"] = Field(
        default="intermediate",
        description="Scenario complexity level — controls dropdown ordering",
    )
    agents: list[AgentDefinition] = Field(..., min_length=2)
    toggles: list[ToggleDefinition] = Field(..., min_length=1)
    negotiation_params: NegotiationParams
    outcome_receipt: OutcomeReceipt
    allowed_email_domains: list[str] | None = Field(
        default=None,
        description="If set, only users whose email ends with one of these "
        "domains can see and run this scenario. None means public.",
    )

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
