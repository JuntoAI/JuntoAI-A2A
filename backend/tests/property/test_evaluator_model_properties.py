"""Property-based tests for evaluator output model serialization.

Feature: negotiation-evaluator
Uses Hypothesis to verify round-trip serialization for new Pydantic models.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.outputs import (
    ConfirmationOutput,
    EvaluationInterview,
    EvaluationReport,
)

# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs", "P")),
    min_size=1,
    max_size=50,
)

_any_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs", "P")),
    min_size=0,
    max_size=50,
)

_satisfaction = st.integers(min_value=1, max_value=10)

_dimension_score = st.integers(min_value=1, max_value=10)


@st.composite
def confirmation_output_strategy(draw):
    """Generate a random valid ConfirmationOutput instance."""
    return ConfirmationOutput(
        accept=draw(st.booleans()),
        final_statement=draw(_safe_text),
        conditions=draw(st.lists(_safe_text, min_size=0, max_size=5)),
    )


@st.composite
def evaluation_interview_strategy(draw):
    """Generate a random valid EvaluationInterview instance."""
    return EvaluationInterview(
        feels_served=draw(st.booleans()),
        felt_respected=draw(st.booleans()),
        is_win_win=draw(st.booleans()),
        criticism=draw(_any_text),
        satisfaction_rating=draw(_satisfaction),
    )


@st.composite
def participant_interview_dict_strategy(draw):
    """Generate a dict representing a single participant interview summary."""
    return {
        "role": draw(_safe_text),
        "feels_served": draw(st.booleans()),
        "felt_respected": draw(st.booleans()),
        "is_win_win": draw(st.booleans()),
        "criticism": draw(_any_text),
        "satisfaction_rating": draw(_satisfaction),
    }


@st.composite
def dimensions_strategy(draw):
    """Generate the four score dimensions dict."""
    return {
        "fairness": draw(_dimension_score),
        "mutual_respect": draw(_dimension_score),
        "value_creation": draw(_dimension_score),
        "satisfaction": draw(_dimension_score),
    }


@st.composite
def evaluation_report_strategy(draw):
    """Generate a random valid EvaluationReport instance."""
    return EvaluationReport(
        participant_interviews=draw(
            st.lists(participant_interview_dict_strategy(), min_size=1, max_size=5)
        ),
        dimensions=draw(dimensions_strategy()),
        overall_score=draw(_satisfaction),
        verdict=draw(_safe_text),
        deal_status=draw(
            st.sampled_from(["Agreed", "Blocked", "Failed", "Negotiating", "Confirming"])
        ),
    )


# ---------------------------------------------------------------------------
# Feature: negotiation-evaluator
# Property 5: Output model serialization round-trip
# **Validates: Requirements 1.5, 3.1, 6.2, 7.1, 7.4**
#
# For any valid instance of ConfirmationOutput, EvaluationInterview, or
# EvaluationReport, serializing to JSON via .model_dump_json() and
# deserializing back via .model_validate_json() SHALL produce an
# equivalent object.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(output=confirmation_output_strategy())
def test_confirmation_output_round_trip(output: ConfirmationOutput):
    """Serializing and deserializing any valid ConfirmationOutput must produce an equal object.

    **Validates: Requirements 1.5, 3.1**
    """
    json_str = output.model_dump_json()
    restored = ConfirmationOutput.model_validate_json(json_str)
    assert restored == output


@settings(max_examples=100)
@given(interview=evaluation_interview_strategy())
def test_evaluation_interview_round_trip(interview: EvaluationInterview):
    """Serializing and deserializing any valid EvaluationInterview must produce an equal object.

    **Validates: Requirements 6.2**
    """
    json_str = interview.model_dump_json()
    restored = EvaluationInterview.model_validate_json(json_str)
    assert restored == interview


@settings(max_examples=100)
@given(report=evaluation_report_strategy())
def test_evaluation_report_round_trip(report: EvaluationReport):
    """Serializing and deserializing any valid EvaluationReport must produce an equal object.

    **Validates: Requirements 7.1, 7.4**
    """
    json_str = report.model_dump_json()
    restored = EvaluationReport.model_validate_json(json_str)
    assert restored == report
