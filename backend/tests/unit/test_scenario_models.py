"""Unit tests for Scenario Engine Pydantic V2 models.

Tests cover: Budget, AgentDefinition, ToggleDefinition, NegotiationParams,
OutcomeReceipt, and ArenaScenario (including cross-reference validation).

Requirements: 1.1–1.12, 2.5, 2.6
"""

import pytest
from pydantic import ValidationError

from app.scenarios.models import (
    AgentDefinition,
    ArenaScenario,
    Budget,
    NegotiationParams,
    OutcomeReceipt,
    ToggleDefinition,
)


# ---------------------------------------------------------------------------
# Helpers — minimal valid fixtures
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
# Budget
# ---------------------------------------------------------------------------

class TestBudget:
    def test_valid_budget(self):
        b = Budget(min=100, max=200, target=150)
        assert b.min == 100
        assert b.max == 200
        assert b.target == 150

    def test_min_equals_max_is_valid(self):
        b = Budget(min=100, max=100, target=100)
        assert b.min == b.max

    def test_min_greater_than_max_rejected(self):
        with pytest.raises(ValidationError, match="min.*must be <= max"):
            Budget(min=300, max=100, target=150)

    def test_negative_values_rejected(self):
        with pytest.raises(ValidationError):
            Budget(min=-1, max=200, target=150)


# ---------------------------------------------------------------------------
# AgentDefinition
# ---------------------------------------------------------------------------

class TestAgentDefinition:
    def test_valid_agent(self):
        agent = AgentDefinition(**_agent())
        assert agent.role == "Buyer"
        assert agent.type == "negotiator"
        assert agent.fallback_model_id is None

    def test_with_fallback_model(self):
        agent = AgentDefinition(**_agent(fallback_model_id="gemini-2.5-pro"))
        assert agent.fallback_model_id == "gemini-2.5-pro"

    def test_missing_role_rejected(self):
        data = _agent()
        del data["role"]
        with pytest.raises(ValidationError):
            AgentDefinition(**data)

    def test_empty_role_rejected(self):
        with pytest.raises(ValidationError):
            AgentDefinition(**_agent(role=""))

    def test_empty_goals_rejected(self):
        with pytest.raises(ValidationError):
            AgentDefinition(**_agent(goals=[]))

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            AgentDefinition(**_agent(type="invalid_type"))

    def test_all_valid_types(self):
        for t in ("negotiator", "regulator", "observer"):
            agent = AgentDefinition(**_agent(type=t))
            assert agent.type == t


# ---------------------------------------------------------------------------
# ToggleDefinition
# ---------------------------------------------------------------------------

class TestToggleDefinition:
    def test_valid_toggle(self):
        toggle = ToggleDefinition(**_toggle())
        assert toggle.id == "toggle_1"
        assert toggle.hidden_context_payload == {"secret": "value"}

    def test_empty_hidden_context_payload_rejected(self):
        with pytest.raises(ValidationError):
            ToggleDefinition(**_toggle(hidden_context_payload={}))

    def test_missing_id_rejected(self):
        data = _toggle()
        del data["id"]
        with pytest.raises(ValidationError):
            ToggleDefinition(**data)


# ---------------------------------------------------------------------------
# NegotiationParams
# ---------------------------------------------------------------------------

class TestNegotiationParams:
    def test_valid_params(self):
        params = NegotiationParams(**_negotiation_params())
        assert params.max_turns == 10

    def test_zero_max_turns_rejected(self):
        with pytest.raises(ValidationError):
            NegotiationParams(**_negotiation_params(max_turns=0))

    def test_empty_turn_order_rejected(self):
        with pytest.raises(ValidationError):
            NegotiationParams(**_negotiation_params(turn_order=[]))


# ---------------------------------------------------------------------------
# OutcomeReceipt
# ---------------------------------------------------------------------------

class TestOutcomeReceipt:
    def test_valid_receipt(self):
        receipt = OutcomeReceipt(**_outcome_receipt())
        assert receipt.process_label == "Acquisition"

    def test_empty_field_rejected(self):
        with pytest.raises(ValidationError):
            OutcomeReceipt(equivalent_human_time="", process_label="X")


# ---------------------------------------------------------------------------
# ArenaScenario — happy path
# ---------------------------------------------------------------------------

class TestArenaScenarioValid:
    def test_valid_scenario(self):
        scenario = ArenaScenario(**_scenario())
        assert scenario.id == "test-scenario"
        assert len(scenario.agents) == 2
        assert len(scenario.toggles) == 1

    def test_three_agents_with_observer(self):
        agents = [
            _agent(role="Buyer", name="A"),
            _agent(role="Seller", name="B"),
            _agent(role="Watcher", name="C", type="observer"),
        ]
        s = ArenaScenario(**_scenario(
            agents=agents,
            negotiation_params=_negotiation_params(turn_order=["Buyer", "Seller", "Watcher"]),
        ))
        assert len(s.agents) == 3


# ---------------------------------------------------------------------------
# ArenaScenario — cross-reference validation
# ---------------------------------------------------------------------------

class TestArenaScenarioCrossRef:
    def test_duplicate_agent_roles_rejected(self):
        agents = [
            _agent(role="Buyer", name="A"),
            _agent(role="Buyer", name="B"),
        ]
        with pytest.raises(ValidationError, match="Duplicate agent roles"):
            ArenaScenario(**_scenario(agents=agents))

    def test_invalid_toggle_target_role_rejected(self):
        toggles = [_toggle(target_agent_role="NonExistentRole")]
        with pytest.raises(ValidationError, match="not in agents"):
            ArenaScenario(**_scenario(toggles=toggles))

    def test_invalid_turn_order_entry_rejected(self):
        params = _negotiation_params(turn_order=["Buyer", "Ghost"])
        with pytest.raises(ValidationError, match="not a valid agent role"):
            ArenaScenario(**_scenario(negotiation_params=params))

    def test_no_negotiator_agent_rejected(self):
        agents = [
            _agent(role="Watcher1", name="A", type="regulator"),
            _agent(role="Watcher2", name="B", type="observer"),
        ]
        params = _negotiation_params(turn_order=["Watcher1", "Watcher2"])
        toggles = [_toggle(target_agent_role="Watcher1")]
        with pytest.raises(ValidationError, match="At least one agent must have type"):
            ArenaScenario(**_scenario(
                agents=agents,
                negotiation_params=params,
                toggles=toggles,
            ))

    def test_single_agent_rejected(self):
        """min_length=2 on agents field."""
        with pytest.raises(ValidationError):
            ArenaScenario(**_scenario(agents=[_agent()]))

    def test_no_toggles_rejected(self):
        """min_length=1 on toggles field."""
        with pytest.raises(ValidationError):
            ArenaScenario(**_scenario(toggles=[]))
