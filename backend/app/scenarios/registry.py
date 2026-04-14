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


def _is_scenario_available(
    scenario: ArenaScenario, allowed: frozenset[str]
) -> bool:
    """Return True if every agent has at least one reachable model."""
    for agent in scenario.agents:
        agent_models = {agent.model_id}
        if agent.fallback_model_id:
            agent_models.add(agent.fallback_model_id)
        if not agent_models & allowed:
            return False
    return True


class ScenarioRegistry:
    def __init__(
        self,
        scenarios_dir: str | None = None,
        allowed_model_ids: frozenset[str] | None = None,
    ):
        self._scenarios: dict[str, ArenaScenario] = {}
        self._allowed_model_ids: frozenset[str] | None = allowed_model_ids
        self._dir = Path(
            scenarios_dir or os.getenv("SCENARIOS_DIR", DEFAULT_SCENARIOS_DIR)
        )
        self._discover()

    def set_allowed_model_ids(self, ids: frozenset[str]) -> None:
        """Update the allowed model set (e.g. after startup probes complete)."""
        self._allowed_model_ids = ids

    def _discover(self) -> None:
        if not self._dir.exists():
            logger.warning(f"Scenarios directory not found: {self._dir}")
            return
        for path in sorted(self._dir.glob("*.scenario.json")):
            try:
                scenario = load_scenario_from_file(path)
                self._scenarios[scenario.id] = scenario
                logger.info(f"Loaded scenario: {scenario.id} ({scenario.name})")
                self._log_unavailable_agents(scenario)
            except (
                ScenarioFileNotFoundError,
                ScenarioParseError,
                ScenarioValidationError,
            ) as e:
                logger.warning(f"Skipping invalid scenario file {path}: {e}")

    def _log_unavailable_agents(self, scenario: ArenaScenario) -> None:
        """Log WARNING for each agent whose models are not in the allowed set."""
        if self._allowed_model_ids is None:
            return
        for agent in scenario.agents:
            agent_models = {agent.model_id}
            if agent.fallback_model_id:
                agent_models.add(agent.fallback_model_id)
            if not agent_models & self._allowed_model_ids:
                logger.warning(
                    "Scenario '%s' agent '%s' has no available model "
                    "(model_id=%s, fallback_model_id=%s)",
                    scenario.id,
                    agent.role,
                    agent.model_id,
                    agent.fallback_model_id,
                )

    def list_scenarios(self, email: str | None = None, persona: str | None = None) -> list[dict]:
        def _sort_key(s: ArenaScenario) -> tuple:
            # Primary: category alphabetical, "General" last
            cat_key = (1, s.category) if s.category == "General" else (0, s.category)
            # Secondary: difficulty order
            diff_key = DIFFICULTY_ORDER.get(s.difficulty, 1)
            # Tertiary: name
            return (*cat_key, diff_key, s.name)

        sorted_scenarios = sorted(
            self._scenarios.values(),
            key=_sort_key,
        )
        allowed = self._allowed_model_ids
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "difficulty": s.difficulty,
                "category": s.category,
                "tags": s.tags,
                "available": (
                    _is_scenario_available(s, allowed)
                    if allowed is not None
                    else True
                ),
            }
            for s in sorted_scenarios
            if self._user_can_access(s, email)
            and (persona is None or s.tags is None or persona in s.tags)
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
