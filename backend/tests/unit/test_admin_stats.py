"""Integration tests for the admin stats endpoint logic.

Feature: 270_public-stats-dashboard
Validates: Requirements 11.1, 11.4, 11.5

Note: These tests verify the stats aggregation logic and response shape
directly, avoiding the module-reload pattern that causes hangs in the
admin integration test suite. The endpoint wiring is verified by the
router registration test.
"""

from datetime import datetime, timezone

import pytest

from app.models.stats import StatsResponse
from app.services.stats_aggregator import compute_stats

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TODAY_STR = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_doc(
    session_id: str,
    scenario_id: str = "talent-war",
    deal_status: str = "Agreed",
    turn_count: int = 5,
    total_tokens_used: int = 1000,
    owner_email: str = "user@example.com",
    created_at: str | None = None,
    agent_calls: list[dict] | None = None,
    endpoint_overrides: dict | None = None,
) -> dict:
    doc = {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "deal_status": deal_status,
        "turn_count": turn_count,
        "total_tokens_used": total_tokens_used,
        "owner_email": owner_email,
        "created_at": created_at or f"{TODAY_STR}T10:00:00+00:00",
    }
    if agent_calls is not None:
        doc["agent_calls"] = agent_calls
    if endpoint_overrides is not None:
        doc["endpoint_overrides"] = endpoint_overrides
    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStatsEndpointLogic:
    """Test the stats aggregation logic that powers GET /api/v1/admin/stats."""

    @pytest.mark.integration
    def test_returns_valid_stats_response_shape(self):
        """Validates: Requirement 11.1 — endpoint returns all metrics as JSON."""
        sessions = [
            _make_session_doc("s1", deal_status="Agreed", total_tokens_used=500),
            _make_session_doc("s2", deal_status="Negotiating", total_tokens_used=300),
            _make_session_doc(
                "s3", deal_status="Failed", total_tokens_used=200,
                agent_calls=[{"model_id": "gemini-3-flash-preview", "input_tokens": 100, "output_tokens": 50, "latency_ms": 400}],
            ),
        ]

        result = compute_stats(sessions)

        # Verify it's a valid StatsResponse
        assert isinstance(result, StatsResponse)

        # Verify all fields are present via JSON serialization
        data = result.model_dump()
        for key in [
            "unique_users_today", "unique_users_7d", "simulations_today",
            "simulations_7d", "active_simulations", "outcomes_today",
            "outcomes_7d", "total_tokens_today", "total_tokens_7d",
            "model_tokens", "model_performance", "scenario_popularity",
            "avg_turns_today", "avg_turns_7d", "custom_scenarios_today",
            "custom_scenarios_7d", "custom_scenarios_all_time",
            "custom_agent_sessions_today", "custom_agent_sessions_7d",
            "custom_agent_sessions_all_time", "generated_at",
        ]:
            assert key in data, f"Missing key: {key}"

        # Verify computed values
        assert data["simulations_today"] == 3
        assert data["active_simulations"] == 1
        assert data["total_tokens_today"] == 1000

    @pytest.mark.integration
    def test_empty_sessions_returns_zeros(self):
        """Validates: empty state returns all zeros, no errors."""
        result = compute_stats([])
        data = result.model_dump()

        assert data["unique_users_today"] == 0
        assert data["simulations_today"] == 0
        assert data["active_simulations"] == 0
        assert data["total_tokens_today"] == 0
        assert data["avg_turns_today"] is None
        assert data["model_tokens"] == []
        assert data["scenario_popularity"] == []

    @pytest.mark.integration
    def test_outcomes_breakdown_correct(self):
        """Validates: Requirement 4.4 — outcome breakdown by status."""
        sessions = [
            _make_session_doc("s1", deal_status="Agreed"),
            _make_session_doc("s2", deal_status="Agreed"),
            _make_session_doc("s3", deal_status="Blocked"),
            _make_session_doc("s4", deal_status="Failed"),
            _make_session_doc("s5", deal_status="Negotiating"),
        ]

        result = compute_stats(sessions)

        assert result.outcomes_today.agreed == 2
        assert result.outcomes_today.blocked == 1
        assert result.outcomes_today.failed == 1

    @pytest.mark.integration
    def test_model_tokens_and_performance(self):
        """Validates: Requirements 6.1, 6.2, 7.1, 7.2 — per-model metrics."""
        sessions = [
            _make_session_doc(
                "s1", agent_calls=[
                    {"model_id": "gemini-3-flash-preview", "input_tokens": 100, "output_tokens": 200, "latency_ms": 500},
                    {"model_id": "claude-sonnet-4", "input_tokens": 150, "output_tokens": 250, "latency_ms": 800},
                ],
            ),
            _make_session_doc(
                "s2", agent_calls=[
                    {"model_id": "gemini-3-flash-preview", "input_tokens": 80, "output_tokens": 120, "latency_ms": 450},
                ],
            ),
        ]

        result = compute_stats(sessions)

        token_map = {m.model_id: m for m in result.model_tokens}
        assert "gemini-3-flash-preview" in token_map
        assert "claude-sonnet-4" in token_map
        assert token_map["gemini-3-flash-preview"].tokens_today == 500  # (100+200) + (80+120)
        assert token_map["claude-sonnet-4"].tokens_today == 400  # 150+250

        perf_map = {m.model_id: m for m in result.model_performance}
        assert perf_map["gemini-3-flash-preview"].avg_response_time_today == pytest.approx(475.0)  # (500+450)/2
        assert perf_map["claude-sonnet-4"].avg_response_time_today == pytest.approx(800.0)

    @pytest.mark.integration
    def test_scenario_popularity_sorted_descending(self):
        """Validates: Requirement 8.1 — scenarios ranked by count."""
        sessions = [
            _make_session_doc("s1", scenario_id="talent-war"),
            _make_session_doc("s2", scenario_id="talent-war"),
            _make_session_doc("s3", scenario_id="talent-war"),
            _make_session_doc("s4", scenario_id="mna-buyout"),
            _make_session_doc("s5", scenario_id="b2b-sales"),
            _make_session_doc("s6", scenario_id="b2b-sales"),
        ]

        result = compute_stats(sessions)

        # Should be sorted descending by 7d count
        counts = [sp.count_7d for sp in result.scenario_popularity]
        assert counts == sorted(counts, reverse=True)
        assert result.scenario_popularity[0].scenario_id == "talent-war"

    @pytest.mark.integration
    def test_custom_agent_sessions_detected(self):
        """Validates: Requirement 16.4 — endpoint_overrides detection."""
        sessions = [
            _make_session_doc("s1"),  # no overrides
            _make_session_doc("s2", endpoint_overrides={"Buyer": "http://my-agent.com"}),
            _make_session_doc("s3", endpoint_overrides={}),  # empty = not custom
        ]

        result = compute_stats(sessions)

        assert result.custom_agent_sessions_today == 1
        assert result.custom_agent_sessions_all_time == 1

    @pytest.mark.integration
    def test_avg_turns_only_terminal_sessions(self):
        """Validates: Requirement 9.3 — avg turns from terminal sessions only."""
        sessions = [
            _make_session_doc("s1", deal_status="Agreed", turn_count=6),
            _make_session_doc("s2", deal_status="Failed", turn_count=10),
            _make_session_doc("s3", deal_status="Negotiating", turn_count=3),  # excluded
            _make_session_doc("s4", deal_status="Confirming", turn_count=7),  # excluded
        ]

        result = compute_stats(sessions)

        assert result.avg_turns_today == pytest.approx(8.0)  # (6+10)/2

    @pytest.mark.integration
    def test_router_registration(self):
        """Validates: Requirement 11.1 — stats route is registered in admin router."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"ADMIN_PASSWORD": "test", "RUN_MODE": "cloud"}):
            import importlib
            import app.config as config_mod
            importlib.reload(config_mod)

            from app.routers.admin import router
            paths = [r.path for r in router.routes]
            assert "/admin/stats" in paths
