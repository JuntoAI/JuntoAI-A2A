"""Unit tests for Scenario Registry.

Tests cover: discovery from directory, list_scenarios, get_scenario,
ScenarioNotFoundError, SCENARIOS_DIR env var, invalid file skipping,
empty directory, and __len__.

Requirements: 4.1–4.7, 10.1, 10.4
"""

import json
import logging

import pytest

from app.scenarios.exceptions import ScenarioNotFoundError
from app.scenarios.registry import ScenarioRegistry


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


def _write_scenario(directory, filename, data):
    """Write a scenario dict as JSON to a *.scenario.json file."""
    path = directory / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Discovery — valid and invalid files
# ---------------------------------------------------------------------------


class TestRegistryDiscovery:
    def test_discovers_valid_scenario_files(self, tmp_path):
        _write_scenario(tmp_path, "alpha.scenario.json", _scenario(id="alpha", name="Alpha"))
        _write_scenario(tmp_path, "beta.scenario.json", _scenario(id="beta", name="Beta"))

        registry = ScenarioRegistry(scenarios_dir=str(tmp_path))

        assert len(registry) == 2

    def test_skips_invalid_json_files(self, tmp_path, caplog):
        _write_scenario(tmp_path, "good.scenario.json", _scenario(id="good"))
        (tmp_path / "bad.scenario.json").write_text("{not json!!!", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            registry = ScenarioRegistry(scenarios_dir=str(tmp_path))

        assert len(registry) == 1
        assert "Skipping invalid scenario file" in caplog.text

    def test_skips_schema_invalid_files(self, tmp_path, caplog):
        _write_scenario(tmp_path, "good.scenario.json", _scenario(id="good"))
        _write_scenario(tmp_path, "bad.scenario.json", {"id": "incomplete"})

        with caplog.at_level(logging.WARNING):
            registry = ScenarioRegistry(scenarios_dir=str(tmp_path))

        assert len(registry) == 1
        assert "Skipping invalid scenario file" in caplog.text

    def test_ignores_non_scenario_json_files(self, tmp_path):
        """Only *.scenario.json files should be discovered."""
        _write_scenario(tmp_path, "valid.scenario.json", _scenario(id="valid"))
        (tmp_path / "readme.json").write_text(json.dumps({"note": "ignore me"}), encoding="utf-8")
        (tmp_path / "config.txt").write_text("not a scenario", encoding="utf-8")

        registry = ScenarioRegistry(scenarios_dir=str(tmp_path))

        assert len(registry) == 1

    def test_nonexistent_directory_results_in_empty_registry(self, tmp_path, caplog):
        missing = tmp_path / "does_not_exist"

        with caplog.at_level(logging.WARNING):
            registry = ScenarioRegistry(scenarios_dir=str(missing))

        assert len(registry) == 0
        assert "not found" in caplog.text


# ---------------------------------------------------------------------------
# Empty directory
# ---------------------------------------------------------------------------


class TestRegistryEmptyDirectory:
    def test_empty_directory_results_in_empty_registry(self, tmp_path):
        registry = ScenarioRegistry(scenarios_dir=str(tmp_path))

        assert len(registry) == 0
        assert registry.list_scenarios() == []


# ---------------------------------------------------------------------------
# list_scenarios
# ---------------------------------------------------------------------------


class TestListScenarios:
    def test_returns_correct_entries(self, tmp_path):
        _write_scenario(tmp_path, "s1.scenario.json", _scenario(id="s1", name="Scenario 1", description="Desc 1"))
        _write_scenario(tmp_path, "s2.scenario.json", _scenario(id="s2", name="Scenario 2", description="Desc 2"))

        registry = ScenarioRegistry(scenarios_dir=str(tmp_path))
        result = registry.list_scenarios()

        assert len(result) == 2
        ids = {entry["id"] for entry in result}
        assert ids == {"s1", "s2"}
        for entry in result:
            assert set(entry.keys()) == {"id", "name", "description", "difficulty"}

    def test_entries_contain_correct_fields(self, tmp_path):
        _write_scenario(tmp_path, "x.scenario.json", _scenario(id="x", name="X Name", description="X Desc"))

        registry = ScenarioRegistry(scenarios_dir=str(tmp_path))
        result = registry.list_scenarios()

        assert result == [{"id": "x", "name": "X Name", "description": "X Desc", "difficulty": "intermediate"}]


# ---------------------------------------------------------------------------
# get_scenario
# ---------------------------------------------------------------------------


class TestGetScenario:
    def test_returns_correct_scenario_object(self, tmp_path):
        _write_scenario(tmp_path, "demo.scenario.json", _scenario(id="demo", name="Demo"))

        registry = ScenarioRegistry(scenarios_dir=str(tmp_path))
        scenario = registry.get_scenario("demo")

        assert scenario.id == "demo"
        assert scenario.name == "Demo"
        assert len(scenario.agents) == 2

    def test_unknown_id_raises_scenario_not_found_error(self, tmp_path):
        _write_scenario(tmp_path, "real.scenario.json", _scenario(id="real"))

        registry = ScenarioRegistry(scenarios_dir=str(tmp_path))

        with pytest.raises(ScenarioNotFoundError) as exc_info:
            registry.get_scenario("ghost")

        assert exc_info.value.scenario_id == "ghost"


# ---------------------------------------------------------------------------
# SCENARIOS_DIR env var
# ---------------------------------------------------------------------------


class TestScenariosEnvVar:
    def test_scenarios_dir_env_var_is_respected(self, tmp_path, monkeypatch):
        _write_scenario(tmp_path, "env.scenario.json", _scenario(id="env-scenario"))
        monkeypatch.setenv("SCENARIOS_DIR", str(tmp_path))

        registry = ScenarioRegistry()

        assert len(registry) == 1
        assert registry.get_scenario("env-scenario").id == "env-scenario"


# ---------------------------------------------------------------------------
# __len__
# ---------------------------------------------------------------------------


class TestRegistryLen:
    def test_len_returns_correct_count(self, tmp_path):
        _write_scenario(tmp_path, "a.scenario.json", _scenario(id="a"))
        _write_scenario(tmp_path, "b.scenario.json", _scenario(id="b"))
        _write_scenario(tmp_path, "c.scenario.json", _scenario(id="c"))

        registry = ScenarioRegistry(scenarios_dir=str(tmp_path))

        assert len(registry) == 3

    def test_len_zero_for_empty_dir(self, tmp_path):
        registry = ScenarioRegistry(scenarios_dir=str(tmp_path))

        assert len(registry) == 0
