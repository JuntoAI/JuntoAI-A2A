"""Unit tests for _snapshot_to_events() from app.routers.negotiation.

Validates that LangGraph state snapshots are correctly converted into
the expected sequence of SSE event model instances.
"""

import json

import pytest

from app.models.events import (
    AgentMessageEvent,
    AgentThoughtEvent,
    NegotiationCompleteEvent,
)
from app.routers.negotiation import _snapshot_to_events
from app.utils.sse import format_sse_event

SESSION_ID = "test-session-001"


def _assert_valid_sse_format(event) -> None:
    """Assert that an event serialises to valid ``data: <JSON>\\n\\n`` SSE."""
    sse_str = format_sse_event(event)
    assert sse_str.startswith("data: "), f"SSE must start with 'data: ', got: {sse_str!r}"
    assert sse_str.endswith("\n\n"), f"SSE must end with '\\n\\n', got: {sse_str!r}"
    json_part = sse_str[len("data: "):-2]
    parsed = json.loads(json_part)
    assert "event_type" in parsed


# ---------------------------------------------------------------------------
# Negotiator snapshots
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNegotiatorSnapshot:
    """Negotiator snapshot → agent_thought then agent_message (order matters)."""

    def _make_negotiator_snapshot(self, **overrides):
        entry = {
            "role": "Buyer",
            "agent_type": "negotiator",
            "turn_number": 1,
            "content": {
                "inner_thought": "I should start low.",
                "public_message": "I propose $500,000.",
                "proposed_price": 500_000.0,
            },
        }
        state = {
            "history": [entry],
            "turn_count": 1,
            "deal_status": "Negotiating",
            **overrides,
        }
        return {"negotiator_node": state}

    def test_yields_thought_then_message(self):
        snapshot = self._make_negotiator_snapshot()
        events = _snapshot_to_events(snapshot, SESSION_ID)

        assert len(events) == 2
        assert isinstance(events[0], AgentThoughtEvent)
        assert isinstance(events[1], AgentMessageEvent)

    def test_thought_event_content(self):
        snapshot = self._make_negotiator_snapshot()
        events = _snapshot_to_events(snapshot, SESSION_ID)
        thought = events[0]

        assert thought.event_type == "agent_thought"
        assert thought.agent_name == "Buyer"
        assert thought.inner_thought == "I should start low."
        assert thought.turn_number == 1

    def test_message_event_content(self):
        snapshot = self._make_negotiator_snapshot()
        events = _snapshot_to_events(snapshot, SESSION_ID)
        msg = events[1]

        assert msg.event_type == "agent_message"
        assert msg.agent_name == "Buyer"
        assert msg.public_message == "I propose $500,000."
        assert msg.proposed_price == 500_000.0
        assert msg.turn_number == 1

    def test_thought_before_message_ordering(self):
        """Inner thoughts MUST stream before public messages (product rule)."""
        snapshot = self._make_negotiator_snapshot()
        events = _snapshot_to_events(snapshot, SESSION_ID)
        types = [type(e).__name__ for e in events]
        assert types.index("AgentThoughtEvent") < types.index("AgentMessageEvent")

    def test_all_events_valid_sse_format(self):
        snapshot = self._make_negotiator_snapshot()
        events = _snapshot_to_events(snapshot, SESSION_ID)
        for event in events:
            _assert_valid_sse_format(event)


# ---------------------------------------------------------------------------
# Regulator snapshots
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRegulatorSnapshot:
    """Regulator snapshots with CLEAR / WARNING / BLOCKED status."""

    def _make_regulator_snapshot(self, status: str, **state_overrides):
        entry = {
            "role": "Regulator",
            "agent_type": "regulator",
            "turn_number": 1,
            "content": {
                "reasoning": f"Status is {status}.",
                "public_message": f"Compliance check: {status}.",
                "status": status,
            },
        }
        state = {
            "history": [entry],
            "turn_count": 1,
            "deal_status": "Negotiating",
            **state_overrides,
        }
        return {"regulator_node": state}

    def test_clear_status(self):
        snapshot = self._make_regulator_snapshot("CLEAR")
        events = _snapshot_to_events(snapshot, SESSION_ID)

        msgs = [e for e in events if isinstance(e, AgentMessageEvent)]
        assert len(msgs) == 1
        assert msgs[0].status == "CLEAR"
        assert msgs[0].agent_name == "Regulator"

    def test_warning_status(self):
        snapshot = self._make_regulator_snapshot("WARNING")
        events = _snapshot_to_events(snapshot, SESSION_ID)

        msgs = [e for e in events if isinstance(e, AgentMessageEvent)]
        assert len(msgs) == 1
        assert msgs[0].status == "WARNING"

    def test_blocked_status_with_terminal(self):
        """BLOCKED regulator with deal_status Blocked → message + complete."""
        snapshot = self._make_regulator_snapshot(
            "BLOCKED",
            deal_status="Blocked",
            current_offer=600_000.0,
            warning_count=3,
        )
        events = _snapshot_to_events(snapshot, SESSION_ID)

        msgs = [e for e in events if isinstance(e, AgentMessageEvent)]
        assert len(msgs) == 1
        assert msgs[0].status == "BLOCKED"

        completes = [e for e in events if isinstance(e, NegotiationCompleteEvent)]
        assert len(completes) == 1
        assert completes[0].deal_status == "Blocked"

    def test_regulator_events_valid_sse_format(self):
        for status in ("CLEAR", "WARNING", "BLOCKED"):
            snapshot = self._make_regulator_snapshot(status)
            events = _snapshot_to_events(snapshot, SESSION_ID)
            for event in events:
                _assert_valid_sse_format(event)


# ---------------------------------------------------------------------------
# Observer snapshots
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestObserverSnapshot:
    """Observer snapshot → thought (observation) + message events."""

    def _make_observer_snapshot(self):
        entry = {
            "role": "Analyst",
            "agent_type": "observer",
            "turn_number": 2,
            "content": {
                "observation": "Gap between parties is narrowing.",
                "public_message": "Consider splitting the difference.",
            },
        }
        state = {
            "history": [entry],
            "turn_count": 2,
            "deal_status": "Negotiating",
        }
        return {"observer_node": state}

    def test_observer_yields_events(self):
        snapshot = self._make_observer_snapshot()
        events = _snapshot_to_events(snapshot, SESSION_ID)

        thoughts = [e for e in events if isinstance(e, AgentThoughtEvent)]
        msgs = [e for e in events if isinstance(e, AgentMessageEvent)]
        assert len(thoughts) == 1
        assert thoughts[0].inner_thought == "Gap between parties is narrowing."
        assert thoughts[0].agent_name == "Analyst"
        assert len(msgs) == 1
        assert msgs[0].public_message == "Consider splitting the difference."

    def test_observer_events_valid_sse_format(self):
        snapshot = self._make_observer_snapshot()
        events = _snapshot_to_events(snapshot, SESSION_ID)
        for event in events:
            _assert_valid_sse_format(event)


# ---------------------------------------------------------------------------
# Dispatcher snapshots (terminal deal_status, no history)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDispatcherSnapshot:
    """Dispatcher sets terminal deal_status with empty history."""

    def _make_dispatcher_snapshot(self, deal_status: str, **extras):
        state = {
            "history": [],
            "deal_status": deal_status,
            "current_offer": extras.get("current_offer", 700_000.0),
            "turn_count": extras.get("turn_count", 5),
            "warning_count": extras.get("warning_count", 0),
            "total_tokens_used": extras.get("total_tokens_used", 0),
            "max_turns": extras.get("max_turns", 10),
        }
        state.update(extras)
        return {"dispatcher_node": state}

    def test_agreed_yields_negotiation_complete(self):
        snapshot = self._make_dispatcher_snapshot("Agreed", current_offer=650_000.0)
        events = _snapshot_to_events(snapshot, SESSION_ID)

        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, NegotiationCompleteEvent)
        assert evt.deal_status == "Agreed"
        assert evt.session_id == SESSION_ID
        assert "outcome" in evt.final_summary

    def test_failed_yields_negotiation_complete(self):
        snapshot = self._make_dispatcher_snapshot("Failed", max_turns=10)
        events = _snapshot_to_events(snapshot, SESSION_ID)

        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, NegotiationCompleteEvent)
        assert evt.deal_status == "Failed"
        assert "reason" in evt.final_summary

    def test_blocked_yields_negotiation_complete(self):
        snapshot = self._make_dispatcher_snapshot("Blocked", warning_count=3)
        events = _snapshot_to_events(snapshot, SESSION_ID)

        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, NegotiationCompleteEvent)
        assert evt.deal_status == "Blocked"

    def test_dispatcher_events_valid_sse_format(self):
        for status in ("Agreed", "Failed", "Blocked"):
            snapshot = self._make_dispatcher_snapshot(status)
            events = _snapshot_to_events(snapshot, SESSION_ID)
            for event in events:
                _assert_valid_sse_format(event)

    def test_negotiating_status_yields_nothing(self):
        """Dispatcher with non-terminal status and empty history → no events."""
        snapshot = self._make_dispatcher_snapshot("Negotiating")
        # Override deal_status back to Negotiating (non-terminal)
        snapshot["dispatcher_node"]["deal_status"] = "Negotiating"
        events = _snapshot_to_events(snapshot, SESSION_ID)
        assert events == []
