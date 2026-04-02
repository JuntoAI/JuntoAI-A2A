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
from app.scenarios.models import DIFFICULTY_ORDER, ArenaScenario

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

    def list_scenarios(self, email: str | None = None) -> list[dict[str, str]]:
        sorted_scenarios = sorted(
            self._scenarios.values(),
            key=lambda s: (DIFFICULTY_ORDER.get(s.difficulty, 1), s.name),
        )
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "difficulty": s.difficulty,
            }
            for s in sorted_scenarios
            if self._user_can_access(s, email)
        ]

    def get_scenario(self, scenario_id: str, email: str | None = None) -> ArenaScenario:
        if scenario_id not in self._scenarios:
            raise ScenarioNotFoundError(scenario_id)
        scenario = self._scenarios[scenario_id]
        if not self._user_can_access(scenario, email):
            raise ScenarioNotFoundError(scenario_id)
        return scenario

    @staticmethod
    def _user_can_access(scenario: ArenaScenario, email: str | None) -> bool:
        """Check if a user's email is allowed to access a scenario."""
        if scenario.allowed_email_domains is None:
            return True
        if email is None:
            return False
        domain = email.lower().split("@")[-1] if "@" in email else ""
        return domain in scenario.allowed_email_domains

    def __len__(self) -> int:
        return len(self._scenarios)
