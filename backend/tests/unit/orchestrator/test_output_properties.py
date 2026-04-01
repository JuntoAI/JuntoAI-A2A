"""Property-based tests for orchestrator output models.

P1: Output Model Round-Trip
P13: Output Parsing by Type
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.orchestrator.exceptions import AgentOutputParseError
from app.orchestrator.outputs import NegotiatorOutput, ObserverOutput, RegulatorOutput

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_text = st.text(min_size=1, max_size=100)
st_price = st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False)
st_status = st.sampled_from(["CLEAR", "WARNING", "BLOCKED"])

st_extra_fields = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=st.one_of(st.integers(), st.text(max_size=30), st.booleans(), st.floats(allow_nan=False, allow_infinity=False)),
    max_size=5,
)

st_negotiator_output = st.builds(
    NegotiatorOutput,
    inner_thought=st_text,
    public_message=st_text,
    proposed_price=st_price,
    extra_fields=st_extra_fields,
)

st_regulator_output = st.builds(
    RegulatorOutput,
    status=st_status,
    reasoning=st_text,
)

st_observer_output = st.builds(
    ObserverOutput,
    observation=st_text,
    recommendation=st_text,
)


# ---------------------------------------------------------------------------
# Standalone _parse_output helper (mirrors agent_node.py logic for Task 1.6)
# ---------------------------------------------------------------------------

_OUTPUT_MODEL_MAP = {
    "negotiator": NegotiatorOutput,
    "regulator": RegulatorOutput,
    "observer": ObserverOutput,
}


def _parse_output(response_text: str, agent_type: str, agent_name: str = "test-agent") -> NegotiatorOutput | RegulatorOutput | ObserverOutput:
    """Parse LLM response JSON into the correct output model by agent type.

    Raises AgentOutputParseError on invalid JSON or schema mismatch.
    """
    model_cls = _OUTPUT_MODEL_MAP.get(agent_type)
    if model_cls is None:
        raise AgentOutputParseError(agent_name, response_text)
    try:
        return model_cls.model_validate_json(response_text)
    except (ValidationError, json.JSONDecodeError) as exc:
        raise AgentOutputParseError(agent_name, response_text) from exc


# ---------------------------------------------------------------------------
# P1: Output Model Round-Trip
# **Validates: Requirements 7.7, 7.8**
# ---------------------------------------------------------------------------


class TestP1OutputModelRoundTrip:
    """FOR ALL valid output instances, model_validate_json(model_dump_json()) == original."""

    @settings(max_examples=100)
    @given(instance=st_negotiator_output)
    def test_negotiator_round_trip(self, instance: NegotiatorOutput):
        restored = NegotiatorOutput.model_validate_json(instance.model_dump_json())
        assert restored == instance

    @settings(max_examples=100)
    @given(instance=st_regulator_output)
    def test_regulator_round_trip(self, instance: RegulatorOutput):
        restored = RegulatorOutput.model_validate_json(instance.model_dump_json())
        assert restored == instance

    @settings(max_examples=100)
    @given(instance=st_observer_output)
    def test_observer_round_trip(self, instance: ObserverOutput):
        restored = ObserverOutput.model_validate_json(instance.model_dump_json())
        assert restored == instance


# ---------------------------------------------------------------------------
# P13: Output Parsing by Type
# **Validates: Requirements 7.4, 7.6**
# ---------------------------------------------------------------------------


class TestP13OutputParsingByType:
    """_parse_output dispatches to the correct model by agent_type and rejects mismatches."""

    @settings(max_examples=100)
    @given(instance=st_negotiator_output)
    def test_negotiator_parses_correctly(self, instance: NegotiatorOutput):
        json_str = instance.model_dump_json()
        result = _parse_output(json_str, "negotiator")
        assert isinstance(result, NegotiatorOutput)
        assert result == instance

    @settings(max_examples=100)
    @given(instance=st_regulator_output)
    def test_regulator_parses_correctly(self, instance: RegulatorOutput):
        json_str = instance.model_dump_json()
        result = _parse_output(json_str, "regulator")
        assert isinstance(result, RegulatorOutput)
        assert result == instance

    @settings(max_examples=100)
    @given(instance=st_observer_output)
    def test_observer_parses_correctly(self, instance: ObserverOutput):
        json_str = instance.model_dump_json()
        result = _parse_output(json_str, "observer")
        assert isinstance(result, ObserverOutput)
        assert result == instance

    @settings(max_examples=100)
    @given(instance=st_negotiator_output)
    def test_negotiator_json_rejected_as_regulator(self, instance: NegotiatorOutput):
        json_str = instance.model_dump_json()
        with pytest.raises(AgentOutputParseError):
            _parse_output(json_str, "regulator")

    @settings(max_examples=100)
    @given(instance=st_negotiator_output)
    def test_negotiator_json_rejected_as_observer(self, instance: NegotiatorOutput):
        json_str = instance.model_dump_json()
        with pytest.raises(AgentOutputParseError):
            _parse_output(json_str, "observer")

    @settings(max_examples=100)
    @given(instance=st_regulator_output)
    def test_regulator_json_rejected_as_negotiator(self, instance: RegulatorOutput):
        json_str = instance.model_dump_json()
        with pytest.raises(AgentOutputParseError):
            _parse_output(json_str, "negotiator")

    def test_unknown_agent_type_raises(self):
        with pytest.raises(AgentOutputParseError):
            _parse_output('{"foo": "bar"}', "unknown_type")

    def test_invalid_json_raises(self):
        with pytest.raises(AgentOutputParseError):
            _parse_output("not json at all", "negotiator")
