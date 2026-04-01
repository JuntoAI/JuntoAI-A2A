"""Unit tests for NegotiationState TypedDict and create_initial_state() factory."""

import pytest

from app.orchestrator.state import NegotiationState, create_initial_state


# ---------------------------------------------------------------------------
# Helpers — scenario config factories
# ---------------------------------------------------------------------------


def _make_agent(role: str, name: str, agent_type: str = "negotiator", model_id: str = "gemini-2.5-flash") -> dict:
    return {"role": role, "name": name, "type": agent_type, "model_id": model_id}


def _make_config(agents: list[dict], turn_order: list[str] | None = None, **params) -> dict:
    neg_params: dict = {"max_turns": 10, "agreement_threshold": 5000.0}
    if turn_order is not None:
        neg_params["turn_order"] = turn_order
    neg_params.update(params)
    return {"id": "scenario-001", "agents": agents, "negotiation_params": neg_params}


# ---------------------------------------------------------------------------
# 2-agent scenarios
# ---------------------------------------------------------------------------


class TestCreateInitialState2Agent:
    """create_initial_state with 2-agent configs (buyer + seller)."""

    def test_explicit_turn_order(self):
        agents = [_make_agent("Buyer", "Alice"), _make_agent("Seller", "Bob")]
        config = _make_config(agents, turn_order=["Buyer", "Seller"])
        state = create_initial_state("sess-1", config)

        assert state["session_id"] == "sess-1"
        assert state["scenario_id"] == "scenario-001"
        assert state["turn_order"] == ["Buyer", "Seller"]
        assert state["current_speaker"] == "Buyer"
        assert state["turn_count"] == 0
        assert state["max_turns"] == 10
        assert state["deal_status"] == "Negotiating"
        assert state["current_offer"] == 0.0
        assert state["history"] == []
        assert state["warning_count"] == 0
        assert state["agreement_threshold"] == 5000.0
        assert state["turn_order_index"] == 0
        assert state["active_toggles"] == []

    def test_derived_turn_order_no_regulators(self):
        agents = [_make_agent("Buyer", "Alice"), _make_agent("Seller", "Bob")]
        config = _make_config(agents)
        state = create_initial_state("sess-2", config)

        # No regulators → just negotiators in order
        assert state["turn_order"] == ["Buyer", "Seller"]

    def test_agent_states_populated(self):
        agents = [_make_agent("Buyer", "Alice"), _make_agent("Seller", "Bob")]
        config = _make_config(agents)
        state = create_initial_state("sess-3", config)

        assert set(state["agent_states"].keys()) == {"Buyer", "Seller"}
        buyer = state["agent_states"]["Buyer"]
        assert buyer["role"] == "Buyer"
        assert buyer["name"] == "Alice"
        assert buyer["agent_type"] == "negotiator"
        assert buyer["model_id"] == "gemini-2.5-flash"
        assert buyer["last_proposed_price"] == 0.0
        assert buyer["warning_count"] == 0


# ---------------------------------------------------------------------------
# 3-agent scenarios (negotiator + negotiator + regulator)
# ---------------------------------------------------------------------------


class TestCreateInitialState3Agent:
    """create_initial_state with 3-agent configs."""

    def test_derived_turn_order_with_regulator(self):
        agents = [
            _make_agent("Buyer", "Alice"),
            _make_agent("Seller", "Bob"),
            _make_agent("Regulator", "Carol", agent_type="regulator", model_id="claude-sonnet-4"),
        ]
        config = _make_config(agents)
        state = create_initial_state("sess-4", config)

        # Interleave: Buyer, Regulator, Seller, Regulator
        assert state["turn_order"] == ["Buyer", "Regulator", "Seller", "Regulator"]
        assert state["current_speaker"] == "Buyer"

    def test_explicit_turn_order_overrides_derivation(self):
        agents = [
            _make_agent("Buyer", "Alice"),
            _make_agent("Seller", "Bob"),
            _make_agent("Regulator", "Carol", agent_type="regulator"),
        ]
        config = _make_config(agents, turn_order=["Seller", "Buyer", "Regulator"])
        state = create_initial_state("sess-5", config)

        assert state["turn_order"] == ["Seller", "Buyer", "Regulator"]
        assert state["current_speaker"] == "Seller"


# ---------------------------------------------------------------------------
# 4-agent scenarios (2 negotiators + 1 regulator + 1 observer)
# ---------------------------------------------------------------------------


class TestCreateInitialState4Agent:
    """create_initial_state with 4-agent configs."""

    def test_derived_turn_order_with_observer(self):
        agents = [
            _make_agent("Buyer", "Alice"),
            _make_agent("Seller", "Bob"),
            _make_agent("Regulator", "Carol", agent_type="regulator"),
            _make_agent("Analyst", "Dave", agent_type="observer"),
        ]
        config = _make_config(agents)
        state = create_initial_state("sess-6", config)

        # Interleave negotiators with regulators, then observers at end
        assert state["turn_order"] == ["Buyer", "Regulator", "Seller", "Regulator", "Analyst"]
        assert len(state["agent_states"]) == 4
        assert state["agent_states"]["Analyst"]["agent_type"] == "observer"

    def test_all_agent_states_have_required_keys(self):
        agents = [
            _make_agent("Buyer", "Alice"),
            _make_agent("Seller", "Bob"),
            _make_agent("Regulator", "Carol", agent_type="regulator"),
            _make_agent("Analyst", "Dave", agent_type="observer"),
        ]
        config = _make_config(agents)
        state = create_initial_state("sess-7", config)

        required_keys = {"role", "name", "agent_type", "model_id", "last_proposed_price", "warning_count"}
        for role, agent_state in state["agent_states"].items():
            assert set(agent_state.keys()) == required_keys, f"Missing keys for {role}"


# ---------------------------------------------------------------------------
# Optional parameters
# ---------------------------------------------------------------------------


class TestCreateInitialStateOptionals:
    """active_toggles and hidden_context optional params."""

    def test_active_toggles_passed(self):
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"])
        state = create_initial_state("sess-8", config, active_toggles=["secret_offer"])

        assert state["active_toggles"] == ["secret_offer"]

    def test_hidden_context_passed(self):
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"])
        ctx = {"Buyer": {"secret": "competing offer at 400k"}}
        state = create_initial_state("sess-9", config, hidden_context=ctx)

        assert state["hidden_context"] == ctx

    def test_defaults_when_none(self):
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"])
        state = create_initial_state("sess-10", config)

        assert state["active_toggles"] == []
        assert state["hidden_context"] == {}

    def test_scenario_config_stored(self):
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"])
        state = create_initial_state("sess-11", config)

        assert state["scenario_config"] is config

    def test_default_max_turns(self):
        """When max_turns is absent from negotiation_params, defaults to 15."""
        agents = [_make_agent("Buyer", "Alice")]
        config = {"id": "s1", "agents": agents, "negotiation_params": {}}
        config["negotiation_params"]["turn_order"] = ["Buyer"]
        state = create_initial_state("sess-12", config)

        assert state["max_turns"] == 15

    def test_default_agreement_threshold(self):
        """When agreement_threshold is absent, defaults to 1_000_000."""
        agents = [_make_agent("Buyer", "Alice")]
        config = {"id": "s1", "agents": agents, "negotiation_params": {"turn_order": ["Buyer"]}}
        state = create_initial_state("sess-13", config)

        assert state["agreement_threshold"] == 1_000_000.0
