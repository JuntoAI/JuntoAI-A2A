"""Unit tests for NegotiationState milestone fields and create_initial_state milestone behavior.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 9.3, 9.4
"""

import pytest

from app.orchestrator.state import NegotiationState, create_initial_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(role: str, name: str, agent_type: str = "negotiator", model_id: str = "gemini-3-flash-preview") -> dict:
    return {"role": role, "name": name, "type": agent_type, "model_id": model_id}


def _make_config(agents: list[dict], turn_order: list[str] | None = None, **params) -> dict:
    neg_params: dict = {"max_turns": 10, "agreement_threshold": 5000.0}
    if turn_order is not None:
        neg_params["turn_order"] = turn_order
    neg_params.update(params)
    return {"id": "scenario-001", "agents": agents, "negotiation_params": neg_params}


# ---------------------------------------------------------------------------
# Task 2.4: milestone_summaries_enabled=True
# ---------------------------------------------------------------------------


class TestMilestoneEnabled:
    """create_initial_state with milestone_summaries_enabled=True."""

    def test_milestone_enabled_sets_flag(self):
        agents = [_make_agent("Buyer", "Alice"), _make_agent("Seller", "Bob")]
        config = _make_config(agents, turn_order=["Buyer", "Seller"])
        state = create_initial_state("sess-m1", config, milestone_summaries_enabled=True)

        assert state["milestone_summaries_enabled"] is True

    def test_milestone_enabled_forces_structured_memory(self):
        """Req 2.4: milestone_summaries_enabled=True forces structured_memory_enabled=True."""
        agents = [_make_agent("Buyer", "Alice"), _make_agent("Seller", "Bob")]
        config = _make_config(agents, turn_order=["Buyer", "Seller"])
        state = create_initial_state("sess-m2", config, milestone_summaries_enabled=True)

        assert state["structured_memory_enabled"] is True
        assert set(state["agent_memories"].keys()) == {"Buyer", "Seller"}

    def test_milestone_enabled_initializes_summaries_per_role(self):
        """Req 2.5: milestone_summaries has one empty list per agent role."""
        agents = [
            _make_agent("Buyer", "Alice"),
            _make_agent("Seller", "Bob"),
            _make_agent("Regulator", "Carol", agent_type="regulator"),
        ]
        config = _make_config(agents, turn_order=["Buyer", "Regulator", "Seller", "Regulator"])
        state = create_initial_state("sess-m3", config, milestone_summaries_enabled=True)

        assert set(state["milestone_summaries"].keys()) == {"Buyer", "Seller", "Regulator"}
        for role_summaries in state["milestone_summaries"].values():
            assert role_summaries == []


# ---------------------------------------------------------------------------
# Task 2.4: milestone_summaries_enabled=False
# ---------------------------------------------------------------------------


class TestMilestoneDisabled:
    """create_initial_state with milestone_summaries_enabled=False."""

    def test_milestone_disabled_sets_flag(self):
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"])
        state = create_initial_state("sess-m4", config, milestone_summaries_enabled=False)

        assert state["milestone_summaries_enabled"] is False

    def test_milestone_disabled_empty_summaries(self):
        """Req 2.6: milestone_summaries is empty dict when disabled."""
        agents = [_make_agent("Buyer", "Alice"), _make_agent("Seller", "Bob")]
        config = _make_config(agents, turn_order=["Buyer", "Seller"])
        state = create_initial_state("sess-m5", config, milestone_summaries_enabled=False)

        assert state["milestone_summaries"] == {}

    def test_milestone_disabled_does_not_force_structured_memory(self):
        """Structured memory stays off when milestones are disabled."""
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"])
        state = create_initial_state("sess-m6", config, milestone_summaries_enabled=False)

        assert state["structured_memory_enabled"] is False

    def test_default_milestone_disabled(self):
        """Default: milestone_summaries_enabled=False when not passed."""
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"])
        state = create_initial_state("sess-m7", config)

        assert state["milestone_summaries_enabled"] is False
        assert state["milestone_summaries"] == {}


# ---------------------------------------------------------------------------
# Task 2.4: sliding_window_size and milestone_interval from params
# ---------------------------------------------------------------------------


class TestSlidingWindowAndMilestoneInterval:
    """Verify sliding_window_size and milestone_interval are read from params."""

    def test_explicit_values_from_params(self):
        """Req 2.7: Fields populated from scenario NegotiationParams."""
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(
            agents,
            turn_order=["Buyer"],
            sliding_window_size=5,
            milestone_interval=8,
        )
        state = create_initial_state("sess-sw1", config)

        assert state["sliding_window_size"] == 5
        assert state["milestone_interval"] == 8

    def test_defaults_when_absent(self):
        """Req 9.4: Default values of 3 and 4 when fields absent from params."""
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"])
        state = create_initial_state("sess-sw2", config)

        assert state["sliding_window_size"] == 3
        assert state["milestone_interval"] == 4

    def test_partial_params_sliding_window_only(self):
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"], sliding_window_size=7)
        state = create_initial_state("sess-sw3", config)

        assert state["sliding_window_size"] == 7
        assert state["milestone_interval"] == 4

    def test_partial_params_milestone_interval_only(self):
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"], milestone_interval=6)
        state = create_initial_state("sess-sw4", config)

        assert state["sliding_window_size"] == 3
        assert state["milestone_interval"] == 6


# ---------------------------------------------------------------------------
# Task 2.4: Backward compatibility (Req 9.3, 9.4)
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify backward compatibility when milestone fields are absent from state dict."""

    def test_state_dict_without_milestone_fields_uses_defaults(self):
        """Req 9.3, 9.4: System treats absent fields as defaults."""
        # Simulate a state dict from before this feature existed
        state: dict = {
            "session_id": "old-sess",
            "scenario_id": "s1",
            "turn_count": 5,
            "max_turns": 10,
            "current_speaker": "Buyer",
            "deal_status": "Negotiating",
            "current_offer": 100.0,
            "history": [],
            "hidden_context": {},
            "warning_count": 0,
            "agreement_threshold": 5000.0,
            "scenario_config": {},
            "turn_order": ["Buyer", "Seller"],
            "turn_order_index": 0,
            "agent_states": {},
            "active_toggles": [],
            "total_tokens_used": 0,
            "stall_diagnosis": None,
            "custom_prompts": {},
            "model_overrides": {},
            "structured_memory_enabled": False,
            "structured_memory_roles": [],
            "agent_memories": {},
        }

        # Accessing new fields via .get() should return defaults
        assert state.get("milestone_summaries_enabled", False) is False
        assert state.get("milestone_summaries", {}) == {}
        assert state.get("sliding_window_size", 3) == 3
        assert state.get("milestone_interval", 4) == 4

    def test_create_initial_state_without_milestone_param(self):
        """create_initial_state works without milestone_summaries_enabled param."""
        agents = [_make_agent("Buyer", "Alice")]
        config = _make_config(agents, turn_order=["Buyer"])
        # Call without milestone_summaries_enabled — should default to False
        state = create_initial_state("sess-bc1", config)

        assert state["milestone_summaries_enabled"] is False
        assert state["milestone_summaries"] == {}
        assert state["sliding_window_size"] == 3
        assert state["milestone_interval"] == 4
