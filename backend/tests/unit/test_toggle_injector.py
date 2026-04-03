"""Unit tests for Toggle Injector.

Tests cover: single toggle injection, multiple toggles same role merge
(shallow merge, last wins on key conflict), no toggles returns empty dict,
invalid toggle raises InvalidToggleError, multiple toggles targeting
different roles produce separate keys.

Requirements: 5.1, 5.2, 5.3, 5.5, 5.6
"""

import pytest

from app.scenarios.exceptions import InvalidToggleError
from app.scenarios.models import ArenaScenario
from app.scenarios.toggle_injector import build_hidden_context


# ---------------------------------------------------------------------------
# Helpers — minimal valid scenario builders
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


def _scenario(**overrides) -> dict:
    defaults = {
        "id": "test-scenario",
        "name": "Test Scenario",
        "description": "A test scenario for toggle injection",
        "agents": [
            _agent(role="Buyer", name="Alice"),
            _agent(role="Seller", name="Bob"),
        ],
        "toggles": [
            _toggle(id="toggle_buyer", target_agent_role="Buyer", hidden_context_payload={"intel": "debt_info"}),
            _toggle(id="toggle_seller", target_agent_role="Seller", hidden_context_payload={"pressure": "deadline"}),
            _toggle(id="toggle_buyer_extra", target_agent_role="Buyer", hidden_context_payload={"leverage": "patent"}),
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
    return defaults


def _build_scenario(**overrides) -> ArenaScenario:
    return ArenaScenario.model_validate(_scenario(**overrides))


# ---------------------------------------------------------------------------
# Single toggle injection
# ---------------------------------------------------------------------------


class TestSingleToggleInjection:
    def test_single_toggle_returns_correct_hidden_context(self):
        scenario = _build_scenario()

        result = build_hidden_context(scenario, ["toggle_buyer"])

        assert result == {"Buyer": {"intel": "debt_info"}}

    def test_single_toggle_targets_correct_role(self):
        scenario = _build_scenario()

        result = build_hidden_context(scenario, ["toggle_seller"])

        assert "Seller" in result
        assert "Buyer" not in result
        assert result["Seller"] == {"pressure": "deadline"}


# ---------------------------------------------------------------------------
# Multiple toggles — same role merge (shallow merge, last wins)
# ---------------------------------------------------------------------------


class TestMultipleTogglesSameRole:
    def test_multiple_toggles_same_role_merge_payloads(self):
        scenario = _build_scenario()

        result = build_hidden_context(scenario, ["toggle_buyer", "toggle_buyer_extra"])

        assert "Buyer" in result
        assert result["Buyer"]["intel"] == "debt_info"
        assert result["Buyer"]["leverage"] == "patent"

    def test_last_wins_on_key_conflict(self):
        """When two toggles targeting the same role share a key, the later one wins."""
        scenario = _build_scenario(
            toggles=[
                _toggle(id="t1", target_agent_role="Buyer", hidden_context_payload={"mood": "calm", "budget": 100}),
                _toggle(id="t2", target_agent_role="Buyer", hidden_context_payload={"mood": "aggressive"}),
                _toggle(id="t3", target_agent_role="Seller", hidden_context_payload={"info": "x"}),
            ]
        )

        result = build_hidden_context(scenario, ["t1", "t2"])

        assert result["Buyer"]["mood"] == "aggressive"
        assert result["Buyer"]["budget"] == 100


# ---------------------------------------------------------------------------
# No toggles — empty list returns empty dict
# ---------------------------------------------------------------------------


class TestNoToggles:
    def test_empty_toggle_list_returns_empty_dict(self):
        scenario = _build_scenario()

        result = build_hidden_context(scenario, [])

        assert result == {}


# ---------------------------------------------------------------------------
# Invalid toggle id raises InvalidToggleError
# ---------------------------------------------------------------------------


class TestInvalidToggle:
    def test_invalid_toggle_id_raises_error(self):
        scenario = _build_scenario()

        with pytest.raises(InvalidToggleError) as exc_info:
            build_hidden_context(scenario, ["nonexistent_toggle"])

        assert exc_info.value.toggle_id == "nonexistent_toggle"
        assert exc_info.value.scenario_id == "test-scenario"

    def test_invalid_toggle_among_valid_ones_raises_error(self):
        """Even if some toggle ids are valid, one bad id should raise."""
        scenario = _build_scenario()

        with pytest.raises(InvalidToggleError) as exc_info:
            build_hidden_context(scenario, ["toggle_buyer", "ghost_toggle"])

        assert exc_info.value.toggle_id == "ghost_toggle"


# ---------------------------------------------------------------------------
# Multiple toggles — different roles produce separate keys
# ---------------------------------------------------------------------------


class TestMultipleTogglesDifferentRoles:
    def test_different_roles_produce_separate_keys(self):
        scenario = _build_scenario()

        result = build_hidden_context(scenario, ["toggle_buyer", "toggle_seller"])

        assert set(result.keys()) == {"Buyer", "Seller"}
        assert result["Buyer"] == {"intel": "debt_info"}
        assert result["Seller"] == {"pressure": "deadline"}

    def test_all_toggles_activated_produces_all_role_keys(self):
        scenario = _build_scenario()

        result = build_hidden_context(scenario, ["toggle_buyer", "toggle_seller", "toggle_buyer_extra"])

        assert set(result.keys()) == {"Buyer", "Seller"}
        assert result["Buyer"] == {"intel": "debt_info", "leverage": "patent"}
        assert result["Seller"] == {"pressure": "deadline"}
