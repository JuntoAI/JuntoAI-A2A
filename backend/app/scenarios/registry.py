"""Scenario Registry — in-memory index of validated scenarios."""

import logging
import os
from pathlib import Path

from app.scenarios.exceptions import (
    ScenarioFileNotFoundError,
    ScenarioNotFoundError,
    ScenarioParseError,
    ScenarioValidationError,
)
from app.scenarios.loader import load_scenario_from_file
from app.scenarios.models import ArenaScenario

logger = logging.getLogger(__name__)

DEFAULT_SCENARIOS_DIR = str(Path(__file__).resolve().parent / "data")


class ScenarioRegistry:
    def __init__(self, scenarios_dir: str | None = None):
        self._scenarios: dict[str, ArenaScenario] = {}
        self._dir = Path(
            scenarios_dir or os.getenv("SCENARIOS_DIR", DEFAULT_SCENARIOS_DIR)
        )
        self._discover()

    def _discover(self) -> None:
        if not self._dir.exists():
            logger.warning(f"Scenarios directory not found: {self._dir}")
            return
        for path in sorted(self._dir.glob("*.scenario.json")):
            try:
                scenario = load_scenario_from_file(path)
                self._scenarios[scenario.id] = scenario
                logger.info(f"Loaded scenario: {scenario.id} ({scenario.name})")
            except (
                ScenarioFileNotFoundError,
                ScenarioParseError,
                ScenarioValidationError,
            ) as e:
                logger.warning(f"Skipping invalid scenario file {path}: {e}")

    def list_scenarios(self) -> list[dict[str, str]]:
        return [
            {"id": s.id, "name": s.name, "description": s.description}
            for s in self._scenarios.values()
        ]

    def get_scenario(self, scenario_id: str) -> ArenaScenario:
        if scenario_id not in self._scenarios:
            raise ScenarioNotFoundError(scenario_id)
        return self._scenarios[scenario_id]

    def __len__(self) -> int:
        return len(self._scenarios)
