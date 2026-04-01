"""Scenario loader — reads, parses, and validates scenario JSON files."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.scenarios.exceptions import (
    ScenarioFileNotFoundError,
    ScenarioParseError,
    ScenarioValidationError,
)
from app.scenarios.models import ArenaScenario


def load_scenario_from_file(file_path: str | Path) -> ArenaScenario:
    """Load and validate a scenario from a JSON file.

    Raises:
        ScenarioFileNotFoundError: File doesn't exist or isn't readable
        ScenarioParseError: File content isn't valid JSON
        ScenarioValidationError: JSON doesn't conform to schema
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ScenarioFileNotFoundError(str(path))

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ScenarioFileNotFoundError(str(path)) from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ScenarioParseError(str(path), str(e)) from e

    return load_scenario_from_dict(data, source_path=str(path))


def load_scenario_from_dict(
    data: dict, source_path: str = "<dict>"
) -> ArenaScenario:
    """Validate a dict against the ArenaScenario schema.

    Raises:
        ScenarioValidationError: Data doesn't conform to schema
    """
    try:
        return ArenaScenario.model_validate(data)
    except ValidationError as e:
        raise ScenarioValidationError(source_path, e.errors()) from e
