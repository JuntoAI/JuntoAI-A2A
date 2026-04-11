"""Pydantic V2 models for the stats dashboard API."""

from pydantic import BaseModel, Field


class OutcomeBreakdown(BaseModel):
    """Counts of terminal deal statuses."""

    agreed: int = 0
    blocked: int = 0
    failed: int = 0


class ModelTokenBreakdown(BaseModel):
    """Per-model token consumption."""

    model_id: str
    tokens_today: int = 0
    tokens_7d: int = 0


class ModelPerformance(BaseModel):
    """Per-model average response time."""

    model_id: str
    avg_response_time_today: float | None = None
    avg_response_time_7d: float | None = None


class ScenarioPopularity(BaseModel):
    """Per-scenario simulation count."""

    scenario_id: str
    scenario_name: str
    count_today: int = 0
    count_7d: int = 0


class StatsResponse(BaseModel):
    """Full stats dashboard response."""

    # User activity
    unique_users_today: int = 0
    unique_users_7d: int = 0

    # Simulations
    simulations_today: int = 0
    simulations_7d: int = 0
    active_simulations: int = 0
    outcomes_today: OutcomeBreakdown = Field(default_factory=OutcomeBreakdown)
    outcomes_7d: OutcomeBreakdown = Field(default_factory=OutcomeBreakdown)

    # Tokens
    total_tokens_today: int = 0
    total_tokens_7d: int = 0

    # Per-model
    model_tokens: list[ModelTokenBreakdown] = Field(default_factory=list)
    model_performance: list[ModelPerformance] = Field(default_factory=list)

    # Scenarios
    scenario_popularity: list[ScenarioPopularity] = Field(default_factory=list)

    # Turns
    avg_turns_today: float | None = None
    avg_turns_7d: float | None = None

    # Custom scenarios
    custom_scenarios_today: int = 0
    custom_scenarios_7d: int = 0
    custom_scenarios_all_time: int = 0

    # Custom agent sessions
    custom_agent_sessions_today: int = 0
    custom_agent_sessions_7d: int = 0
    custom_agent_sessions_all_time: int = 0

    # Metadata
    generated_at: str = ""
