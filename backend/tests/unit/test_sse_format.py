"""Tests for SSE event formatting utility.

Verifies format_sse_event output for each event type:
- starts with 'data: '
- ends with '\n\n'
- contains parseable JSON with 'event_type' field
"""

import json

from app.models.events import (
    AgentMessageEvent,
    AgentThoughtEvent,
    NegotiationCompleteEvent,
    StreamErrorEvent,
)
from app.utils.sse import format_sse_event


def _assert_sse_format(result: str, expected_event_type: str) -> None:
    assert result.startswith("data: ")
    assert result.endswith("\n\n")

    json_str = result[len("data: "):-2]
    payload = json.loads(json_str)
    assert payload["event_type"] == expected_event_type


def test_format_agent_thought_event():
    event = AgentThoughtEvent(
        event_type="agent_thought",
        agent_name="Buyer",
        inner_thought="Analyzing the offer...",
        turn_number=1,
    )
    _assert_sse_format(format_sse_event(event), "agent_thought")


def test_format_agent_message_event():
    event = AgentMessageEvent(
        event_type="agent_message",
        agent_name="Seller",
        public_message="I propose €40M.",
        turn_number=2,
        proposed_price=40_000_000.0,
    )
    _assert_sse_format(format_sse_event(event), "agent_message")


def test_format_negotiation_complete_event():
    event = NegotiationCompleteEvent(
        event_type="negotiation_complete",
        session_id="sess-123",
        deal_status="Agreed",
        final_summary={"final_price": 35_000_000.0},
    )
    _assert_sse_format(format_sse_event(event), "negotiation_complete")


def test_format_stream_error_event():
    event = StreamErrorEvent(
        event_type="error",
        message="Something went wrong",
    )
    _assert_sse_format(format_sse_event(event), "error")
