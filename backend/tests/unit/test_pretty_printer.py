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
        "model_id": "gemini-3-flash-preview",
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
        assert agent["model_id"] == "gemini-3-flash-preview"
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


# ---------------------------------------------------------------------------
# Readable output (Requirement 11.2)
# ---------------------------------------------------------------------------


class TestReadableOutput:
    def test_pretty_print_is_multiline(self):
        """Output must be multi-line, not a single-line JSON blob."""
        scenario = _build_scenario()

        result = pretty_print(scenario)
        lines = result.splitlines()

        assert len(lines) > 1, "Pretty print should produce multiple lines"

    def test_pretty_print_contains_key_labels(self):
        """Human-readable output should contain recognizable field names."""
        scenario = _build_scenario()

        result = pretty_print(scenario)

        assert '"id"' in result
        assert '"name"' in result
        assert '"agents"' in result
        assert '"negotiation_params"' in result

    def test_pretty_print_not_compact(self):
        """Output should be longer than compact JSON (no whitespace)."""
        scenario = _build_scenario()

        result = pretty_print(scenario)
        compact = scenario.model_dump_json()

        assert len(result) > len(compact)


# ---------------------------------------------------------------------------
# Scenario with all fields populated (Requirement 11.2)
# ---------------------------------------------------------------------------


class TestAllFieldsPopulated:
    @staticmethod
    def _full_scenario() -> ArenaScenario:
        return ArenaScenario.model_validate(
            {
                "id": "full-scenario",
                "name": "Full Scenario",
                "description": "Every optional field is set",
                "difficulty": "advanced",
                "agents": [
                    _agent(
                        role="Negotiator",
                        name="Nora",
                        type="negotiator",
                        fallback_model_id="gemini-3-flash-preview",
                    ),
                    _agent(role="Regulator", name="Rex", type="regulator"),
                    _agent(role="Observer", name="Ollie", type="observer"),
                ],
                "toggles": [
                    _toggle(id="t1", target_agent_role="Negotiator"),
                    _toggle(id="t2", target_agent_role="Regulator"),
                ],
                "negotiation_params": {
                    "max_turns": 20,
                    "agreement_threshold": 5000.0,
                    "turn_order": ["Negotiator", "Regulator", "Observer"],
                    "price_unit": "hourly",
                    "normalization_factor": 480.0,
                    "value_label": "Price (€)",
                    "value_format": "currency",
                    "sliding_window_size": 5,
                    "milestone_interval": 6,
                },
                "outcome_receipt": {
                    "equivalent_human_time": "~1 month",
                    "process_label": "M&A Buyout",
                },
                "evaluator_config": {
                    "model_id": "gemini-3.1-pro-preview",
                    "fallback_model_id": "gemini-3-flash-preview",
                    "enabled": True,
                },
                "allowed_email_domains": ["example.com", "test.org"],
            }
        )

    def test_all_optional_fields_present_in_output(self):
        scenario = self._full_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)

        assert parsed["difficulty"] == "advanced"
        assert parsed["evaluator_config"]["model_id"] == "gemini-3.1-pro-preview"
        assert parsed["evaluator_config"]["fallback_model_id"] == "gemini-3-flash-preview"
        assert parsed["evaluator_config"]["enabled"] is True
        assert parsed["allowed_email_domains"] == ["example.com", "test.org"]

    def test_all_negotiation_params_in_output(self):
        scenario = self._full_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)
        params = parsed["negotiation_params"]

        assert params["price_unit"] == "hourly"
        assert params["normalization_factor"] == 480.0
        assert params["value_label"] == "Price (€)"
        assert params["value_format"] == "currency"
        assert params["sliding_window_size"] == 5
        assert params["milestone_interval"] == 6

    def test_fallback_model_id_preserved(self):
        scenario = self._full_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)

        negotiator = next(a for a in parsed["agents"] if a["role"] == "Negotiator")
        assert negotiator["fallback_model_id"] == "gemini-3-flash-preview"

    def test_round_trip_with_all_fields(self):
        scenario = self._full_scenario()

        result = pretty_print(scenario)
        restored = ArenaScenario.model_validate(json.loads(result))

        assert restored == scenario


# ---------------------------------------------------------------------------
# Scenario with minimal fields (Requirement 11.2)
# ---------------------------------------------------------------------------


class TestMinimalFields:
    @staticmethod
    def _minimal_scenario() -> ArenaScenario:
        """Only required fields — all optionals left at defaults."""
        return ArenaScenario.model_validate(
            {
                "id": "min",
                "name": "M",
                "description": "D",
                "agents": [
                    _agent(role="A", name="X"),
                    _agent(role="B", name="Y"),
                ],
                "toggles": [_toggle(target_agent_role="A")],
                "negotiation_params": {
                    "max_turns": 1,
                    "agreement_threshold": 1.0,
                    "turn_order": ["A", "B"],
                },
                "outcome_receipt": {
                    "equivalent_human_time": "1h",
                    "process_label": "P",
                },
            }
        )

    def test_minimal_scenario_produces_valid_json(self):
        scenario = self._minimal_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)

        assert parsed["id"] == "min"

    def test_defaults_appear_in_output(self):
        """Optional fields should still appear with their default values."""
        scenario = self._minimal_scenario()

        result = pretty_print(scenario)
        parsed = json.loads(result)

        assert parsed["difficulty"] == "intermediate"
        assert parsed["evaluator_config"] is None
        assert parsed["allowed_email_domains"] is None
        params = parsed["negotiation_params"]
        assert params["price_unit"] == "total"
        assert params["normalization_factor"] == 1.0
        assert params["value_format"] == "currency"
        assert params["sliding_window_size"] == 3
        assert params["milestone_interval"] == 4

    def test_minimal_round_trip(self):
        scenario = self._minimal_scenario()

        result = pretty_print(scenario)
        restored = ArenaScenario.model_validate(json.loads(result))

        assert restored == scenario
