"""Unit tests for share service extraction helpers.

Tests _extract_evaluation_scores and _extract_public_conversation
which extract public-facing data from session documents.
"""

from __future__ import annotations

import pytest

from app.models.share import EvaluationScores, PublicMessage
from app.services.share_service import (
    _extract_evaluation_scores,
    _extract_public_conversation,
)


# ---------------------------------------------------------------------------
# _extract_evaluation_scores
# ---------------------------------------------------------------------------


class TestExtractEvaluationScores:
    """Tests for extracting evaluation dimension scores from session docs."""

    def test_extracts_scores_from_valid_evaluation(self):
        session_doc = {
            "evaluation": {
                "dimensions": {
                    "fairness": 7,
                    "mutual_respect": 8,
                    "value_creation": 6,
                    "satisfaction": 9,
                },
                "overall_score": 7,
                "verdict": "Good negotiation",
            }
        }
        result = _extract_evaluation_scores(session_doc)
        assert result is not None
        assert result.fairness == 7
        assert result.mutual_respect == 8
        assert result.value_creation == 6
        assert result.satisfaction == 9
        assert result.overall_score == 7

    def test_returns_none_when_no_evaluation(self):
        assert _extract_evaluation_scores({}) is None

    def test_returns_none_when_evaluation_is_not_dict(self):
        assert _extract_evaluation_scores({"evaluation": "invalid"}) is None

    def test_returns_none_when_dimensions_missing(self):
        assert _extract_evaluation_scores({"evaluation": {"overall_score": 5}}) is None

    def test_returns_none_when_overall_score_missing(self):
        session_doc = {
            "evaluation": {
                "dimensions": {"fairness": 5, "mutual_respect": 5, "value_creation": 5, "satisfaction": 5},
            }
        }
        assert _extract_evaluation_scores(session_doc) is None

    def test_defaults_missing_dimensions_to_5(self):
        session_doc = {
            "evaluation": {
                "dimensions": {"fairness": 8},
                "overall_score": 6,
            }
        }
        result = _extract_evaluation_scores(session_doc)
        assert result is not None
        assert result.fairness == 8
        assert result.mutual_respect == 5
        assert result.value_creation == 5
        assert result.satisfaction == 5


# ---------------------------------------------------------------------------
# _extract_public_conversation
# ---------------------------------------------------------------------------


class TestExtractPublicConversation:
    """Tests for extracting public messages from session history."""

    def test_extracts_public_messages(self):
        session_doc = {
            "history": [
                {
                    "role": "Buyer",
                    "name": "Alice",
                    "agent_type": "negotiator",
                    "turn_number": 1,
                    "content": {
                        "inner_thought": "I should start low.",
                        "public_message": "I offer $500k.",
                        "proposed_price": 500000,
                    },
                },
                {
                    "role": "Regulator",
                    "name": "Compliance Bot",
                    "agent_type": "regulator",
                    "turn_number": 1,
                    "content": {
                        "reasoning": "Offer is within range.",
                        "public_message": "No issues detected.",
                        "status": "CLEAR",
                    },
                },
            ]
        }
        result = _extract_public_conversation(session_doc)
        assert len(result) == 2
        assert result[0].agent_name == "Alice"
        assert result[0].message == "I offer $500k."
        assert result[0].turn_number == 1
        assert result[1].agent_name == "Compliance Bot"
        assert result[1].agent_type == "regulator"

    def test_returns_empty_when_no_history(self):
        assert _extract_public_conversation({}) == []

    def test_returns_empty_when_history_is_not_list(self):
        assert _extract_public_conversation({"history": "invalid"}) == []

    def test_skips_entries_without_public_message(self):
        session_doc = {
            "history": [
                {"role": "Buyer", "content": {"inner_thought": "thinking"}},
                {"role": "Seller", "content": {"public_message": "Hello"}},
            ]
        }
        result = _extract_public_conversation(session_doc)
        assert len(result) == 1
        assert result[0].message == "Hello"

    def test_skips_entries_with_empty_public_message(self):
        session_doc = {
            "history": [
                {"role": "Buyer", "content": {"public_message": ""}},
                {"role": "Seller", "content": {"public_message": "Real message"}},
            ]
        }
        result = _extract_public_conversation(session_doc)
        assert len(result) == 1
        assert result[0].message == "Real message"

    def test_never_includes_inner_thought(self):
        """Public conversation must never leak inner_thought or reasoning."""
        session_doc = {
            "history": [
                {
                    "role": "Buyer",
                    "name": "Alice",
                    "agent_type": "negotiator",
                    "turn_number": 1,
                    "content": {
                        "inner_thought": "SECRET_THOUGHT",
                        "public_message": "I offer $500k.",
                    },
                },
            ]
        }
        result = _extract_public_conversation(session_doc)
        serialized = str([m.model_dump() for m in result])
        assert "SECRET_THOUGHT" not in serialized

    def test_falls_back_to_role_when_name_missing(self):
        session_doc = {
            "history": [
                {
                    "role": "Buyer",
                    "agent_type": "negotiator",
                    "turn_number": 1,
                    "content": {"public_message": "Hello"},
                },
            ]
        }
        result = _extract_public_conversation(session_doc)
        assert result[0].agent_name == "Buyer"
