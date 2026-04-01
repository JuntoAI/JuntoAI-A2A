"""Unit and integration tests for the agent node factory.

Covers subtasks 5.6–5.10:
- 5.6: _build_prompt with hidden context present/absent, various agent types
- 5.7: _parse_output with valid JSON, invalid JSON
- 5.8: _update_state for each agent type
- 5.9: _advance_turn_order with various lengths and wrap-around
- 5.10: Integration test for full agent node execution with mocked LLM
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.orchestrator.agent_node import (
    _advance_turn_order,
    _build_prompt,
    _parse_output,
    _update_state,
    create_agent_node,
)
from app.orchestrator.exceptions import AgentOutputParseError
from app.orchestrator.outputs import NegotiatorOutput, ObserverOutput, RegulatorOutput
from app.orchestrator.state import NegotiationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(
    role: str = "Buyer",
    name: str = "Alice",
    agent_type: str = "negotiator",
    model_id: str = "gemini-2.5-flash",
    persona_prompt: str = "You are a savvy buyer.",
    goals: list[str] | None = None,
    budget: dict | None = None,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "role": role,
        "name": name,
        "type": agent_type,
        "model_id": model_id,
        "persona_prompt": persona_prompt,
    }
    if goals is not None:
        cfg["goals"] = goals
    if budget is not None:
        cfg["budget"] = budget
    return cfg


def _make_state(
    turn_order: list[str] | None = None,
    turn_order_index: int = 0,
    turn_count: int = 0,
    max_turns: int = 10,
    current_offer: float = 0.0,
    deal_status: str = "Negotiating",
    warning_count: int = 0,
    hidden_context: dict | None = None,
    agent_states: dict | None = None,
    agents: list[dict] | None = None,
    history: list | None = None,
) -> NegotiationState:
    if turn_order is None:
        turn_order = ["Buyer", "Seller"]
    if agents is None:
        agents = [
            _make_agent_config("Buyer", "Alice"),
            _make_agent_config("Seller", "Bob"),
        ]
    if agent_states is None:
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
            "Seller": {"role": "Seller", "name": "Bob", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
        }
    return NegotiationState(
        session_id="test-sess",
        scenario_id="test-scenario",
        turn_count=turn_count,
        max_turns=max_turns,
        current_speaker=turn_order[turn_order_index],
        deal_status=deal_status,
        current_offer=current_offer,
        history=history or [],
        hidden_context=hidden_context or {},
        warning_count=warning_count,
        agreement_threshold=5000.0,
        scenario_config={"id": "test-scenario", "agents": agents, "negotiation_params": {"max_turns": max_turns}},
        turn_order=turn_order,
        turn_order_index=turn_order_index,
        agent_states=agent_states,
        active_toggles=[],
    )


# ===========================================================================
# 5.6: _build_prompt tests
# ===========================================================================


class TestBuildPrompt:
    """Unit tests for _build_prompt()."""

    def test_system_contains_persona(self):
        config = _make_agent_config(persona_prompt="You are a tough negotiator.")
        state = _make_state()
        system, _ = _build_prompt(config, state)
        assert "You are a tough negotiator." in system

    def test_system_contains_goals(self):
        config = _make_agent_config(goals=["Minimize price", "Close quickly"])
        state = _make_state()
        system, _ = _build_prompt(config, state)
        assert "- Minimize price" in system
        assert "- Close quickly" in system

    def test_system_contains_budget(self):
        config = _make_agent_config(budget={"min": 100000, "max": 500000, "target": 300000})
        state = _make_state()
        system, _ = _build_prompt(config, state)
        assert "min=100000" in system
        assert "max=500000" in system
        assert "target=300000" in system

    def test_system_contains_hidden_context_when_present(self):
        config = _make_agent_config(role="Buyer")
        state = _make_state(hidden_context={"Buyer": {"secret": "competing offer at 400k"}})
        system, _ = _build_prompt(config, state)
        assert "Confidential information" in system
        assert "competing offer at 400k" in system

    def test_system_no_hidden_context_when_absent(self):
        config = _make_agent_config(role="Buyer")
        state = _make_state(hidden_context={})
        system, _ = _build_prompt(config, state)
        assert "Confidential" not in system

    def test_system_no_hidden_context_for_other_role(self):
        config = _make_agent_config(role="Buyer")
        state = _make_state(hidden_context={"Seller": {"secret": "info"}})
        system, _ = _build_prompt(config, state)
        assert "Confidential" not in system

    def test_system_contains_output_schema_negotiator(self):
        config = _make_agent_config(agent_type="negotiator")
        state = _make_state()
        system, _ = _build_prompt(config, state)
        assert "proposed_price" in system
        assert "inner_thought" in system

    def test_system_contains_output_schema_regulator(self):
        config = _make_agent_config(agent_type="regulator")
        state = _make_state()
        system, _ = _build_prompt(config, state)
        assert "CLEAR" in system or "status" in system
        assert "reasoning" in system

    def test_system_contains_output_schema_observer(self):
        config = _make_agent_config(agent_type="observer")
        state = _make_state()
        system, _ = _build_prompt(config, state)
        assert "observation" in system
        assert "recommendation" in system

    def test_user_contains_current_offer(self):
        config = _make_agent_config()
        state = _make_state(current_offer=250000.0)
        _, user = _build_prompt(config, state)
        assert "250000.0" in user

    def test_user_contains_turn_info(self):
        config = _make_agent_config()
        state = _make_state(turn_count=3, max_turns=10)
        _, user = _build_prompt(config, state)
        assert "Turn: 3 of 10" in user

    def test_user_contains_json_instruction(self):
        config = _make_agent_config()
        state = _make_state()
        _, user = _build_prompt(config, state)
        assert "Respond with JSON only." in user

    def test_user_contains_history(self):
        config = _make_agent_config()
        state = _make_state(history=[
            {"role": "Buyer", "content": {"public_message": "I offer 300k"}},
        ])
        _, user = _build_prompt(config, state)
        assert "I offer 300k" in user

    def test_hidden_context_string_value(self):
        config = _make_agent_config(role="Buyer")
        state = _make_state(hidden_context={"Buyer": "secret string info"})
        system, _ = _build_prompt(config, state)
        assert "secret string info" in system


# ===========================================================================
# 5.7: _parse_output tests
# ===========================================================================


class TestParseOutput:
    """Unit tests for _parse_output()."""

    def test_valid_negotiator_json(self):
        json_str = '{"inner_thought": "think", "public_message": "say", "proposed_price": 100.0}'
        result = _parse_output(json_str, "negotiator")
        assert isinstance(result, NegotiatorOutput)
        assert result.proposed_price == 100.0

    def test_valid_regulator_json(self):
        json_str = '{"status": "WARNING", "reasoning": "price too high"}'
        result = _parse_output(json_str, "regulator")
        assert isinstance(result, RegulatorOutput)
        assert result.status == "WARNING"

    def test_valid_observer_json(self):
        json_str = '{"observation": "stalemate detected"}'
        result = _parse_output(json_str, "observer")
        assert isinstance(result, ObserverOutput)
        assert result.observation == "stalemate detected"

    def test_invalid_json_raises(self):
        with pytest.raises(AgentOutputParseError):
            _parse_output("not json", "negotiator")

    def test_missing_required_field_raises(self):
        json_str = '{"inner_thought": "x"}'
        with pytest.raises(AgentOutputParseError):
            _parse_output(json_str, "negotiator")

    def test_unknown_agent_type_raises(self):
        with pytest.raises(AgentOutputParseError):
            _parse_output('{"foo": "bar"}', "unknown_type")

    def test_negotiator_with_extra_fields(self):
        json_str = '{"inner_thought": "t", "public_message": "m", "proposed_price": 50.0, "extra_fields": {"urgency": "high"}}'
        result = _parse_output(json_str, "negotiator")
        assert result.extra_fields == {"urgency": "high"}


# ===========================================================================
# 5.8: _update_state tests
# ===========================================================================


class TestUpdateStateNegotiator:
    """_update_state for negotiator type."""

    def test_updates_current_offer(self):
        parsed = NegotiatorOutput(inner_thought="t", public_message="m", proposed_price=350000.0)
        state = _make_state(current_offer=0.0)
        delta = _update_state(parsed, "negotiator", "Buyer", state)
        assert delta["current_offer"] == 350000.0

    def test_updates_agent_states_last_proposed_price(self):
        parsed = NegotiatorOutput(inner_thought="t", public_message="m", proposed_price=350000.0)
        state = _make_state()
        delta = _update_state(parsed, "negotiator", "Buyer", state)
        assert delta["agent_states"]["Buyer"]["last_proposed_price"] == 350000.0

    def test_preserves_other_agent_states(self):
        parsed = NegotiatorOutput(inner_thought="t", public_message="m", proposed_price=100.0)
        state = _make_state()
        delta = _update_state(parsed, "negotiator", "Buyer", state)
        # Seller's state should be unchanged
        assert delta["agent_states"]["Seller"]["last_proposed_price"] == 0.0

    def test_appends_history_entry(self):
        parsed = NegotiatorOutput(inner_thought="t", public_message="m", proposed_price=100.0)
        state = _make_state(turn_count=2)
        delta = _update_state(parsed, "negotiator", "Buyer", state)
        assert len(delta["history"]) == 1
        entry = delta["history"][0]
        assert entry["role"] == "Buyer"
        assert entry["agent_type"] == "negotiator"
        assert entry["turn_number"] == 2
        assert entry["content"]["proposed_price"] == 100.0


class TestUpdateStateRegulator:
    """_update_state for regulator type."""

    def test_warning_increments_global_warning_count(self):
        parsed = RegulatorOutput(status="WARNING", reasoning="too high")
        agents = [
            _make_agent_config("Buyer", "Alice"),
            _make_agent_config("Regulator", "Carol", agent_type="regulator"),
        ]
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
            "Regulator": {"role": "Regulator", "name": "Carol", "agent_type": "regulator", "model_id": "claude-sonnet-4-6", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(warning_count=1, agents=agents, agent_states=agent_states, turn_order=["Buyer", "Regulator"])
        delta = _update_state(parsed, "regulator", "Regulator", state)
        assert delta["warning_count"] == 2

    def test_warning_increments_role_warning_count(self):
        parsed = RegulatorOutput(status="WARNING", reasoning="too high")
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
            "Regulator": {"role": "Regulator", "name": "Carol", "agent_type": "regulator", "model_id": "claude-sonnet-4-6", "last_proposed_price": 0.0, "warning_count": 1},
        }
        state = _make_state(warning_count=1, agent_states=agent_states, turn_order=["Buyer", "Regulator"])
        delta = _update_state(parsed, "regulator", "Regulator", state)
        assert delta["agent_states"]["Regulator"]["warning_count"] == 2

    def test_clear_does_not_increment(self):
        parsed = RegulatorOutput(status="CLEAR", reasoning="all good")
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
            "Regulator": {"role": "Regulator", "name": "Carol", "agent_type": "regulator", "model_id": "claude-sonnet-4-6", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(warning_count=0, agent_states=agent_states, turn_order=["Buyer", "Regulator"])
        delta = _update_state(parsed, "regulator", "Regulator", state)
        assert delta["warning_count"] == 0
        assert delta["agent_states"]["Regulator"]["warning_count"] == 0

    def test_blocked_status_sets_deal_blocked(self):
        parsed = RegulatorOutput(status="BLOCKED", reasoning="violation")
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
            "Regulator": {"role": "Regulator", "name": "Carol", "agent_type": "regulator", "model_id": "claude-sonnet-4-6", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(agent_states=agent_states, turn_order=["Buyer", "Regulator"])
        delta = _update_state(parsed, "regulator", "Regulator", state)
        assert delta["deal_status"] == "Blocked"

    def test_three_warnings_blocks_deal(self):
        parsed = RegulatorOutput(status="WARNING", reasoning="third warning")
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
            "Regulator": {"role": "Regulator", "name": "Carol", "agent_type": "regulator", "model_id": "claude-sonnet-4-6", "last_proposed_price": 0.0, "warning_count": 2},
        }
        state = _make_state(warning_count=2, agent_states=agent_states, turn_order=["Buyer", "Regulator"])
        delta = _update_state(parsed, "regulator", "Regulator", state)
        assert delta["agent_states"]["Regulator"]["warning_count"] == 3
        assert delta["deal_status"] == "Blocked"

    def test_appends_history_entry(self):
        parsed = RegulatorOutput(status="CLEAR", reasoning="ok")
        agent_states = {
            "Regulator": {"role": "Regulator", "name": "Carol", "agent_type": "regulator", "model_id": "claude-sonnet-4-6", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(agent_states=agent_states, turn_order=["Regulator"], turn_count=1)
        delta = _update_state(parsed, "regulator", "Regulator", state)
        assert len(delta["history"]) == 1
        assert delta["history"][0]["agent_type"] == "regulator"
        assert delta["history"][0]["turn_number"] == 1


class TestUpdateStateObserver:
    """_update_state for observer type."""

    def test_only_appends_history(self):
        parsed = ObserverOutput(observation="stalemate detected", recommendation="split")
        agent_states = {
            "Analyst": {"role": "Analyst", "name": "Dave", "agent_type": "observer", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(
            current_offer=500.0,
            deal_status="Negotiating",
            warning_count=1,
            agent_states=agent_states,
            turn_order=["Analyst"],
        )
        delta = _update_state(parsed, "observer", "Analyst", state)

        # Only history should be in delta
        assert "history" in delta
        assert len(delta["history"]) == 1
        assert "current_offer" not in delta
        assert "deal_status" not in delta
        assert "warning_count" not in delta
        assert "agent_states" not in delta

    def test_history_entry_format(self):
        parsed = ObserverOutput(observation="noted")
        agent_states = {
            "Analyst": {"role": "Analyst", "name": "Dave", "agent_type": "observer", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(agent_states=agent_states, turn_order=["Analyst"], turn_count=5)
        delta = _update_state(parsed, "observer", "Analyst", state)
        entry = delta["history"][0]
        assert entry["role"] == "Analyst"
        assert entry["agent_type"] == "observer"
        assert entry["turn_number"] == 5
        assert entry["content"]["observation"] == "noted"


# ===========================================================================
# 5.9: _advance_turn_order tests
# ===========================================================================


class TestAdvanceTurnOrder:
    """Unit tests for _advance_turn_order()."""

    def test_simple_advance(self):
        state = _make_state(turn_order=["Buyer", "Seller"], turn_order_index=0, turn_count=0)
        delta = _advance_turn_order(state)
        assert delta["turn_order_index"] == 1
        assert delta["current_speaker"] == "Seller"
        assert "turn_count" not in delta

    def test_wrap_around_increments_turn_count(self):
        state = _make_state(turn_order=["Buyer", "Seller"], turn_order_index=1, turn_count=0)
        delta = _advance_turn_order(state)
        assert delta["turn_order_index"] == 0
        assert delta["current_speaker"] == "Buyer"
        assert delta["turn_count"] == 1

    def test_three_element_turn_order(self):
        state = _make_state(turn_order=["A", "B", "C"], turn_order_index=1, turn_count=0)
        delta = _advance_turn_order(state)
        assert delta["turn_order_index"] == 2
        assert delta["current_speaker"] == "C"

    def test_three_element_wrap(self):
        state = _make_state(turn_order=["A", "B", "C"], turn_order_index=2, turn_count=3)
        delta = _advance_turn_order(state)
        assert delta["turn_order_index"] == 0
        assert delta["current_speaker"] == "A"
        assert delta["turn_count"] == 4

    def test_single_element_always_wraps(self):
        state = _make_state(turn_order=["Solo"], turn_order_index=0, turn_count=0)
        delta = _advance_turn_order(state)
        assert delta["turn_order_index"] == 0
        assert delta["current_speaker"] == "Solo"
        assert delta["turn_count"] == 1

    def test_four_element_mid_advance(self):
        state = _make_state(turn_order=["A", "B", "C", "D"], turn_order_index=2, turn_count=0)
        delta = _advance_turn_order(state)
        assert delta["turn_order_index"] == 3
        assert delta["current_speaker"] == "D"

    def test_empty_turn_order_returns_empty(self):
        # Build state manually to avoid IndexError in helper
        state = NegotiationState(
            session_id="test", scenario_id="test", turn_count=0, max_turns=10,
            current_speaker="", deal_status="Negotiating", current_offer=0.0,
            history=[], hidden_context={}, warning_count=0, agreement_threshold=5000.0,
            scenario_config={}, turn_order=[], turn_order_index=0, agent_states={},
            active_toggles=[],
        )
        delta = _advance_turn_order(state)
        assert delta == {}


# ===========================================================================
# 5.10: Integration test — full agent node with mocked LLM
# ===========================================================================


class TestAgentNodeIntegration:
    """Integration test for create_agent_node with mocked LLM client."""

    @patch("app.orchestrator.agent_node.model_router")
    def test_negotiator_node_full_execution(self, mock_router):
        """Full pipeline: create node → invoke → verify state delta."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(
            content='{"inner_thought": "lowball", "public_message": "I offer 300k", "proposed_price": 300000.0}'
        )
        mock_router.get_model.return_value = mock_model

        agents = [_make_agent_config("Buyer", "Alice", "negotiator", "gemini-2.5-flash", "You are a buyer.")]
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(
            turn_order=["Buyer"],
            turn_order_index=0,
            turn_count=0,
            agents=agents,
            agent_states=agent_states,
        )

        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert result["current_offer"] == 300000.0
        assert result["agent_states"]["Buyer"]["last_proposed_price"] == 300000.0
        assert len(result["history"]) == 1
        assert result["history"][0]["role"] == "Buyer"
        # Turn should advance: single-element wraps
        assert result["turn_order_index"] == 0
        assert result["turn_count"] == 1

    @patch("app.orchestrator.agent_node.model_router")
    def test_regulator_node_warning(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(
            content='{"status": "WARNING", "reasoning": "price seems inflated"}'
        )
        mock_router.get_model.return_value = mock_model

        agents = [
            _make_agent_config("Buyer", "Alice"),
            _make_agent_config("Regulator", "Carol", "regulator", "claude-sonnet-4-6", "You are a regulator."),
        ]
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
            "Regulator": {"role": "Regulator", "name": "Carol", "agent_type": "regulator", "model_id": "claude-sonnet-4-6", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(
            turn_order=["Buyer", "Regulator"],
            turn_order_index=1,
            turn_count=0,
            agents=agents,
            agent_states=agent_states,
        )

        node_fn = create_agent_node("Regulator")
        result = node_fn(state)

        assert result["warning_count"] == 1
        assert result["agent_states"]["Regulator"]["warning_count"] == 1
        assert result["history"][0]["agent_type"] == "regulator"
        # Wraps back to 0
        assert result["turn_order_index"] == 0
        assert result["turn_count"] == 1

    @patch("app.orchestrator.agent_node.model_router")
    def test_observer_node_read_only(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(
            content='{"observation": "stalemate detected", "recommendation": "split the difference"}'
        )
        mock_router.get_model.return_value = mock_model

        agents = [_make_agent_config("Analyst", "Dave", "observer", "gemini-2.5-flash", "You observe.")]
        agent_states = {
            "Analyst": {"role": "Analyst", "name": "Dave", "agent_type": "observer", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(
            turn_order=["Analyst"],
            turn_order_index=0,
            turn_count=0,
            current_offer=500.0,
            warning_count=2,
            agents=agents,
            agent_states=agent_states,
        )

        node_fn = create_agent_node("Analyst")
        result = node_fn(state)

        # Observer should NOT change these
        assert "current_offer" not in result or result.get("current_offer") is None
        assert "deal_status" not in result or result.get("deal_status") is None
        # History should be appended
        assert len(result["history"]) == 1
        assert result["history"][0]["content"]["observation"] == "stalemate detected"

    @patch("app.orchestrator.agent_node.model_router")
    def test_retry_on_parse_failure(self, mock_router):
        """First LLM call returns garbage, retry returns valid JSON."""
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content="not valid json at all"),
            AIMessage(content='{"inner_thought": "retry", "public_message": "ok", "proposed_price": 42.0}'),
        ]
        mock_router.get_model.return_value = mock_model

        agents = [_make_agent_config("Buyer", "Alice", "negotiator", "gemini-2.5-flash", "You buy.")]
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(turn_order=["Buyer"], agents=agents, agent_states=agent_states)

        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert result["current_offer"] == 42.0
        assert mock_model.invoke.call_count == 2

    @patch("app.orchestrator.agent_node.model_router")
    def test_double_parse_failure_raises(self, mock_router):
        """Both LLM calls return garbage → AgentOutputParseError."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content="still not json")
        mock_router.get_model.return_value = mock_model

        agents = [_make_agent_config("Buyer", "Alice", "negotiator", "gemini-2.5-flash", "You buy.")]
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-2.5-flash", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(turn_order=["Buyer"], agents=agents, agent_states=agent_states)

        node_fn = create_agent_node("Buyer")
        with pytest.raises(AgentOutputParseError):
            node_fn(state)

    @patch("app.orchestrator.agent_node.model_router")
    def test_missing_role_raises(self, mock_router):
        """Agent role not in scenario_config raises AgentOutputParseError."""
        state = _make_state()
        node_fn = create_agent_node("NonExistentRole")
        with pytest.raises(AgentOutputParseError):
            node_fn(state)
