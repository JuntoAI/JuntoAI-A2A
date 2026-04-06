"""Unit tests for the confirmation node.

Covers task 3.10:
- Parse retry + fallback (invalid JSON → retry → fallback rejection)
- Confirmation history entry shape and agent_type = "confirmation"
- _snapshot_to_events emits AgentMessageEvent for confirmation final_statement entries
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.orchestrator.confirmation_node import (
    confirmation_node,
    _build_confirmation_messages,
    _parse_confirmation,
    _fallback_rejection,
)
from app.orchestrator.exceptions import AgentOutputParseError
from app.orchestrator.state import NegotiationState
from app.models.events import AgentMessageEvent
from app.routers.negotiation import _snapshot_to_events


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(
    role: str = "Buyer",
    name: str = "Alice",
    agent_type: str = "negotiator",
    model_id: str = "gemini-3-flash-preview",
) -> dict[str, Any]:
    return {
        "role": role,
        "name": name,
        "type": agent_type,
        "model_id": model_id,
        "persona_prompt": f"You are {name}.",
        "goals": [f"Goal for {name}"],
    }


def _make_state(
    agents: list[dict[str, Any]] | None = None,
    confirmation_pending: list[str] | None = None,
    turn_count: int = 5,
    current_offer: float = 100000.0,
    history: list[dict[str, Any]] | None = None,
) -> NegotiationState:
    if agents is None:
        agents = [
            _make_agent_config("Buyer", "Alice"),
            _make_agent_config("Seller", "Bob"),
        ]
    if confirmation_pending is None:
        confirmation_pending = ["Buyer"]

    agent_states = {}
    for cfg in agents:
        agent_states[cfg["role"]] = {
            "role": cfg["role"],
            "name": cfg["name"],
            "agent_type": cfg.get("type", "negotiator"),
            "model_id": cfg["model_id"],
            "last_proposed_price": current_offer,
            "warning_count": 0,
        }

    turn_order = [cfg["role"] for cfg in agents]

    return NegotiationState(
        session_id="test-sess",
        scenario_id="test-scenario",
        turn_count=turn_count,
        max_turns=15,
        current_speaker=turn_order[0],
        deal_status="Confirming",
        current_offer=current_offer,
        history=history or [
            {
                "role": "Buyer",
                "agent_type": "negotiator",
                "turn_number": turn_count - 1,
                "content": {"public_message": "I propose 100k", "proposed_price": 100000.0, "inner_thought": "thinking"},
            },
        ],
        hidden_context={},
        warning_count=0,
        agreement_threshold=5000.0,
        scenario_config={
            "id": "test-scenario",
            "agents": agents,
            "negotiation_params": {"max_turns": 15},
        },
        turn_order=turn_order,
        turn_order_index=0,
        agent_states=agent_states,
        active_toggles=[],
        total_tokens_used=0,
        stall_diagnosis=None,
        custom_prompts={},
        model_overrides={},
        structured_memory_enabled=False,
        structured_memory_roles=[],
        agent_memories={},
        milestone_summaries_enabled=False,
        milestone_summaries={},
        sliding_window_size=3,
        milestone_interval=4,
        no_memory_roles=[],
        agent_calls=[],
        closure_status="",
        confirmation_pending=confirmation_pending,
    )



# ===========================================================================
# Test: Parse retry + fallback
# ===========================================================================


class TestParseRetryAndFallback:
    """Test that invalid JSON triggers retry, and double failure uses fallback."""

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_first_parse_fails_retry_succeeds(self, mock_router):
        """First LLM response is invalid JSON, retry returns valid JSON."""
        valid_json = json.dumps({
            "accept": True,
            "final_statement": "I accept the deal.",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content="not valid json"),
            AIMessage(content=valid_json),
        ]
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"])
        result = confirmation_node(state)

        assert mock_model.invoke.call_count == 2
        assert len(result["history"]) == 1
        entry = result["history"][0]
        assert entry["content"]["accept"] is True
        assert entry["content"]["final_statement"] == "I accept the deal."

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_double_parse_failure_uses_fallback_rejection(self, mock_router):
        """Both LLM calls return garbage → fallback rejection used."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content="still not json")
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"])
        result = confirmation_node(state)

        assert mock_model.invoke.call_count == 2
        assert len(result["history"]) == 1
        entry = result["history"][0]
        # Fallback is a rejection
        assert entry["content"]["accept"] is False
        assert "could not provide a clear response" in entry["content"]["final_statement"]
        assert entry["content"]["conditions"] == []

    def test_fallback_rejection_shape(self):
        """_fallback_rejection returns correct structure."""
        fallback = _fallback_rejection("TestRole")
        assert fallback.accept is False
        assert "TestRole" in fallback.final_statement
        assert fallback.conditions == []


# ===========================================================================
# Test: Confirmation history entry shape
# ===========================================================================


class TestConfirmationHistoryEntry:
    """Test that confirmation_node produces correctly shaped history entries."""

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_history_entry_has_correct_agent_type(self, mock_router):
        """History entry must have agent_type == 'confirmation'."""
        valid_json = json.dumps({
            "accept": True,
            "final_statement": "Deal accepted.",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"], turn_count=7)
        result = confirmation_node(state)

        entry = result["history"][0]
        assert entry["agent_type"] == "confirmation"
        assert entry["role"] == "Buyer"
        assert entry["turn_number"] == 7

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_history_entry_content_matches_parsed_output(self, mock_router):
        """History entry content must match the parsed ConfirmationOutput."""
        valid_json = json.dumps({
            "accept": False,
            "final_statement": "I reject this deal.",
            "conditions": ["Need better terms"],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Seller"])
        result = confirmation_node(state)

        entry = result["history"][0]
        assert entry["content"]["accept"] is False
        assert entry["content"]["final_statement"] == "I reject this deal."
        assert entry["content"]["conditions"] == ["Need better terms"]

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_confirmation_pending_decremented(self, mock_router):
        """After processing one role, confirmation_pending shrinks by one."""
        valid_json = json.dumps({
            "accept": True,
            "final_statement": "Accepted.",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer", "Seller"])
        result = confirmation_node(state)

        assert result["confirmation_pending"] == ["Seller"]

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_empty_pending_returns_empty(self, mock_router):
        """When confirmation_pending is empty, node returns empty dict."""
        state = _make_state(confirmation_pending=[])
        result = confirmation_node(state)
        assert result == {}


# ===========================================================================
# Test: _snapshot_to_events emits AgentMessageEvent for confirmation entries
# ===========================================================================


class TestSnapshotToEventsConfirmation:
    """Test that _snapshot_to_events handles confirmation history entries."""

    def test_confirmation_entry_emits_agent_message_event(self):
        """Confirmation history entry with final_statement produces AgentMessageEvent."""
        snapshot = {
            "confirmation": {
                "history": [
                    {
                        "role": "Buyer",
                        "agent_type": "confirmation",
                        "turn_number": 5,
                        "content": {
                            "accept": True,
                            "final_statement": "I accept these terms.",
                            "conditions": [],
                        },
                    }
                ],
                "deal_status": "Confirming",
                "turn_count": 5,
                "confirmation_pending": ["Seller"],
            }
        }

        events = _snapshot_to_events(snapshot, "test-session")

        # Should produce exactly one AgentMessageEvent
        msg_events = [e for e in events if isinstance(e, AgentMessageEvent)]
        assert len(msg_events) == 1
        assert msg_events[0].agent_name == "Buyer"
        assert msg_events[0].public_message == "I accept these terms."
        assert msg_events[0].turn_number == 5

    def test_confirmation_entry_does_not_emit_thought_event(self):
        """Confirmation entries should NOT produce AgentThoughtEvent."""
        from app.models.events import AgentThoughtEvent

        snapshot = {
            "confirmation": {
                "history": [
                    {
                        "role": "Seller",
                        "agent_type": "confirmation",
                        "turn_number": 3,
                        "content": {
                            "accept": False,
                            "final_statement": "I reject this deal.",
                            "conditions": [],
                        },
                    }
                ],
                "deal_status": "Confirming",
                "turn_count": 3,
            }
        }

        events = _snapshot_to_events(snapshot, "test-session")

        thought_events = [e for e in events if isinstance(e, AgentThoughtEvent)]
        assert len(thought_events) == 0

    def test_confirming_status_does_not_emit_complete_event(self):
        """deal_status='Confirming' should NOT produce NegotiationCompleteEvent."""
        from app.models.events import NegotiationCompleteEvent

        snapshot = {
            "confirmation": {
                "history": [
                    {
                        "role": "Buyer",
                        "agent_type": "confirmation",
                        "turn_number": 5,
                        "content": {
                            "accept": True,
                            "final_statement": "Accepted.",
                            "conditions": [],
                        },
                    }
                ],
                "deal_status": "Confirming",
                "turn_count": 5,
            }
        }

        events = _snapshot_to_events(snapshot, "test-session")

        complete_events = [e for e in events if isinstance(e, NegotiationCompleteEvent)]
        assert len(complete_events) == 0


# ===========================================================================
# Test: Confirmation with accept response
# ===========================================================================


class TestConfirmationAcceptResponse:
    """Test the full accept flow through confirmation_node."""

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_accept_preserves_deal_status_as_confirming(self, mock_router):
        """Accept response does NOT change deal_status — dispatcher handles that."""
        valid_json = json.dumps({
            "accept": True,
            "final_statement": "I accept the terms as proposed.",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"])
        result = confirmation_node(state)

        # confirmation_node never sets deal_status — only history + pending
        assert "deal_status" not in result

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_accept_with_conditions(self, mock_router):
        """Accept with conditions stores them in history entry."""
        valid_json = json.dumps({
            "accept": True,
            "final_statement": "I accept, but with conditions.",
            "conditions": ["Payment within 30 days", "Non-compete clause"],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Seller"])
        result = confirmation_node(state)

        entry = result["history"][0]
        assert entry["content"]["accept"] is True
        assert entry["content"]["conditions"] == ["Payment within 30 days", "Non-compete clause"]
        assert entry["role"] == "Seller"

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_accept_uses_model_override_when_set(self, mock_router):
        """When model_overrides has an entry for the role, it's used instead of agent config model."""
        valid_json = json.dumps({
            "accept": True,
            "final_statement": "Accepted.",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"])
        state["model_overrides"] = {"Buyer": "gpt-4o-override"}
        confirmation_node(state)

        mock_router.get_model.assert_called_once_with(
            "gpt-4o-override",
            fallback_model_id=None,
        )

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_accept_invokes_llm_exactly_once(self, mock_router):
        """Successful parse on first try means only one LLM call."""
        valid_json = json.dumps({
            "accept": True,
            "final_statement": "Deal!",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"])
        confirmation_node(state)

        assert mock_model.invoke.call_count == 1


# ===========================================================================
# Test: Confirmation with reject response
# ===========================================================================


class TestConfirmationRejectResponse:
    """Test the full reject flow through confirmation_node."""

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_reject_stores_false_accept(self, mock_router):
        """Reject response stores accept=False in history."""
        valid_json = json.dumps({
            "accept": False,
            "final_statement": "This deal does not meet my minimum requirements.",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"])
        result = confirmation_node(state)

        entry = result["history"][0]
        assert entry["content"]["accept"] is False
        assert "minimum requirements" in entry["content"]["final_statement"]

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_reject_with_conditions_as_reasons(self, mock_router):
        """Reject with conditions lists reasons for rejection."""
        valid_json = json.dumps({
            "accept": False,
            "final_statement": "I cannot accept this deal.",
            "conditions": ["Price too high", "Timeline unrealistic"],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Seller"])
        result = confirmation_node(state)

        entry = result["history"][0]
        assert entry["content"]["accept"] is False
        assert len(entry["content"]["conditions"]) == 2
        assert "Price too high" in entry["content"]["conditions"]

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_reject_still_decrements_pending(self, mock_router):
        """Rejection still removes the role from confirmation_pending."""
        valid_json = json.dumps({
            "accept": False,
            "final_statement": "No deal.",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=valid_json)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer", "Seller"])
        result = confirmation_node(state)

        assert result["confirmation_pending"] == ["Seller"]
        assert result["history"][0]["content"]["accept"] is False


# ===========================================================================
# Test: Confirmation with invalid JSON from LLM
# ===========================================================================


class TestConfirmationInvalidJSON:
    """Test edge cases for invalid/malformed LLM responses."""

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_markdown_wrapped_json_parsed_successfully(self, mock_router):
        """JSON wrapped in markdown code fences is parsed correctly."""
        inner_json = json.dumps({
            "accept": True,
            "final_statement": "Accepted.",
            "conditions": [],
        })
        markdown_wrapped = f"```json\n{inner_json}\n```"
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content=markdown_wrapped)
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"])
        result = confirmation_node(state)

        # Should parse successfully on first try (no retry needed)
        assert mock_model.invoke.call_count == 1
        assert result["history"][0]["content"]["accept"] is True

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_empty_response_triggers_fallback(self, mock_router):
        """Empty string from LLM triggers retry then fallback."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content="")
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"])
        result = confirmation_node(state)

        assert mock_model.invoke.call_count == 2
        entry = result["history"][0]
        assert entry["content"]["accept"] is False
        assert "could not provide a clear response" in entry["content"]["final_statement"]

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_partial_json_triggers_retry(self, mock_router):
        """Truncated JSON triggers retry."""
        valid_json = json.dumps({
            "accept": True,
            "final_statement": "OK deal.",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            AIMessage(content='{"accept": true, "final_sta'),  # truncated
            AIMessage(content=valid_json),
        ]
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Seller"])
        result = confirmation_node(state)

        assert mock_model.invoke.call_count == 2
        assert result["history"][0]["content"]["accept"] is True

    @patch("app.orchestrator.confirmation_node.model_router")
    def test_list_content_blocks_extracted(self, mock_router):
        """LLM returning list-of-blocks content is handled correctly."""
        valid_json = json.dumps({
            "accept": False,
            "final_statement": "Rejected.",
            "conditions": [],
        })
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(
            content=[{"type": "text", "text": valid_json}]
        )
        mock_router.get_model.return_value = mock_model

        state = _make_state(confirmation_pending=["Buyer"])
        result = confirmation_node(state)

        assert mock_model.invoke.call_count == 1
        assert result["history"][0]["content"]["accept"] is False

    def test_parse_confirmation_raises_on_missing_required_field(self):
        """_parse_confirmation raises AgentOutputParseError when required fields missing."""
        incomplete_json = json.dumps({"accept": True})  # missing final_statement
        with pytest.raises(AgentOutputParseError):
            _parse_confirmation(incomplete_json, "TestRole")

    def test_parse_confirmation_valid_json(self):
        """_parse_confirmation returns ConfirmationOutput for valid JSON."""
        valid_json = json.dumps({
            "accept": True,
            "final_statement": "Done.",
            "conditions": ["cond1"],
        })
        result = _parse_confirmation(valid_json, "TestRole")
        assert result.accept is True
        assert result.final_statement == "Done."
        assert result.conditions == ["cond1"]

    def test_parse_confirmation_raises_on_plain_text(self):
        """_parse_confirmation raises AgentOutputParseError for non-JSON text."""
        with pytest.raises(AgentOutputParseError):
            _parse_confirmation("I accept the deal, let's go!", "TestRole")
