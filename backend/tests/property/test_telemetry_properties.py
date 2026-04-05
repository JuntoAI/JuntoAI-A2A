"""Property-based tests for per-model telemetry.

Feature: per-model-telemetry
Uses Hypothesis to verify universal invariants across generated inputs.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.outputs import AgentCallRecord

# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs", "P")),
    min_size=1,
    max_size=50,
)

_agent_type = st.sampled_from(["negotiator", "regulator", "observer"])

_iso_timestamp = st.datetimes().map(lambda dt: dt.isoformat() + "Z")


@st.composite
def agent_call_record_strategy(draw):
    """Generate a random valid AgentCallRecord instance."""
    return AgentCallRecord(
        agent_role=draw(_safe_text),
        agent_type=draw(_agent_type),
        model_id=draw(_safe_text),
        latency_ms=draw(st.integers(min_value=0, max_value=10_000_000)),
        input_tokens=draw(st.integers(min_value=0, max_value=10_000_000)),
        output_tokens=draw(st.integers(min_value=0, max_value=10_000_000)),
        error=draw(st.booleans()),
        turn_number=draw(st.integers(min_value=0, max_value=10_000)),
        timestamp=draw(_iso_timestamp),
    )


# ---------------------------------------------------------------------------
# Feature: per-model-telemetry
# Property 1: AgentCallRecord round-trip serialization
# **Validates: Requirements 1.2**
#
# For any valid AgentCallRecord instance, serializing to JSON via
# .model_dump_json() and deserializing back via
# AgentCallRecord.model_validate_json() SHALL produce an equivalent object.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(record=agent_call_record_strategy())
def test_agent_call_record_round_trip(record: AgentCallRecord):
    """Serializing and deserializing any valid AgentCallRecord must produce an equal object.

    Feature: per-model-telemetry, Property 1: AgentCallRecord round-trip serialization
    """
    json_str = record.model_dump_json()
    restored = AgentCallRecord.model_validate_json(json_str)
    assert restored == record


# ---------------------------------------------------------------------------
# Feature: per-model-telemetry
# Property 2: Converter round-trip preserves agent_calls
# **Validates: Requirements 2.4**
#
# For any list of valid AgentCallRecord dicts placed in a NegotiationState,
# converting via to_pydantic() then from_pydantic() SHALL produce a state
# where agent_calls is equal to the original list.
# ---------------------------------------------------------------------------

from app.orchestrator.converters import from_pydantic, to_pydantic
from app.orchestrator.state import NegotiationState


def _minimal_negotiation_state(
    agent_calls: list[dict],
) -> NegotiationState:
    """Build a minimal valid NegotiationState with the given agent_calls."""
    return NegotiationState(
        session_id="test-session",
        scenario_id="test-scenario",
        turn_count=0,
        max_turns=15,
        current_speaker="Buyer",
        deal_status="Negotiating",
        current_offer=0.0,
        history=[],
        hidden_context={},
        warning_count=0,
        agreement_threshold=1000000.0,
        scenario_config={},
        turn_order=["Buyer"],
        turn_order_index=0,
        agent_states={},
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
        agent_calls=agent_calls,
    )


@settings(max_examples=100)
@given(records=st.lists(agent_call_record_strategy(), min_size=0, max_size=10))
def test_converter_round_trip_preserves_agent_calls(
    records: list[AgentCallRecord],
):
    """Round-tripping agent_calls through to_pydantic/from_pydantic must preserve them.

    Feature: per-model-telemetry, Property 2: Converter round-trip preserves agent_calls
    """
    record_dicts = [r.model_dump() for r in records]
    state = _minimal_negotiation_state(agent_calls=record_dicts)

    pydantic_model = to_pydantic(state)
    restored_state = from_pydantic(pydantic_model)

    assert restored_state["agent_calls"] == record_dicts


# ---------------------------------------------------------------------------
# Feature: per-model-telemetry
# Property 3: Token extraction correctness
# **Validates: Requirements 3.2**
#
# For any non-negative integer pair (input_tokens, output_tokens), when
# usage_metadata contains those values (as dict or object), _extract_tokens()
# SHALL return the same pair. When usage_metadata is None, it SHALL return
# (0, 0).
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock

from app.orchestrator.agent_node import _extract_tokens

_non_neg_tokens = st.integers(min_value=0, max_value=10_000_000)


def _make_response_with_dict_usage(
    input_tokens: int, output_tokens: int
) -> MagicMock:
    """Create a mock AIMessage with usage_metadata as a dict."""
    resp = MagicMock()
    resp.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return resp


def _make_response_with_object_usage(
    input_tokens: int, output_tokens: int
) -> MagicMock:
    """Create a mock AIMessage with usage_metadata as an object with attributes."""

    class _UsageMeta:
        def __init__(self, inp: int, out: int):
            self.input_tokens = inp
            self.output_tokens = out

    resp = MagicMock()
    resp.usage_metadata = _UsageMeta(input_tokens, output_tokens)
    return resp


def _make_response_with_none_usage() -> MagicMock:
    """Create a mock AIMessage with usage_metadata = None."""
    resp = MagicMock()
    resp.usage_metadata = None
    return resp


@settings(max_examples=100)
@given(
    input_tokens=_non_neg_tokens,
    output_tokens=_non_neg_tokens,
    usage_form=st.sampled_from(["dict", "object", "none"]),
)
def test_extract_tokens_correctness(
    input_tokens: int, output_tokens: int, usage_form: str
):
    """_extract_tokens returns the correct token pair for any usage_metadata form.

    Feature: per-model-telemetry, Property 3: Token extraction correctness
    """
    if usage_form == "dict":
        response = _make_response_with_dict_usage(input_tokens, output_tokens)
        expected = (input_tokens, output_tokens)
    elif usage_form == "object":
        response = _make_response_with_object_usage(input_tokens, output_tokens)
        expected = (input_tokens, output_tokens)
    else:  # none
        response = _make_response_with_none_usage()
        expected = (0, 0)

    result = _extract_tokens(response)
    assert result == expected, (
        f"usage_form={usage_form}, input={input_tokens}, output={output_tokens}: "
        f"got {result}, expected {expected}"
    )
