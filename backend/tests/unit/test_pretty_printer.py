"""Unit tests for Pretty Printer.

Tests cover: output is valid JSON, output uses 2-space indentation,
all fields preserved in output (round-trip check).

Requirements: 3.1, 3.2, 3.3
"""

import json

from app.scenarios.models import ArenaScenario
from app.scenarios.pretty_printer import pretty_print


# ---------------------------------------------------------------------------
# Helpers — minimal valid scenario builder
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
        "model_id": "gemini-2.5-flash",
    }
    defaults.update(overrides)
    return defaults


def _toggle(**overrides) -> dict:
    defaults = {
        "id": "toggle_buyer",
        "label": "Secret info for buyer",
        "target_agent_role": "Buyer",
        "hidden_context_payload": {"secret": "value"},
    }
    defaults.update(overrides)
    return defaults


def _build_scenario(**overrides) -> ArenaScenario:
    defaults = {
        "id": "test-scenario",
        "name": "Test Scenario",
        "description": "A test scenario for pretty printer",
        "agents": [
            _agent(role="Buyer", name="Alice"),
            _agent(role="Seller", name="Bob"),
        ],
        "toggles": [
            _toggle(id="toggle_buyer", target_agent_role="Buyer"),
        ],
        "negotiation_params": {
            "max_turns": 10,
            "agreement_threshold": 1000.0,
            "turn_order": ["Buyer", "Seller"],
        },
        "outcome_receipt": {
            "equivalent_human_time": "~2 weeks",
            "process_label": "Acquisition",
        },
    }
    defaults.update(overrides)
    return ArenaScenario.model_validate(defaults)


# ---------------------------------------------------------------------------
# Output is valid JSON
# ---------------------------------------------------------------------------


class TestOutputIsValidJson:
    def test_pretty_print_returns_parseable_json(self):
        scenario = _build_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)

        assert isinstance(parsed, dict)

    def test_pretty_print_returns_string(self):
        scenario = _build_scenario()

        result = pretty_print(scenario)

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Output has 2-space indentation
# ---------------------------------------------------------------------------


class TestTwoSpaceIndentation:
    def test_output_uses_two_space_indent(self):
        scenario = _build_scenario()

        result = pretty_print(scenario)
        lines = result.splitlines()

        # Find first indented line and verify it starts with exactly 2 spaces
        indented = [l for l in lines if l.startswith(" ")]
        assert len(indented) > 0, "Expected indented lines in output"
        # First level of indentation should be 2 spaces
        first_indented = indented[0]
        stripped = first_indented.lstrip(" ")
        indent_size = len(first_indented) - len(stripped)
        assert indent_size == 2

    def test_output_matches_json_dumps_indent_2(self):
        """Re-serializing with json.dumps(indent=2) should produce identical output."""
        scenario = _build_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)
        expected = json.dumps(parsed, indent=2)

        assert result == expected


# ---------------------------------------------------------------------------
# All fields preserved in output (round-trip check)
# ---------------------------------------------------------------------------


class TestFieldsPreserved:
    def test_round_trip_preserves_all_top_level_fields(self):
        scenario = _build_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)

        assert parsed["id"] == "test-scenario"
        assert parsed["name"] == "Test Scenario"
        assert parsed["description"] == "A test scenario for pretty printer"
        assert len(parsed["agents"]) == 2
        assert len(parsed["toggles"]) == 1
        assert "negotiation_params" in parsed
        assert "outcome_receipt" in parsed

    def test_round_trip_produces_equal_model(self):
        """Parsing pretty_print output back into ArenaScenario yields an equal object."""
        scenario = _build_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)
        restored = ArenaScenario.model_validate(parsed)

        assert restored == scenario

    def test_agent_fields_preserved(self):
        scenario = _build_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)
        agent = parsed["agents"][0]

        assert agent["role"] == "Buyer"
        assert agent["name"] == "Alice"
        assert agent["type"] == "negotiator"
        assert agent["persona_prompt"] == "You are a buyer."
        assert agent["goals"] == ["Get the best deal"]
        assert agent["budget"] == {"min": 100.0, "max": 200.0, "target": 150.0}
        assert agent["tone"] == "assertive"
        assert agent["output_fields"] == ["offer"]
        assert agent["model_id"] == "gemini-2.5-flash"
        assert agent["fallback_model_id"] is None

    def test_toggle_fields_preserved(self):
        scenario = _build_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)
        toggle = parsed["toggles"][0]

        assert toggle["id"] == "toggle_buyer"
        assert toggle["label"] == "Secret info for buyer"
        assert toggle["target_agent_role"] == "Buyer"
        assert toggle["hidden_context_payload"] == {"secret": "value"}

    def test_negotiation_params_preserved(self):
        scenario = _build_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)
        params = parsed["negotiation_params"]

        assert params["max_turns"] == 10
        assert params["agreement_threshold"] == 1000.0
        assert params["turn_order"] == ["Buyer", "Seller"]
