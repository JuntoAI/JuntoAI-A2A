"""Unit tests for to_pydantic() and from_pydantic() state converters."""

from app.models.negotiation import NegotiationStateModel
from app.orchestrator.converters import from_pydantic, to_pydantic
from app.orchestrator.state import NegotiationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _full_state(**overrides) -> NegotiationState:
    defaults: dict = {
        "session_id": "sess-1",
        "scenario_id": "scen-1",
        "turn_count": 2,
        "max_turns": 10,
        "current_speaker": "Buyer",
        "deal_status": "Negotiating",
        "current_offer": 500_000.0,
        "history": [{"role": "Buyer", "msg": "offer 500k"}],
        "hidden_context": {"Buyer": {"secret": "competing offer"}},
        "warning_count": 1,
        "agreement_threshold": 5000.0,
        "scenario_config": {"id": "scen-1", "agents": []},
        "turn_order": ["Buyer", "Regulator", "Seller"],
        "turn_order_index": 1,
        "agent_states": {
            "Buyer": {
                "role": "Buyer",
                "name": "Alice",
                "agent_type": "negotiator",
                "model_id": "gemini-3-flash-preview",
                "last_proposed_price": 500_000.0,
                "warning_count": 0,
            },
        },
        "active_toggles": ["secret_offer"],
        "total_tokens_used": 0,
        "stall_diagnosis": None,
    }
    defaults.update(overrides)
    return NegotiationState(**defaults)


# ---------------------------------------------------------------------------
# to_pydantic tests
# ---------------------------------------------------------------------------


class TestToPydantic:
    def test_basic_conversion(self):
        state = _full_state()
        model = to_pydantic(state)

        assert isinstance(model, NegotiationStateModel)
        assert model.session_id == "sess-1"
        assert model.scenario_id == "scen-1"
        assert model.turn_count == 2
        assert model.max_turns == 10
        assert model.current_speaker == "Buyer"
        assert model.deal_status == "Negotiating"
        assert model.current_offer == 500_000.0
        assert model.warning_count == 1
        assert model.agreement_threshold == 5000.0

    def test_turn_order_preserved(self):
        state = _full_state()
        model = to_pydantic(state)

        assert model.turn_order == ["Buyer", "Regulator", "Seller"]
        assert model.turn_order_index == 1

    def test_agent_states_preserved(self):
        state = _full_state()
        model = to_pydantic(state)

        assert "Buyer" in model.agent_states
        assert model.agent_states["Buyer"]["name"] == "Alice"
        assert model.agent_states["Buyer"]["last_proposed_price"] == 500_000.0

    def test_history_preserved(self):
        state = _full_state()
        model = to_pydantic(state)

        assert model.history == [{"role": "Buyer", "msg": "offer 500k"}]

    def test_active_toggles_preserved(self):
        state = _full_state()
        model = to_pydantic(state)

        assert model.active_toggles == ["secret_offer"]

    def test_scenario_config_dropped(self):
        """NegotiationStateModel has no scenario_config field — it should be silently dropped."""
        state = _full_state(scenario_config={"id": "big-config", "agents": [1, 2, 3]})
        model = to_pydantic(state)

        assert not hasattr(model, "scenario_config")


# ---------------------------------------------------------------------------
# from_pydantic tests
# ---------------------------------------------------------------------------


class TestFromPydantic:
    def test_basic_conversion(self):
        model = NegotiationStateModel(
            session_id="sess-1",
            scenario_id="scen-1",
            turn_count=3,
            max_turns=15,
            current_speaker="Seller",
            deal_status="Negotiating",
            current_offer=750_000.0,
            history=[],
            warning_count=0,
            hidden_context={},
            agreement_threshold=10_000.0,
            turn_order=["Buyer", "Seller"],
            turn_order_index=1,
            agent_states={},
            active_toggles=[],
        )
        state = from_pydantic(model)

        assert state["session_id"] == "sess-1"
        assert state["turn_count"] == 3
        assert state["current_speaker"] == "Seller"
        assert state["current_offer"] == 750_000.0

    def test_scenario_config_set_to_empty_dict(self):
        """from_pydantic must set scenario_config to {} since the Pydantic model doesn't carry it."""
        model = NegotiationStateModel(
            session_id="s", scenario_id="sc",
            turn_order=["A"], turn_order_index=0, agent_states={},
        )
        state = from_pydantic(model)

        assert state["scenario_config"] == {}

    def test_agent_states_round_trip(self):
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator",
                       "model_id": "gemini-3-flash-preview", "last_proposed_price": 100.0, "warning_count": 0},
            "Seller": {"role": "Seller", "name": "Bob", "agent_type": "negotiator",
                        "model_id": "claude-sonnet-4-6", "last_proposed_price": 200.0, "warning_count": 0},
        }
        model = NegotiationStateModel(
            session_id="s", scenario_id="sc",
            turn_order=["Buyer", "Seller"], turn_order_index=0,
            agent_states=agent_states,
        )
        state = from_pydantic(model)

        assert state["agent_states"] == agent_states


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestConverterEdgeCases:
    def test_empty_agent_states(self):
        state = _full_state(agent_states={})
        model = to_pydantic(state)
        assert model.agent_states == {}

        restored = from_pydantic(model)
        assert restored["agent_states"] == {}

    def test_empty_history(self):
        state = _full_state(history=[])
        model = to_pydantic(state)
        assert model.history == []

        restored = from_pydantic(model)
        assert restored["history"] == []

    def test_empty_active_toggles(self):
        state = _full_state(active_toggles=[])
        model = to_pydantic(state)
        assert model.active_toggles == []

        restored = from_pydantic(model)
        assert restored["active_toggles"] == []

    def test_empty_hidden_context(self):
        state = _full_state(hidden_context={})
        model = to_pydantic(state)
        assert model.hidden_context == {}

        restored = from_pydantic(model)
        assert restored["hidden_context"] == {}

    def test_round_trip_loses_scenario_config(self):
        """Round-trip drops scenario_config and stall_diagnosis (Pydantic model doesn't have them)."""
        state = _full_state(scenario_config={"id": "x", "agents": [{"role": "A"}]})
        restored = from_pydantic(to_pydantic(state))

        assert restored["scenario_config"] == {}
        # All other fields should match (stall_diagnosis resets to None)
        for key in state:
            if key in ("scenario_config", "stall_diagnosis"):
                continue
            assert restored[key] == state[key], f"Mismatch on {key}"

    def test_multiple_agent_states(self):
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "A", "agent_type": "negotiator",
                       "model_id": "m1", "last_proposed_price": 0.0, "warning_count": 0},
            "Seller": {"role": "Seller", "name": "B", "agent_type": "negotiator",
                        "model_id": "m2", "last_proposed_price": 0.0, "warning_count": 0},
            "Reg": {"role": "Reg", "name": "C", "agent_type": "regulator",
                     "model_id": "m3", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _full_state(agent_states=agent_states)
        model = to_pydantic(state)
        restored = from_pydantic(model)

        assert restored["agent_states"] == agent_states
