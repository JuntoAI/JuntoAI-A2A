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
        "custom_prompts": {},
        "model_overrides": {},
        "structured_memory_enabled": False,
        "structured_memory_roles": [],
        "agent_memories": {},
        "milestone_summaries_enabled": False,
        "milestone_summaries": {},
        "sliding_window_size": 3,
        "milestone_interval": 4,
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


# ---------------------------------------------------------------------------
# Milestone field round-trip tests
# ---------------------------------------------------------------------------


class TestMilestoneFieldsRoundTrip:
    """Validates: Requirements 2.8, 10.1, 10.3"""

    def test_to_pydantic_passes_milestone_fields(self):
        summaries = {
            "Buyer": [{"turn_number": 4, "summary": "Buyer opened at 500k"}],
        }
        state = _full_state(
            milestone_summaries_enabled=True,
            milestone_summaries=summaries,
            sliding_window_size=5,
            milestone_interval=6,
        )
        model = to_pydantic(state)

        assert model.milestone_summaries_enabled is True
        assert model.milestone_summaries == summaries
        assert model.sliding_window_size == 5
        assert model.milestone_interval == 6

    def test_from_pydantic_passes_milestone_fields(self):
        summaries = {
            "Seller": [{"turn_number": 8, "summary": "Seller conceded on price"}],
        }
        model = NegotiationStateModel(
            session_id="s",
            scenario_id="sc",
            turn_order=["Buyer", "Seller"],
            turn_order_index=0,
            agent_states={},
            milestone_summaries_enabled=True,
            milestone_summaries=summaries,
            sliding_window_size=7,
            milestone_interval=3,
        )
        state = from_pydantic(model)

        assert state["milestone_summaries_enabled"] is True
        assert state["milestone_summaries"] == summaries
        assert state["sliding_window_size"] == 7
        assert state["milestone_interval"] == 3

    def test_round_trip_preserves_all_milestone_fields(self):
        summaries = {
            "Buyer": [
                {"turn_number": 4, "summary": "Initial positions established"},
                {"turn_number": 8, "summary": "Progress on salary band"},
            ],
            "Seller": [
                {"turn_number": 4, "summary": "Buyer seems flexible on timeline"},
            ],
        }
        state = _full_state(
            milestone_summaries_enabled=True,
            milestone_summaries=summaries,
            sliding_window_size=5,
            milestone_interval=4,
        )
        restored = from_pydantic(to_pydantic(state))

        assert restored["milestone_summaries_enabled"] is True
        assert restored["milestone_summaries"] == summaries
        assert restored["sliding_window_size"] == 5
        assert restored["milestone_interval"] == 4

    def test_round_trip_disabled_milestone_fields(self):
        state = _full_state(
            milestone_summaries_enabled=False,
            milestone_summaries={},
            sliding_window_size=3,
            milestone_interval=4,
        )
        restored = from_pydantic(to_pydantic(state))

        assert restored["milestone_summaries_enabled"] is False
        assert restored["milestone_summaries"] == {}
        assert restored["sliding_window_size"] == 3
        assert restored["milestone_interval"] == 4

    def test_round_trip_empty_summaries_list_per_role(self):
        """When milestones enabled but no summaries generated yet."""
        summaries = {"Buyer": [], "Seller": []}
        state = _full_state(
            milestone_summaries_enabled=True,
            milestone_summaries=summaries,
        )
        restored = from_pydantic(to_pydantic(state))

        assert restored["milestone_summaries"] == summaries


class TestMilestoneFieldsDefaults:
    """Validates: Requirements 9.3, 9.4 — backward compatibility when fields absent."""

    def test_to_pydantic_defaults_when_milestone_fields_absent(self):
        """Simulate a legacy state dict without milestone fields — .get() defaults kick in."""
        legacy_state: dict = {
            "session_id": "sess-legacy",
            "scenario_id": "scen-legacy",
            "turn_count": 0,
            "max_turns": 10,
            "current_speaker": "Buyer",
            "deal_status": "Negotiating",
            "current_offer": 0.0,
            "history": [],
            "hidden_context": {},
            "warning_count": 0,
            "agreement_threshold": 5000.0,
            "scenario_config": {},
            "turn_order": ["Buyer"],
            "turn_order_index": 0,
            "agent_states": {},
            "active_toggles": [],
            "total_tokens_used": 0,
            "stall_diagnosis": None,
        }
        # Pass as plain dict — milestone keys are missing
        model = to_pydantic(legacy_state)  # type: ignore[arg-type]

        assert model.milestone_summaries_enabled is False
        assert model.milestone_summaries == {}
        assert model.sliding_window_size == 3
        assert model.milestone_interval == 4

    def test_from_pydantic_defaults_when_model_uses_defaults(self):
        """NegotiationStateModel with no milestone fields set uses Pydantic defaults."""
        model = NegotiationStateModel(
            session_id="s",
            scenario_id="sc",
            turn_order=["A"],
            turn_order_index=0,
            agent_states={},
        )
        state = from_pydantic(model)

        assert state["milestone_summaries_enabled"] is False
        assert state["milestone_summaries"] == {}
        assert state["sliding_window_size"] == 3
        assert state["milestone_interval"] == 4
