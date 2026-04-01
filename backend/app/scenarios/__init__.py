"""Scenario Engine — config-driven scenario loading, validation, and toggle injection."""

from app.scenarios.exceptions import (
    InvalidToggleError,
    ScenarioFileNotFoundError,
    ScenarioNotFoundError,
    ScenarioParseError,
    ScenarioValidationError,
)
from app.scenarios.loader import load_scenario_from_dict, load_scenario_from_file
from app.scenarios.models import ArenaScenario
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.toggle_injector import build_hidden_context

__all__ = [
    "ArenaScenario",
    "InvalidToggleError",
    "ScenarioFileNotFoundError",
    "ScenarioNotFoundError",
    "ScenarioParseError",
    "ScenarioRegistry",
    "ScenarioValidationError",
    "build_hidden_context",
    "load_scenario_from_dict",
    "load_scenario_from_file",
]
