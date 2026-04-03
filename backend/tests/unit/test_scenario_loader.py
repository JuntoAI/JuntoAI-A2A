"""Unit tests for Scenario Loader.

Tests cover: load_scenario_from_file, load_scenario_from_dict,
and the three error paths (file not found, invalid JSON, schema violation).

Requirements: 2.1, 2.2, 2.3, 2.4
"""

import json

import pytest

from app.scenarios.exceptions import (
    ScenarioFileNotFoundError,
    ScenarioParseError,
    ScenarioValidationError,
)
from app.scenarios.loader import load_scenario_from_dict, load_scenario_from_file
from app.scenarios.models import ArenaScenario


# ---------------------------------------------------------------------------
# Helpers — minimal valid fixtures (mirrors test_scenario_models.py pattern)
# ---------------------------------------------------------------------------


def _budget(**overrides) -> dict:
    defaults = {"min": 100.0, "max": 200.0, "target": 150.0}
    defaults.update(overrides)
    return defaults


def _agent(**overrides) -> dict:
    defaults = {
        "role": "Buyer",
        "name": "Alice",
        "type": "negotiator",
        "persona_prompt": "You are a buyer.",
        "goals": ["Get the best deal"],
        "budget": _budget(),
        "tone": "assertive",
        "output_fields": ["offer"],
        "model_id": "gemini-3-flash-preview",
    }
    defaults.update(overrides)
    return defaults


def _toggle(**overrides) -> dict:
    defaults = {
        "id": "toggle_1",
        "label": "Secret info",
        "target_agent_role": "Buyer",
        "hidden_context_payload": {"secret": "value"},
    }
    defaults.update(overrides)
    return defaults


def _negotiation_params(**overrides) -> dict:
    defaults = {
        "max_turns": 10,
        "agreement_threshold": 1000.0,
        "turn_order": ["Buyer", "Seller"],
    }
    defaults.update(overrides)
    return defaults


def _outcome_receipt(**overrides) -> dict:
    defaults = {
        "equivalent_human_time": "~2 weeks",
        "process_label": "Acquisition",
    }
    defaults.update(overrides)
    return defaults


def _scenario(**overrides) -> dict:
    defaults = {
        "id": "test-scenario",
        "name": "Test Scenario",
        "description": "A test scenario",
        "agents": [
            _agent(role="Buyer", name="Alice"),
            _agent(role="Seller", name="Bob", type="negotiator"),
        ],
        "toggles": [_toggle(target_agent_role="Buyer")],
        "negotiation_params": _negotiation_params(),
        "outcome_receipt": _outcome_receipt(),
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# load_scenario_from_file — happy path
# ---------------------------------------------------------------------------


class TestLoadScenarioFromFile:
    def test_valid_json_file_returns_arena_scenario(self, tmp_path):
        f = tmp_path / "valid.scenario.json"
        f.write_text(json.dumps(_scenario()), encoding="utf-8")

        result = load_scenario_from_file(f)

        assert isinstance(result, ArenaScenario)
        assert result.id == "test-scenario"
        assert result.name == "Test Scenario"
        assert len(result.agents) == 2

    def test_loaded_scenario_preserves_nested_fields(self, tmp_path):
        f = tmp_path / "nested.scenario.json"
        f.write_text(json.dumps(_scenario()), encoding="utf-8")

        result = load_scenario_from_file(f)

        assert result.agents[0].budget.min == 100.0
        assert result.toggles[0].hidden_context_payload == {"secret": "value"}
        assert result.negotiation_params.max_turns == 10


# ---------------------------------------------------------------------------
# load_scenario_from_file — error paths
# ---------------------------------------------------------------------------


class TestLoadScenarioFromFileErrors:
    def test_nonexistent_path_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "does_not_exist.json"

        with pytest.raises(ScenarioFileNotFoundError) as exc_info:
            load_scenario_from_file(missing)

        assert str(missing) in str(exc_info.value)
        assert exc_info.value.file_path == str(missing)

    def test_directory_path_raises_file_not_found(self, tmp_path):
        """A directory is not a file — should raise ScenarioFileNotFoundError."""
        with pytest.raises(ScenarioFileNotFoundError):
            load_scenario_from_file(tmp_path)

    def test_invalid_json_raises_parse_error(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json!!!", encoding="utf-8")

        with pytest.raises(ScenarioParseError) as exc_info:
            load_scenario_from_file(f)

        assert str(f) in str(exc_info.value)
        assert exc_info.value.file_path == str(f)
        assert exc_info.value.detail  # contains JSON decode error detail

    def test_empty_file_raises_parse_error(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("", encoding="utf-8")

        with pytest.raises(ScenarioParseError):
            load_scenario_from_file(f)

    def test_schema_invalid_json_raises_validation_error(self, tmp_path):
        f = tmp_path / "invalid_schema.json"
        # Valid JSON but missing required fields
        f.write_text(json.dumps({"id": "x"}), encoding="utf-8")

        with pytest.raises(ScenarioValidationError) as exc_info:
            load_scenario_from_file(f)

        assert str(f) in str(exc_info.value)
        assert exc_info.value.file_path == str(f)
        assert isinstance(exc_info.value.errors, list)
        assert len(exc_info.value.errors) > 0

    def test_validation_error_contains_field_details(self, tmp_path):
        f = tmp_path / "partial.json"
        # Missing agents, toggles, negotiation_params, outcome_receipt
        data = {"id": "x", "name": "X", "description": "X"}
        f.write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(ScenarioValidationError) as exc_info:
            load_scenario_from_file(f)

        error_locs = [tuple(e["loc"]) for e in exc_info.value.errors]
        # Should flag at least agents, toggles, negotiation_params, outcome_receipt
        assert ("agents",) in error_locs
        assert ("toggles",) in error_locs
        assert ("negotiation_params",) in error_locs
        assert ("outcome_receipt",) in error_locs


# ---------------------------------------------------------------------------
# load_scenario_from_dict
# ---------------------------------------------------------------------------


class TestLoadScenarioFromDict:
    def test_valid_dict_returns_arena_scenario(self):
        result = load_scenario_from_dict(_scenario())

        assert isinstance(result, ArenaScenario)
        assert result.id == "test-scenario"

    def test_invalid_dict_raises_validation_error(self):
        with pytest.raises(ScenarioValidationError) as exc_info:
            load_scenario_from_dict({"id": "x"})

        assert exc_info.value.file_path == "<dict>"
        assert len(exc_info.value.errors) > 0

    def test_custom_source_path_in_error(self):
        with pytest.raises(ScenarioValidationError) as exc_info:
            load_scenario_from_dict({"id": "x"}, source_path="/custom/path.json")

        assert exc_info.value.file_path == "/custom/path.json"
