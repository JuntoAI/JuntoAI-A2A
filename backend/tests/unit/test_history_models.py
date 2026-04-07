"""Unit tests for history response Pydantic models.

Requirements: 2.1, 2.2, 2.3
"""

import pytest
from pydantic import ValidationError

from app.models.history import DayGroup, SessionHistoryItem, SessionHistoryResponse


class TestSessionHistoryItem:
    """Requirement 2.1: SessionHistoryItem field validation."""

    def _valid_item(self, **overrides) -> dict:
        defaults = {
            "session_id": "sess-001",
            "scenario_id": "talent-war",
            "scenario_name": "Talent War",
            "deal_status": "Agreed",
            "total_tokens_used": 4500,
            "token_cost": 5,
            "created_at": "2025-06-23T14:30:00Z",
            "completed_at": "2025-06-23T14:32:15Z",
        }
        defaults.update(overrides)
        return defaults

    def test_valid_item(self):
        item = SessionHistoryItem(**self._valid_item())
        assert item.session_id == "sess-001"
        assert item.token_cost == 5

    def test_completed_at_optional(self):
        data = self._valid_item()
        del data["completed_at"]
        item = SessionHistoryItem(**data)
        assert item.completed_at is None

    def test_completed_at_none_explicit(self):
        item = SessionHistoryItem(**self._valid_item(completed_at=None))
        assert item.completed_at is None

    def test_total_tokens_used_ge_zero(self):
        with pytest.raises(ValidationError):
            SessionHistoryItem(**self._valid_item(total_tokens_used=-1))

    def test_total_tokens_used_zero_ok(self):
        item = SessionHistoryItem(**self._valid_item(total_tokens_used=0))
        assert item.total_tokens_used == 0

    def test_token_cost_ge_one(self):
        with pytest.raises(ValidationError):
            SessionHistoryItem(**self._valid_item(token_cost=0))

    def test_token_cost_negative_rejected(self):
        with pytest.raises(ValidationError):
            SessionHistoryItem(**self._valid_item(token_cost=-1))

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            SessionHistoryItem(scenario_id="x", scenario_name="X",
                               deal_status="Agreed", total_tokens_used=0,
                               token_cost=1, created_at="2025-01-01T00:00:00Z")


class TestDayGroup:
    """Requirement 2.2: DayGroup field validation."""

    def _valid_session(self) -> dict:
        return {
            "session_id": "s1", "scenario_id": "sc1", "scenario_name": "Sc1",
            "deal_status": "Agreed", "total_tokens_used": 1000,
            "token_cost": 1, "created_at": "2025-06-23T10:00:00Z",
        }

    def test_valid_day_group(self):
        group = DayGroup(date="2025-06-23", total_token_cost=1,
                         sessions=[SessionHistoryItem(**self._valid_session())])
        assert group.date == "2025-06-23"
        assert len(group.sessions) == 1

    def test_total_token_cost_ge_zero(self):
        with pytest.raises(ValidationError):
            DayGroup(date="2025-06-23", total_token_cost=-1, sessions=[])

    def test_total_token_cost_zero_ok(self):
        group = DayGroup(date="2025-06-23", total_token_cost=0, sessions=[])
        assert group.total_token_cost == 0

    def test_empty_sessions_list(self):
        group = DayGroup(date="2025-06-23", total_token_cost=0, sessions=[])
        assert group.sessions == []


class TestSessionHistoryResponse:
    """Requirement 2.3: SessionHistoryResponse field validation."""

    def test_valid_response(self):
        resp = SessionHistoryResponse(days=[], total_token_cost=0, period_days=7)
        assert resp.period_days == 7
        assert resp.days == []

    def test_period_days_ge_one(self):
        with pytest.raises(ValidationError):
            SessionHistoryResponse(days=[], total_token_cost=0, period_days=0)

    def test_period_days_negative_rejected(self):
        with pytest.raises(ValidationError):
            SessionHistoryResponse(days=[], total_token_cost=0, period_days=-1)

    def test_total_token_cost_ge_zero(self):
        with pytest.raises(ValidationError):
            SessionHistoryResponse(days=[], total_token_cost=-1, period_days=1)
