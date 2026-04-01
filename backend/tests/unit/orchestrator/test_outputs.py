"""Unit tests for orchestrator output models: construction, validation, JSON serialization."""

import pytest
from pydantic import ValidationError

from app.orchestrator.outputs import NegotiatorOutput, ObserverOutput, RegulatorOutput


class TestNegotiatorOutput:
    def test_construction(self):
        out = NegotiatorOutput(
            inner_thought="I should lowball",
            public_message="I offer 500k",
            proposed_price=500_000.0,
        )
        assert out.inner_thought == "I should lowball"
        assert out.public_message == "I offer 500k"
        assert out.proposed_price == 500_000.0
        assert out.extra_fields == {}

    def test_extra_fields(self):
        out = NegotiatorOutput(
            inner_thought="hmm",
            public_message="deal",
            proposed_price=1.0,
            extra_fields={"urgency": "high", "counter": 3},
        )
        assert out.extra_fields == {"urgency": "high", "counter": 3}

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            NegotiatorOutput(inner_thought="x", public_message="y")  # type: ignore[call-arg]

    def test_json_round_trip(self):
        original = NegotiatorOutput(
            inner_thought="think", public_message="say", proposed_price=42.5
        )
        restored = NegotiatorOutput.model_validate_json(original.model_dump_json())
        assert restored == original


class TestRegulatorOutput:
    def test_construction_clear(self):
        out = RegulatorOutput(status="CLEAR", reasoning="All good")
        assert out.status == "CLEAR"
        assert out.reasoning == "All good"

    def test_construction_warning(self):
        out = RegulatorOutput(status="WARNING", reasoning="Price too high")
        assert out.status == "WARNING"

    def test_construction_blocked(self):
        out = RegulatorOutput(status="BLOCKED", reasoning="Violation")
        assert out.status == "BLOCKED"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            RegulatorOutput(status="INVALID", reasoning="nope")  # type: ignore[arg-type]

    def test_missing_reasoning_raises(self):
        with pytest.raises(ValidationError):
            RegulatorOutput(status="CLEAR")  # type: ignore[call-arg]

    def test_json_round_trip(self):
        original = RegulatorOutput(status="WARNING", reasoning="borderline")
        restored = RegulatorOutput.model_validate_json(original.model_dump_json())
        assert restored == original


class TestObserverOutput:
    def test_construction(self):
        out = ObserverOutput(observation="Buyer is aggressive")
        assert out.observation == "Buyer is aggressive"
        assert out.recommendation == ""

    def test_with_recommendation(self):
        out = ObserverOutput(
            observation="Stalemate detected",
            recommendation="Consider splitting the difference",
        )
        assert out.recommendation == "Consider splitting the difference"

    def test_missing_observation_raises(self):
        with pytest.raises(ValidationError):
            ObserverOutput()  # type: ignore[call-arg]

    def test_json_round_trip(self):
        original = ObserverOutput(observation="noted", recommendation="proceed")
        restored = ObserverOutput.model_validate_json(original.model_dump_json())
        assert restored == original
