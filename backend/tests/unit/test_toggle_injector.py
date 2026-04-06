"""Unit tests for Toggle Injector.

Tests cover: single toggle injection, multiple toggles same role merge
(shallow merge, last wins on key conflict), no toggles returns empty dict,
invalid toggle raises InvalidToggleError, multiple toggles targeting
different roles produce separate keys, hidden context targets correct agent
in multi-agent scenarios, non-existent agent role validation, empty toggles
leave state unchanged.

Requirements: 5.1, 5.2, 5.3, 5.5, 5.6, 11.1
"""

import copy

import pytest
from pydantic import ValidationError

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


# ---------------------------------------------------------------------------
# Hidden context targets correct agent in multi-agent scenario
# ---------------------------------------------------------------------------


class TestHiddenContextTargetsCorrectAgent:
    """Verify toggle injection adds hidden context only to the targeted agent
    in a scenario with 4 agents (2 negotiators + regulator + observer)."""

    def _four_agent_scenario(self) -> ArenaScenario:
        return ArenaScenario.model_validate(
            _scenario(
                agents=[
                    _agent(role="Buyer", name="Alice", type="negotiator"),
                    _agent(role="Seller", name="Bob", type="negotiator"),
                    _agent(role="Regulator", name="Rex", type="regulator"),
                    _agent(role="Observer", name="Ollie", type="observer"),
                ],
                toggles=[
                    _toggle(
                        id="reg_secret",
                        target_agent_role="Regulator",
                        hidden_context_payload={"compliance_flag": "strict"},
                    ),
                    _toggle(
                        id="buyer_intel",
                        target_agent_role="Buyer",
                        hidden_context_payload={"intel": "debt_info"},
                    ),
                ],
                negotiation_params={
                    "max_turns": 10,
                    "agreement_threshold": 1000.0,
                    "turn_order": ["Buyer", "Seller", "Regulator", "Observer"],
                },
            )
        )

    def test_toggle_targets_regulator_not_others(self):
        scenario = self._four_agent_scenario()

        result = build_hidden_context(scenario, ["reg_secret"])

        assert result == {"Regulator": {"compliance_flag": "strict"}}
        assert "Buyer" not in result
        assert "Seller" not in result
        assert "Observer" not in result

    def test_toggle_payload_matches_definition(self):
        """Hidden context payload must exactly match the toggle definition."""
        scenario = self._four_agent_scenario()

        result = build_hidden_context(scenario, ["buyer_intel"])

        assert result["Buyer"] == {"intel": "debt_info"}


# ---------------------------------------------------------------------------
# Multiple toggles applied to different agents (4-agent scenario)
# ---------------------------------------------------------------------------


class TestMultipleTogglesDifferentAgents:
    """Activate toggles targeting 3 different roles simultaneously."""

    def test_three_roles_receive_independent_contexts(self):
        scenario = ArenaScenario.model_validate(
            _scenario(
                agents=[
                    _agent(role="Buyer", name="Alice", type="negotiator"),
                    _agent(role="Seller", name="Bob", type="negotiator"),
                    _agent(role="Regulator", name="Rex", type="regulator"),
                ],
                toggles=[
                    _toggle(id="t_buy", target_agent_role="Buyer", hidden_context_payload={"edge": "patent"}),
                    _toggle(id="t_sell", target_agent_role="Seller", hidden_context_payload={"pressure": "q4"}),
                    _toggle(id="t_reg", target_agent_role="Regulator", hidden_context_payload={"bias": "lenient"}),
                ],
                negotiation_params={
                    "max_turns": 10,
                    "agreement_threshold": 1000.0,
                    "turn_order": ["Buyer", "Seller", "Regulator"],
                },
            )
        )

        result = build_hidden_context(scenario, ["t_buy", "t_sell", "t_reg"])

        assert set(result.keys()) == {"Buyer", "Seller", "Regulator"}
        assert result["Buyer"] == {"edge": "patent"}
        assert result["Seller"] == {"pressure": "q4"}
        assert result["Regulator"] == {"bias": "lenient"}


# ---------------------------------------------------------------------------
# Toggle targeting non-existent agent role — Pydantic rejects at model level
# ---------------------------------------------------------------------------


class TestToggleNonExistentAgentRole:
    """ArenaScenario's model_validator ensures toggle target_agent_role
    references a valid agent. build_hidden_context never sees bad roles."""

    def test_pydantic_rejects_toggle_targeting_unknown_role(self):
        with pytest.raises(ValidationError, match="Ghost.*not in agents"):
            ArenaScenario.model_validate(
                _scenario(
                    toggles=[
                        _toggle(
                            id="ghost_toggle",
                            target_agent_role="Ghost",
                            hidden_context_payload={"x": 1},
                        ),
                    ],
                )
            )

    def test_pydantic_rejects_mixed_valid_and_invalid_roles(self):
        with pytest.raises(ValidationError, match="Phantom.*not in agents"):
            ArenaScenario.model_validate(
                _scenario(
                    toggles=[
                        _toggle(id="ok", target_agent_role="Buyer", hidden_context_payload={"a": 1}),
                        _toggle(id="bad", target_agent_role="Phantom", hidden_context_payload={"b": 2}),
                    ],
                )
            )


# ---------------------------------------------------------------------------
# Empty toggles list — no changes to state
# ---------------------------------------------------------------------------


class TestEmptyTogglesNoStateChange:
    """Calling build_hidden_context with [] must not mutate the scenario."""

    def test_scenario_unchanged_after_empty_toggle_call(self):
        scenario = _build_scenario()
        original = copy.deepcopy(scenario)

        build_hidden_context(scenario, [])

        assert scenario.model_dump() == original.model_dump()

    def test_scenario_toggles_list_unchanged_after_activation(self):
        """Even with active toggles, the scenario object itself is not mutated."""
        scenario = _build_scenario()
        original_toggles = copy.deepcopy(scenario.toggles)

        build_hidden_context(scenario, ["toggle_buyer"])

        assert scenario.toggles == original_toggles
