"""Unit tests for NegotiationParams sliding_window_size and milestone_interval fields.

Requirements: 1.1, 1.2, 1.3, 1.4
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.scenarios.loader import load_scenario_from_file
from app.scenarios.models import NegotiationParams

DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "scenarios"
    / "data"
)


def _base_params(**overrides) -> dict:
    defaults = {
        "max_turns": 10,
        "agreement_threshold": 1000.0,
        "turn_order": ["Buyer", "Seller"],
    }
    defaults.update(overrides)
    return defaults


class TestSlidingWindowSize:
    """Requirement 1.1: sliding_window_size field with default=3, ge=1."""

    def test_explicit_value(self):
        params = NegotiationParams(**_base_params(sliding_window_size=5))
        assert params.sliding_window_size == 5

    def test_default_when_omitted(self):
        params = NegotiationParams(**_base_params())
        assert params.sliding_window_size == 3

    def test_minimum_value_1_accepted(self):
        params = NegotiationParams(**_base_params(sliding_window_size=1))
        assert params.sliding_window_size == 1

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="sliding_window_size"):
            NegotiationParams(**_base_params(sliding_window_size=0))

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="sliding_window_size"):
            NegotiationParams(**_base_params(sliding_window_size=-1))


class TestMilestoneInterval:
    """Requirement 1.2: milestone_interval field with default=4, ge=2."""

    def test_explicit_value(self):
        params = NegotiationParams(**_base_params(milestone_interval=6))
        assert params.milestone_interval == 6

    def test_default_when_omitted(self):
        params = NegotiationParams(**_base_params())
        assert params.milestone_interval == 4

    def test_minimum_value_2_accepted(self):
        params = NegotiationParams(**_base_params(milestone_interval=2))
        assert params.milestone_interval == 2

    def test_value_1_rejected(self):
        with pytest.raises(ValidationError, match="milestone_interval"):
            NegotiationParams(**_base_params(milestone_interval=1))

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="milestone_interval"):
            NegotiationParams(**_base_params(milestone_interval=0))


class TestBothFieldsTogether:
    """Requirement 1.3: Both fields work together with defaults."""

    def test_both_explicit(self):
        params = NegotiationParams(
            **_base_params(sliding_window_size=5, milestone_interval=8)
        )
        assert params.sliding_window_size == 5
        assert params.milestone_interval == 8

    def test_both_default(self):
        params = NegotiationParams(**_base_params())
        assert params.sliding_window_size == 3
        assert params.milestone_interval == 4


class TestExistingScenarioFilesBackwardCompat:
    """Requirement 1.4: All existing scenario JSON files parse without errors."""

    @pytest.fixture(scope="class")
    def scenario_files(self) -> list[Path]:
        return sorted(DATA_DIR.glob("*.scenario.json"))

    def test_scenario_files_exist(self, scenario_files):
        assert len(scenario_files) > 0, "No scenario files found"

    def test_all_scenarios_parse_without_errors(self, scenario_files):
        for path in scenario_files:
            scenario = load_scenario_from_file(path)
            # Verify defaults are applied for the new fields
            assert scenario.negotiation_params.sliding_window_size == 3
            assert scenario.negotiation_params.milestone_interval == 4
