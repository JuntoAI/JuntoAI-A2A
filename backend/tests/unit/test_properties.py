"""Property-based tests using hypothesis for the JuntoAI A2A backend.

Properties 1, 2, 3, 5 from the design document.
"""

import asyncio
import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.middleware.sse_limiter import SSEConnectionTracker
from app.models.events import (
    AgentMessageEvent,
    AgentThoughtEvent,
    NegotiationCompleteEvent,
    StreamErrorEvent,
)
from app.models.negotiation import NegotiationStateModel
from app.utils.sse import format_sse_event

# --- Strategies ---

VALID_DEAL_STATUSES = ["Negotiating", "Agreed", "Blocked", "Failed"]

st_text = st.text(min_size=1, max_size=50)
st_int_ge0 = st.integers(min_value=0, max_value=1000)
st_int_gt0 = st.integers(min_value=1, max_value=1000)
st_float_ge0 = st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False)
st_float_gt0 = st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False)
st_deal_status = st.sampled_from(VALID_DEAL_STATUSES)
st_active_toggles = st.lists(st.text(min_size=1, max_size=20), max_size=5)

st_negotiation_state = st.builds(
    NegotiationStateModel,
    session_id=st_text,
    scenario_id=st_text,
    turn_count=st_int_ge0,
    max_turns=st_int_gt0,
    current_speaker=st_text,
    deal_status=st_deal_status,
    current_offer=st_float_ge0,
    history=st.just([]),
    warning_count=st_int_ge0,
    hidden_context=st.just({}),
    agreement_threshold=st_float_gt0,
    active_toggles=st_active_toggles,
)

st_agent_thought = st.builds(
    AgentThoughtEvent,
    event_type=st.just("agent_thought"),
    agent_name=st_text,
    inner_thought=st_text,
    turn_number=st_int_ge0,
)

st_agent_message = st.builds(
    AgentMessageEvent,
    event_type=st.just("agent_message"),
    agent_name=st_text,
    public_message=st_text,
    turn_number=st_int_ge0,
    proposed_price=st.one_of(st.none(), st_float_ge0),
    retention_clause_demanded=st.one_of(st.none(), st.booleans()),
    status=st.one_of(st.none(), st_text),
)

st_negotiation_complete = st.builds(
    NegotiationCompleteEvent,
    event_type=st.just("negotiation_complete"),
    session_id=st_text,
    deal_status=st_text,
    final_summary=st.just({}),
)

st_stream_error = st.builds(
    StreamErrorEvent,
    event_type=st.just("error"),
    message=st_text,
)

st_any_event = st.one_of(st_agent_thought, st_agent_message, st_negotiation_complete, st_stream_error)


# --- Property 1: SSE event format compliance ---
# Feature: 020_a2a-backend-core-sse, Property 1: SSE event format compliance
# **Validates: Requirements 5.4, 5.5, 5.6**


class TestProperty1SSEFormatCompliance:
    @settings(max_examples=100)
    @given(event=st_any_event)
    def test_sse_format_starts_with_data_prefix(self, event):
        result = format_sse_event(event)
        assert result.startswith("data: ")

    @settings(max_examples=100)
    @given(event=st_any_event)
    def test_sse_format_ends_with_double_newline(self, event):
        result = format_sse_event(event)
        assert result.endswith("\n\n")

    @settings(max_examples=100)
    @given(event=st_any_event)
    def test_sse_format_contains_valid_json(self, event):
        result = format_sse_event(event)
        json_str = result[len("data: "):-2]
        payload = json.loads(json_str)
        assert "event_type" in payload

    @settings(max_examples=100)
    @given(event=st_any_event)
    def test_sse_format_event_type_matches(self, event):
        result = format_sse_event(event)
        json_str = result[len("data: "):-2]
        payload = json.loads(json_str)
        assert payload["event_type"] == event.event_type


# --- Property 2: Pydantic model round-trip serialization ---
# Feature: 020_a2a-backend-core-sse, Property 2: Pydantic model round-trip serialization
# **Validates: Requirements 3.13, 6.5**


class TestProperty2RoundTrip:
    @settings(max_examples=100)
    @given(state=st_negotiation_state)
    def test_negotiation_state_round_trip(self, state):
        restored = NegotiationStateModel.model_validate_json(state.model_dump_json())
        assert restored == state

    @settings(max_examples=100)
    @given(event=st_agent_thought)
    def test_agent_thought_round_trip(self, event):
        restored = AgentThoughtEvent.model_validate_json(event.model_dump_json())
        assert restored == event

    @settings(max_examples=100)
    @given(event=st_agent_message)
    def test_agent_message_round_trip(self, event):
        restored = AgentMessageEvent.model_validate_json(event.model_dump_json())
        assert restored == event

    @settings(max_examples=100)
    @given(event=st_negotiation_complete)
    def test_negotiation_complete_round_trip(self, event):
        restored = NegotiationCompleteEvent.model_validate_json(event.model_dump_json())
        assert restored == event

    @settings(max_examples=100)
    @given(event=st_stream_error)
    def test_stream_error_round_trip(self, event):
        restored = StreamErrorEvent.model_validate_json(event.model_dump_json())
        assert restored == event


# --- Property 3: SSE connection tracker invariant ---
# Feature: 020_a2a-backend-core-sse, Property 3: SSE connection tracker invariant
# **Validates: Requirements 7.1, 7.2, 7.5**

st_email = st.sampled_from(["a@test.com", "b@test.com", "c@test.com"])
st_operation = st.tuples(st.sampled_from(["acquire", "release"]), st_email)
st_operations = st.lists(st_operation, min_size=1, max_size=50)


class TestProperty3TrackerInvariant:
    @settings(max_examples=100)
    @given(ops=st_operations)
    def test_count_never_exceeds_max_or_goes_below_zero(self, ops):
        tracker = SSEConnectionTracker()
        loop = asyncio.new_event_loop()
        try:
            counts: dict[str, int] = {}
            for action, email in ops:
                if action == "acquire":
                    result = loop.run_until_complete(tracker.acquire(email))
                    if result:
                        counts[email] = counts.get(email, 0) + 1
                else:
                    loop.run_until_complete(tracker.release(email))
                    counts[email] = max(0, counts.get(email, 0) - 1)

                # Invariant: count is always in [0, MAX]
                for e in counts:
                    assert 0 <= counts[e] <= SSEConnectionTracker.MAX_CONNECTIONS_PER_EMAIL
        finally:
            loop.close()


# --- Property 5: deal_status constraint enforcement ---
# Feature: 020_a2a-backend-core-sse, Property 5: deal_status constraint enforcement
# **Validates: Requirement 3.6**


class TestProperty5DealStatusConstraint:
    @settings(max_examples=100)
    @given(status=st.text(min_size=1, max_size=50).filter(lambda s: s not in VALID_DEAL_STATUSES))
    def test_invalid_deal_status_raises_validation_error(self, status):
        with pytest.raises(ValidationError):
            NegotiationStateModel(
                session_id="s1", scenario_id="sc1", deal_status=status
            )
