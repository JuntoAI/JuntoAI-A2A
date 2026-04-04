"""Unit tests for dispatcher milestone triggering integration.

Covers task 7.2:
- Mock generate_milestones and verify it is called at correct turn intervals
- Verify it is NOT called when milestone_summaries_enabled is False
- Verify it is NOT called when turn_count is not a multiple of milestone_interval
- Verify state is updated with milestone results
- Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 9.2
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.orchestrator.graph import _dispatcher, _should_generate_milestones
from app.orchestrator.state import NegotiationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    agent_states: dict[str, dict[str, Any]] | None = None,
    agreement_threshold: float = 5000.0,
    deal_status: str = "Negotiating",
    turn_count: int = 0,
    max_turns: int = 20,
    current_speaker: str = "Buyer",
    turn_order: list[str] | None = None,
    scenario_config: dict[str, Any] | None = None,
    milestone_summaries_enabled: bool = False,
    milestone_summaries: dict[str, list[dict[str, Any]]] | None = None,
    milestone_interval: int = 4,
    sliding_window_size: int = 3,
) -> NegotiationState:
    if turn_order is None:
        turn_order = ["Buyer", "Seller"]
    if agent_states is None:
        agent_states = {
            "Buyer": _negotiator_state("Buyer", 100000.0),
            "Seller": _negotiator_state("Seller", 200000.0),
        }
    return NegotiationState(
        session_id="s",
        scenario_id="s",
        turn_count=turn_count,
        max_turns=max_turns,
        current_speaker=current_speaker,
        deal_status=deal_status,
        current_offer=0.0,
        history=[],
        hidden_context={},
        warning_count=0,
        agreement_threshold=agreement_threshold,
        scenario_config=scenario_config or {"agents": [], "negotiation_params": {}},
        turn_order=turn_order,
        turn_order_index=0,
        agent_states=agent_states,
        active_toggles=[],
        total_tokens_used=100,
        stall_diagnosis=None,
        custom_prompts={},
        model_overrides={},
        structured_memory_enabled=False,
        structured_memory_roles=[],
        agent_memories={},
        milestone_summaries_enabled=milestone_summaries_enabled,
        milestone_summaries=milestone_summaries or {},
        milestone_interval=milestone_interval,
        sliding_window_size=sliding_window_size,
    )


def _negotiator_state(role: str, price: float) -> dict[str, Any]:
    return {
        "role": role,
        "name": role,
        "agent_type": "negotiator",
        "model_id": "gemini-3-flash-preview",
        "last_proposed_price": price,
        "warning_count": 0,
    }


# ===========================================================================
# _should_generate_milestones unit tests
# ===========================================================================


class TestShouldGenerateMilestones:
    """Unit tests for the _should_generate_milestones helper."""

    def test_disabled_returns_false(self):
        state = _make_state(milestone_summaries_enabled=False, turn_count=4, milestone_interval=4)
        assert _should_generate_milestones(state) is False

    def test_turn_zero_returns_false(self):
        state = _make_state(milestone_summaries_enabled=True, turn_count=0, milestone_interval=4)
        assert _should_generate_milestones(state) is False

    def test_non_multiple_returns_false(self):
        state = _make_state(milestone_summaries_enabled=True, turn_count=3, milestone_interval=4)
        assert _should_generate_milestones(state) is False

    def test_exact_multiple_returns_true(self):
        state = _make_state(milestone_summaries_enabled=True, turn_count=4, milestone_interval=4)
        assert _should_generate_milestones(state) is True

    def test_second_multiple_returns_true(self):
        state = _make_state(milestone_summaries_enabled=True, turn_count=8, milestone_interval=4)
        assert _should_generate_milestones(state) is True

    def test_interval_2_at_turn_2(self):
        state = _make_state(milestone_summaries_enabled=True, turn_count=2, milestone_interval=2)
        assert _should_generate_milestones(state) is True

    def test_interval_2_at_turn_3(self):
        state = _make_state(milestone_summaries_enabled=True, turn_count=3, milestone_interval=2)
        assert _should_generate_milestones(state) is False


# ===========================================================================
# Dispatcher milestone integration tests
# ===========================================================================


class TestDispatcherMilestoneTriggering:
    """Tests that _dispatcher calls generate_milestones at correct intervals."""

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.generate_milestones", new_callable=AsyncMock)
    async def test_calls_generate_milestones_at_interval(self, mock_gen: AsyncMock):
        """Verify generate_milestones is called when turn_count is a multiple of milestone_interval."""
        mock_gen.return_value = {
            "milestone_summaries": {"Buyer": [{"turn_number": 4, "summary": "test"}]},
            "total_tokens_used": 150,
        }
        state = _make_state(
            milestone_summaries_enabled=True,
            turn_count=4,
            milestone_interval=4,
        )
        delta = await _dispatcher(state)
        mock_gen.assert_called_once_with(state)
        assert delta["milestone_summaries"] == {"Buyer": [{"turn_number": 4, "summary": "test"}]}
        assert delta["total_tokens_used"] == 150

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.generate_milestones", new_callable=AsyncMock)
    async def test_not_called_when_disabled(self, mock_gen: AsyncMock):
        """Verify generate_milestones is NOT called when milestone_summaries_enabled is False."""
        state = _make_state(
            milestone_summaries_enabled=False,
            turn_count=4,
            milestone_interval=4,
        )
        delta = await _dispatcher(state)
        mock_gen.assert_not_called()
        assert delta == {}

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.generate_milestones", new_callable=AsyncMock)
    async def test_not_called_at_non_multiple(self, mock_gen: AsyncMock):
        """Verify generate_milestones is NOT called when turn_count is not a multiple."""
        state = _make_state(
            milestone_summaries_enabled=True,
            turn_count=5,
            milestone_interval=4,
        )
        delta = await _dispatcher(state)
        mock_gen.assert_not_called()
        assert delta == {}

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.generate_milestones", new_callable=AsyncMock)
    async def test_not_called_at_turn_zero(self, mock_gen: AsyncMock):
        """Verify generate_milestones is NOT called at turn 0."""
        state = _make_state(
            milestone_summaries_enabled=True,
            turn_count=0,
            milestone_interval=4,
        )
        delta = await _dispatcher(state)
        mock_gen.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.generate_milestones", new_callable=AsyncMock)
    async def test_state_updated_with_milestone_results(self, mock_gen: AsyncMock):
        """Verify the dispatcher merges milestone delta into its return value."""
        mock_gen.return_value = {
            "milestone_summaries": {
                "Buyer": [{"turn_number": 8, "summary": "buyer summary"}],
                "Seller": [{"turn_number": 8, "summary": "seller summary"}],
            },
            "total_tokens_used": 250,
        }
        state = _make_state(
            milestone_summaries_enabled=True,
            turn_count=8,
            milestone_interval=4,
        )
        delta = await _dispatcher(state)
        assert "milestone_summaries" in delta
        assert len(delta["milestone_summaries"]["Buyer"]) == 1
        assert len(delta["milestone_summaries"]["Seller"]) == 1
        assert delta["total_tokens_used"] == 250

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.generate_milestones", new_callable=AsyncMock)
    async def test_continues_on_generation_failure(self, mock_gen: AsyncMock):
        """Verify dispatcher continues when generate_milestones raises an exception."""
        mock_gen.side_effect = RuntimeError("LLM service unavailable")
        state = _make_state(
            milestone_summaries_enabled=True,
            turn_count=4,
            milestone_interval=4,
        )
        delta = await _dispatcher(state)
        # Should return empty dict — no crash, no milestone data
        assert delta == {}

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.generate_milestones", new_callable=AsyncMock)
    async def test_skipped_on_terminal_status(self, mock_gen: AsyncMock):
        """Milestone generation should not run when deal is already terminal."""
        state = _make_state(
            milestone_summaries_enabled=True,
            turn_count=4,
            milestone_interval=4,
            deal_status="Agreed",
        )
        delta = await _dispatcher(state)
        mock_gen.assert_not_called()
        assert delta == {}

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.generate_milestones", new_callable=AsyncMock)
    async def test_skipped_when_max_turns_reached(self, mock_gen: AsyncMock):
        """Milestone generation should not run when max_turns is reached (terminal takes priority)."""
        state = _make_state(
            milestone_summaries_enabled=True,
            turn_count=20,
            max_turns=20,
            milestone_interval=4,
        )
        delta = await _dispatcher(state)
        mock_gen.assert_not_called()
        assert delta["deal_status"] == "Failed"

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.generate_milestones", new_callable=AsyncMock)
    async def test_zero_overhead_when_disabled(self, mock_gen: AsyncMock):
        """When disabled, generate_milestones is never imported/called — zero overhead."""
        for turn in range(1, 20):
            state = _make_state(
                milestone_summaries_enabled=False,
                turn_count=turn,
                milestone_interval=4,
            )
            await _dispatcher(state)
        mock_gen.assert_not_called()
