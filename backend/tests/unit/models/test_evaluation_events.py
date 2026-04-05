"""Unit tests for EvaluationInterviewEvent and EvaluationCompleteEvent SSE models.

Validates Requirements 8.1, 8.2, 8.3:
- EvaluationInterviewEvent shape for "interviewing" and "complete" statuses
- EvaluationCompleteEvent shape with dimensions, overall_score, verdict
- Serialization round-trips for both models
"""

import json

from app.models.events import EvaluationCompleteEvent, EvaluationInterviewEvent


# --- EvaluationInterviewEvent ---


def test_interview_event_interviewing_status_optional_fields_none():
    """Status='interviewing' — optional fields default to None."""
    event = EvaluationInterviewEvent(
        event_type="evaluation_interview",
        agent_name="Buyer",
        turn_number=1,
        status="interviewing",
    )
    assert event.event_type == "evaluation_interview"
    assert event.agent_name == "Buyer"
    assert event.turn_number == 1
    assert event.status == "interviewing"
    assert event.satisfaction_rating is None
    assert event.felt_respected is None
    assert event.is_win_win is None


def test_interview_event_complete_status_fields_populated():
    """Status='complete' — optional fields populated with values."""
    event = EvaluationInterviewEvent(
        event_type="evaluation_interview",
        agent_name="Seller",
        turn_number=2,
        status="complete",
        satisfaction_rating=8,
        felt_respected=True,
        is_win_win=False,
    )
    assert event.status == "complete"
    assert event.satisfaction_rating == 8
    assert event.felt_respected is True
    assert event.is_win_win is False


def test_interview_event_serialization_round_trip():
    """Serialize to JSON and back — object should be equivalent."""
    original = EvaluationInterviewEvent(
        event_type="evaluation_interview",
        agent_name="Candidate",
        turn_number=3,
        status="complete",
        satisfaction_rating=6,
        felt_respected=False,
        is_win_win=True,
    )
    json_str = original.model_dump_json()
    restored = EvaluationInterviewEvent.model_validate_json(json_str)
    assert restored == original


# --- EvaluationCompleteEvent ---


def test_complete_event_all_fields_populated():
    """EvaluationCompleteEvent with all fields set."""
    event = EvaluationCompleteEvent(
        event_type="evaluation_complete",
        dimensions={
            "fairness": 7,
            "mutual_respect": 8,
            "value_creation": 5,
            "satisfaction": 7,
        },
        overall_score=6,
        verdict="A functional deal but lacking creative value.",
        participant_interviews=[
            {"role": "Buyer", "satisfaction_rating": 7, "felt_respected": True},
            {"role": "Seller", "satisfaction_rating": 6, "felt_respected": True},
        ],
        deal_status="Agreed",
    )
    assert event.event_type == "evaluation_complete"
    assert event.dimensions["fairness"] == 7
    assert event.dimensions["value_creation"] == 5
    assert event.overall_score == 6
    assert event.verdict == "A functional deal but lacking creative value."
    assert len(event.participant_interviews) == 2
    assert event.deal_status == "Agreed"


def test_complete_event_serialization_round_trip():
    """Serialize to JSON and back — object should be equivalent."""
    original = EvaluationCompleteEvent(
        event_type="evaluation_complete",
        dimensions={
            "fairness": 3,
            "mutual_respect": 4,
            "value_creation": 2,
            "satisfaction": 5,
        },
        overall_score=3,
        verdict="Poor outcome. One party clearly lost.",
        participant_interviews=[
            {"role": "Recruiter", "satisfaction_rating": 8},
        ],
        deal_status="Failed",
    )
    json_str = original.model_dump_json()
    restored = EvaluationCompleteEvent.model_validate_json(json_str)
    assert restored == original


def test_complete_event_type_is_always_evaluation_complete():
    """event_type Literal is enforced to 'evaluation_complete'."""
    event = EvaluationCompleteEvent(
        event_type="evaluation_complete",
        dimensions={"fairness": 10, "mutual_respect": 10,
                     "value_creation": 10, "satisfaction": 10},
        overall_score=10,
        verdict="Perfect negotiation.",
        participant_interviews=[],
        deal_status="Agreed",
    )
    # Literal field always holds the expected value
    assert event.event_type == "evaluation_complete"
    # Also verify it survives dict serialization
    dumped = event.model_dump()
    assert dumped["event_type"] == "evaluation_complete"
    # And JSON round-trip
    parsed = json.loads(event.model_dump_json())
    assert parsed["event_type"] == "evaluation_complete"
