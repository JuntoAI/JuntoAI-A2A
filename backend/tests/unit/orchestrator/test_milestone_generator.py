"""Unit tests for the MilestoneGenerator module.

Covers task 6.2:
- Summaries generated for each agent with correct prompt content
- LLM failure for one agent does not block others
- Token usage tracked correctly
- max_tokens=300 passed to LLM call
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.orchestrator.milestone_generator import (
    _build_milestone_prompt,
    _format_existing_milestones,
    _format_history,
    generate_milestones,
)
from app.orchestrator.state import NegotiationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(
    role: str = "Buyer",
    name: str = "Alice",
    agent_type: str = "negotiator",
    model_id: str = "gemini-3-flash-preview",
    goals: list[str] | None = None,
    budget: dict | None = None,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "role": role,
        "name": name,
        "type": agent_type,
        "model_id": model_id,
    }
    if goals is not None:
        cfg["goals"] = goals
    if budget is not None:
        cfg["budget"] = budget
    return cfg


def _make_state(
    agents: list[dict[str, Any]] | None = None,
    history: list[dict[str, Any]] | None = None,
    milestone_summaries: dict[str, list[dict[str, Any]]] | None = None,
    turn_count: int = 4,
    total_tokens_used: int = 0,
) -> NegotiationState:
    if agents is None:
        agents = [
            _make_agent_config("Buyer", "Alice", "negotiator", "gemini-3-flash-preview",
                               goals=["Get lowest price"], budget={"min": 100000, "max": 200000}),
            _make_agent_config("Seller", "Bob", "negotiator", "claude-sonnet-4-6",
                               goals=["Maximize sale price"]),
        ]
    if history is None:
        history = [
            {"role": "Buyer", "turn_number": 1, "content": {"public_message": "I offer 150k", "inner_thought": "Starting low", "proposed_price": 150000}},
            {"role": "Seller", "turn_number": 1, "content": {"public_message": "I want 250k", "inner_thought": "Aiming high", "proposed_price": 250000}},
            {"role": "Buyer", "turn_number": 2, "content": {"public_message": "How about 170k?", "inner_thought": "Moving up slightly", "proposed_price": 170000}},
            {"role": "Seller", "turn_number": 2, "content": {"public_message": "230k is my best", "inner_thought": "Conceding a bit", "proposed_price": 230000}},
        ]
    if milestone_summaries is None:
        milestone_summaries = {"Buyer": [], "Seller": []}

    return NegotiationState(
        session_id="test-sess",
        scenario_id="test-scenario",
        turn_count=turn_count,
        max_turns=15,
        current_speaker="Buyer",
        deal_status="Negotiating",
        current_offer=230000.0,
        history=history,
        hidden_context={},
        warning_count=0,
        agreement_threshold=5000.0,
        scenario_config={
            "id": "test-scenario",
            "agents": agents,
            "negotiation_params": {"max_turns": 15},
        },
        turn_order=["Buyer", "Seller"],
        turn_order_index=0,
        agent_states={},
        active_toggles=[],
        total_tokens_used=total_tokens_used,
        stall_diagnosis=None,
        custom_prompts={},
        model_overrides={},
        structured_memory_enabled=True,
        structured_memory_roles=["Buyer", "Seller"],
        agent_memories={},
        milestone_summaries_enabled=True,
        milestone_summaries=milestone_summaries,
        sliding_window_size=3,
        milestone_interval=4,
    )


def _make_fake_response(content: str = "Summary text", total_tokens: int = 100):
    """Create a fake AIMessage-like response with usage_metadata."""
    response = AsyncMock()
    response.content = content
    response.usage_metadata = {"total_tokens": total_tokens}
    return response


# ---------------------------------------------------------------------------
# Prompt building tests
# ---------------------------------------------------------------------------


class TestFormatHistory:
    def test_empty_history(self):
        assert _format_history([]) == "(No history yet)"

    def test_formats_entries(self):
        history = [
            {"role": "Buyer", "turn_number": 1, "content": {"public_message": "I offer 100k"}},
            {"role": "Seller", "turn_number": 1, "content": {"reasoning": "Price too low"}},
        ]
        result = _format_history(history)
        assert "[Turn 1 - Buyer]" in result
        assert "I offer 100k" in result
        assert "[Turn 1 - Seller]" in result
        assert "Price too low" in result


class TestFormatExistingMilestones:
    def test_empty_milestones(self):
        assert _format_existing_milestones([]) == ""

    def test_formats_milestones(self):
        milestones = [{"turn_number": 4, "summary": "Good progress so far"}]
        result = _format_existing_milestones(milestones)
        assert "As of turn 4" in result
        assert "Good progress so far" in result


class TestBuildMilestonePrompt:
    def test_contains_agent_identity(self):
        agent = _make_agent_config("Buyer", "Alice")
        state = _make_state()
        prompt = _build_milestone_prompt(agent, state)
        assert "Alice" in prompt
        assert "Buyer" in prompt

    def test_contains_history(self):
        agent = _make_agent_config("Buyer", "Alice")
        state = _make_state()
        prompt = _build_milestone_prompt(agent, state)
        assert "I offer 150k" in prompt
        assert "I want 250k" in prompt

    def test_contains_goals(self):
        agent = _make_agent_config("Buyer", "Alice", goals=["Get lowest price"])
        state = _make_state()
        prompt = _build_milestone_prompt(agent, state)
        assert "Get lowest price" in prompt

    def test_contains_budget(self):
        agent = _make_agent_config("Buyer", "Alice", budget={"min": 100000, "max": 200000})
        state = _make_state()
        prompt = _build_milestone_prompt(agent, state)
        assert "min=100000" in prompt
        assert "max=200000" in prompt

    def test_contains_inner_thoughts(self):
        agent = _make_agent_config("Buyer", "Alice")
        state = _make_state()
        prompt = _build_milestone_prompt(agent, state)
        assert "Starting low" in prompt
        assert "Moving up slightly" in prompt

    def test_contains_existing_milestones(self):
        agent = _make_agent_config("Buyer", "Alice")
        state = _make_state(
            milestone_summaries={
                "Buyer": [{"turn_number": 4, "summary": "Previous summary content"}],
                "Seller": [],
            }
        )
        prompt = _build_milestone_prompt(agent, state)
        assert "Previous summary content" in prompt

    def test_contains_summary_instructions(self):
        agent = _make_agent_config("Buyer", "Alice")
        state = _make_state()
        prompt = _build_milestone_prompt(agent, state)
        assert "Key positions" in prompt
        assert "Major concessions" in prompt
        assert "Unresolved disputes" in prompt
        assert "Regulatory concerns" in prompt
        assert "trajectory" in prompt
        assert "no JSON wrapping" in prompt


# ---------------------------------------------------------------------------
# generate_milestones tests
# ---------------------------------------------------------------------------


class TestGenerateMilestones:
    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_generates_summaries_for_each_agent(self, mock_router):
        """Summaries are generated for every agent in the scenario."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("Agent summary", 80)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_count=4)
        result = await generate_milestones(state)

        assert "Buyer" in result["milestone_summaries"]
        assert "Seller" in result["milestone_summaries"]
        assert len(result["milestone_summaries"]["Buyer"]) == 1
        assert len(result["milestone_summaries"]["Seller"]) == 1
        assert result["milestone_summaries"]["Buyer"][0]["summary"] == "Agent summary"
        assert result["milestone_summaries"]["Buyer"][0]["turn_number"] == 4
        assert result["milestone_summaries"]["Seller"][0]["turn_number"] == 4

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_max_tokens_300_passed_to_llm(self, mock_router):
        """max_tokens=300 is passed to the ainvoke call."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("Summary", 50)
        mock_router.get_model.return_value = mock_model

        state = _make_state()
        await generate_milestones(state)

        # Check all ainvoke calls had max_tokens=300
        for call in mock_model.ainvoke.call_args_list:
            _, kwargs = call
            assert kwargs.get("max_tokens") == 300

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_llm_failure_does_not_block_others(self, mock_router):
        """If LLM fails for one agent, the other agent still gets a summary."""
        mock_model_ok = AsyncMock()
        mock_model_ok.ainvoke.return_value = _make_fake_response("Good summary", 90)

        mock_model_fail = AsyncMock()
        mock_model_fail.ainvoke.side_effect = RuntimeError("LLM unavailable")

        # First call (Buyer) fails, second call (Seller) succeeds
        def side_effect(model_id, **kwargs):
            if model_id == "gemini-3-flash-preview":
                return mock_model_fail
            return mock_model_ok

        mock_router.get_model.side_effect = side_effect

        state = _make_state(turn_count=4)
        result = await generate_milestones(state)

        # Buyer failed — no summary added
        assert len(result["milestone_summaries"]["Buyer"]) == 0
        # Seller succeeded
        assert len(result["milestone_summaries"]["Seller"]) == 1
        assert result["milestone_summaries"]["Seller"][0]["summary"] == "Good summary"

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_token_usage_tracked(self, mock_router):
        """Token usage from all successful LLM calls is accumulated."""
        mock_model = AsyncMock()
        mock_model.ainvoke.side_effect = [
            _make_fake_response("Summary A", 80),
            _make_fake_response("Summary B", 120),
        ]
        mock_router.get_model.return_value = mock_model

        state = _make_state(total_tokens_used=500, turn_count=4)
        result = await generate_milestones(state)

        # 500 existing + 80 + 120 = 700
        assert result["total_tokens_used"] == 700

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_token_usage_zero_on_all_failures(self, mock_router):
        """When all LLM calls fail, token delta is zero."""
        mock_model = AsyncMock()
        mock_model.ainvoke.side_effect = RuntimeError("All fail")
        mock_router.get_model.return_value = mock_model

        state = _make_state(total_tokens_used=200, turn_count=4)
        result = await generate_milestones(state)

        assert result["total_tokens_used"] == 200

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_uses_correct_model_per_agent(self, mock_router):
        """Each agent's own model_id is used for the LLM call."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("Summary", 50)
        mock_router.get_model.return_value = mock_model

        state = _make_state()
        await generate_milestones(state)

        # Verify get_model was called with each agent's model_id
        call_args = [call.args[0] for call in mock_router.get_model.call_args_list]
        assert "gemini-3-flash-preview" in call_args
        assert "claude-sonnet-4-6" in call_args

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_appends_to_existing_milestones(self, mock_router):
        """New milestones are appended to existing ones, not replacing them."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("New summary", 60)
        mock_router.get_model.return_value = mock_model

        existing = {
            "Buyer": [{"turn_number": 4, "summary": "Old buyer summary"}],
            "Seller": [{"turn_number": 4, "summary": "Old seller summary"}],
        }
        state = _make_state(milestone_summaries=existing, turn_count=8)
        result = await generate_milestones(state)

        assert len(result["milestone_summaries"]["Buyer"]) == 2
        assert result["milestone_summaries"]["Buyer"][0]["summary"] == "Old buyer summary"
        assert result["milestone_summaries"]["Buyer"][1]["summary"] == "New summary"
        assert result["milestone_summaries"]["Buyer"][1]["turn_number"] == 8

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_prompt_includes_full_history(self, mock_router):
        """The prompt sent to the LLM includes the full negotiation history."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("Summary", 50)
        mock_router.get_model.return_value = mock_model

        state = _make_state()
        await generate_milestones(state)

        # Check the prompt content of the first call
        first_call_messages = mock_model.ainvoke.call_args_list[0].args[0]
        prompt_text = first_call_messages[0].content
        assert "I offer 150k" in prompt_text
        assert "I want 250k" in prompt_text

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_model_router_failure_non_blocking(self, mock_router):
        """If model_router.get_model raises, the agent is skipped gracefully."""
        mock_router.get_model.side_effect = Exception("Model not found")

        state = _make_state(turn_count=4)
        result = await generate_milestones(state)

        # No summaries generated, but no crash
        assert len(result["milestone_summaries"]["Buyer"]) == 0
        assert len(result["milestone_summaries"]["Seller"]) == 0
        assert result["total_tokens_used"] == 0

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_handles_list_content_response(self, mock_router):
        """Handles LLM responses where content is a list of blocks (Anthropic style)."""
        mock_model = AsyncMock()
        response = AsyncMock()
        response.content = [{"type": "text", "text": "Block summary"}]
        response.usage_metadata = {"total_tokens": 75}
        mock_model.ainvoke.return_value = response
        mock_router.get_model.return_value = mock_model

        agents = [_make_agent_config("Buyer", "Alice")]
        state = _make_state(
            agents=agents,
            milestone_summaries={"Buyer": []},
        )
        result = await generate_milestones(state)

        assert result["milestone_summaries"]["Buyer"][0]["summary"] == "Block summary"


# ---------------------------------------------------------------------------
# Milestone generation at different negotiation stages
# ---------------------------------------------------------------------------


class TestMilestoneGenerationStages:
    """Tests milestone generation at early, mid, and late negotiation stages."""

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_early_stage_single_turn(self, mock_router):
        """Milestone at turn 1 with minimal history."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("Early summary", 40)
        mock_router.get_model.return_value = mock_model

        agents = [_make_agent_config("Buyer", "Alice")]
        history = [
            {"role": "Buyer", "turn_number": 1, "content": {"public_message": "Opening offer"}},
        ]
        state = _make_state(
            agents=agents,
            history=history,
            milestone_summaries={"Buyer": []},
            turn_count=1,
        )
        result = await generate_milestones(state)

        assert result["milestone_summaries"]["Buyer"][0]["turn_number"] == 1
        assert result["milestone_summaries"]["Buyer"][0]["summary"] == "Early summary"

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_mid_stage_with_accumulated_milestones(self, mock_router):
        """Milestone at turn 8 with a prior milestone at turn 4."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("Mid summary", 90)
        mock_router.get_model.return_value = mock_model

        agents = [_make_agent_config("Buyer", "Alice")]
        history = [
            {"role": "Buyer", "turn_number": i, "content": {"public_message": f"Msg {i}"}}
            for i in range(1, 9)
        ]
        existing = {
            "Buyer": [{"turn_number": 4, "summary": "Early progress summary"}],
        }
        state = _make_state(
            agents=agents,
            history=history,
            milestone_summaries=existing,
            turn_count=8,
        )
        result = await generate_milestones(state)

        buyer_ms = result["milestone_summaries"]["Buyer"]
        assert len(buyer_ms) == 2
        assert buyer_ms[0]["turn_number"] == 4  # existing preserved
        assert buyer_ms[1]["turn_number"] == 8  # new appended

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_late_stage_near_max_turns(self, mock_router):
        """Milestone at turn 14 of 15 max — near deadline."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("Final push summary", 110)
        mock_router.get_model.return_value = mock_model

        agents = [
            _make_agent_config("Buyer", "Alice"),
            _make_agent_config("Seller", "Bob"),
        ]
        history = [
            {"role": r, "turn_number": t, "content": {"public_message": f"Turn {t} {r}"}}
            for t in range(1, 15)
            for r in ["Buyer", "Seller"]
        ]
        existing = {
            "Buyer": [
                {"turn_number": 4, "summary": "Early"},
                {"turn_number": 8, "summary": "Mid"},
            ],
            "Seller": [
                {"turn_number": 4, "summary": "Early seller"},
            ],
        }
        state = _make_state(
            agents=agents,
            history=history,
            milestone_summaries=existing,
            turn_count=14,
        )
        result = await generate_milestones(state)

        assert len(result["milestone_summaries"]["Buyer"]) == 3
        assert result["milestone_summaries"]["Buyer"][2]["turn_number"] == 14
        assert len(result["milestone_summaries"]["Seller"]) == 2
        assert result["milestone_summaries"]["Seller"][1]["turn_number"] == 14

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_empty_history_stage(self, mock_router):
        """Milestone generation with no history entries at all."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("No history yet", 30)
        mock_router.get_model.return_value = mock_model

        agents = [_make_agent_config("Buyer", "Alice")]
        state = _make_state(
            agents=agents,
            history=[],
            milestone_summaries={"Buyer": []},
            turn_count=0,
        )
        result = await generate_milestones(state)

        assert result["milestone_summaries"]["Buyer"][0]["turn_number"] == 0
        # Prompt should contain "(No history yet)"
        prompt_text = mock_model.ainvoke.call_args.args[0][0].content
        assert "(No history yet)" in prompt_text

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_multi_agent_four_roles(self, mock_router):
        """Milestone generation with 4 agents: 2 negotiators + regulator + observer."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("Role summary", 50)
        mock_router.get_model.return_value = mock_model

        agents = [
            _make_agent_config("Buyer", "Alice", "negotiator"),
            _make_agent_config("Seller", "Bob", "negotiator"),
            _make_agent_config("Regulator", "Carol", "regulator"),
            _make_agent_config("Observer", "Dave", "observer"),
        ]
        history = [
            {"role": "Buyer", "turn_number": 1, "content": {"public_message": "Offer"}},
            {"role": "Regulator", "turn_number": 1, "content": {"observation": "Compliant"}},
            {"role": "Seller", "turn_number": 2, "content": {"public_message": "Counter"}},
            {"role": "Observer", "turn_number": 2, "content": {"observation": "Noted"}},
        ]
        state = _make_state(
            agents=agents,
            history=history,
            milestone_summaries={},
            turn_count=4,
        )
        result = await generate_milestones(state)

        # All 4 agents get summaries
        for role in ["Buyer", "Seller", "Regulator", "Observer"]:
            assert role in result["milestone_summaries"]
            assert len(result["milestone_summaries"][role]) == 1
            assert result["milestone_summaries"][role][0]["turn_number"] == 4

    @pytest.mark.asyncio
    @patch("app.orchestrator.milestone_generator.model_router")
    async def test_prompt_reflects_stage_context(self, mock_router):
        """At mid-stage, prompt includes existing milestones as context."""
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = _make_fake_response("Updated", 60)
        mock_router.get_model.return_value = mock_model

        agents = [_make_agent_config("Buyer", "Alice", goals=["Get best deal"])]
        existing = {
            "Buyer": [{"turn_number": 4, "summary": "Buyer started strong at 150k"}],
        }
        history = [
            {"role": "Buyer", "turn_number": i, "content": {"public_message": f"Turn {i}"}}
            for i in range(1, 9)
        ]
        state = _make_state(
            agents=agents,
            history=history,
            milestone_summaries=existing,
            turn_count=8,
        )
        await generate_milestones(state)

        prompt_text = mock_model.ainvoke.call_args.args[0][0].content
        assert "Buyer started strong at 150k" in prompt_text
        assert "As of turn 4" in prompt_text


# ---------------------------------------------------------------------------
# Milestone summary formatting tests
# ---------------------------------------------------------------------------


class TestMilestoneSummaryFormatting:
    """Tests for _format_history and _format_existing_milestones edge cases."""

    def test_format_history_with_observation_content(self):
        """History entry with observation (observer/regulator) is formatted."""
        history = [
            {"role": "Observer", "turn_number": 3, "content": {"observation": "Deal looks fair"}},
        ]
        result = _format_history(history)
        assert "[Turn 3 - Observer]" in result
        assert "Deal looks fair" in result

    def test_format_history_with_non_dict_content(self):
        """History entry with plain string content is handled."""
        history = [
            {"role": "System", "turn_number": 0, "content": "Negotiation started"},
        ]
        result = _format_history(history)
        assert "[Turn 0 - System]" in result
        assert "Negotiation started" in result

    def test_format_history_missing_fields(self):
        """History entry with missing role/turn_number uses defaults."""
        history = [{"content": {"public_message": "Hello"}}]
        result = _format_history(history)
        assert "[Turn ? - unknown]" in result
        assert "Hello" in result

    def test_format_history_dict_content_fallback_to_str(self):
        """Dict content with no recognized keys falls back to str()."""
        history = [
            {"role": "Agent", "turn_number": 1, "content": {"custom_field": "data"}},
        ]
        result = _format_history(history)
        assert "custom_field" in result

    def test_format_existing_milestones_multiple(self):
        """Multiple milestones are formatted in order."""
        milestones = [
            {"turn_number": 4, "summary": "First checkpoint"},
            {"turn_number": 8, "summary": "Second checkpoint"},
            {"turn_number": 12, "summary": "Third checkpoint"},
        ]
        result = _format_existing_milestones(milestones)
        assert "As of turn 4: First checkpoint" in result
        assert "As of turn 8: Second checkpoint" in result
        assert "As of turn 12: Third checkpoint" in result
        # Verify ordering: turn 4 appears before turn 12
        idx_4 = result.index("turn 4")
        idx_12 = result.index("turn 12")
        assert idx_4 < idx_12

    def test_format_existing_milestones_missing_fields(self):
        """Milestones with missing turn_number/summary use defaults."""
        milestones = [{"summary": "No turn"}, {"turn_number": 5}]
        result = _format_existing_milestones(milestones)
        assert "As of turn ?" in result
        assert "No turn" in result
        assert "As of turn 5" in result

    def test_build_prompt_no_goals_no_budget(self):
        """Prompt with agent that has no goals or budget shows no private context."""
        agent = _make_agent_config("Buyer", "Alice")
        state = _make_state(
            agents=[agent],
            history=[],
            milestone_summaries={"Buyer": []},
        )
        prompt = _build_milestone_prompt(agent, state)
        assert "(No private context)" in prompt

    def test_build_prompt_with_multiple_goals(self):
        """Prompt includes all goals separated by semicolons."""
        agent = _make_agent_config(
            "Buyer", "Alice",
            goals=["Minimize cost", "Secure IP rights", "Retain key staff"],
        )
        state = _make_state(agents=[agent], milestone_summaries={"Buyer": []})
        prompt = _build_milestone_prompt(agent, state)
        assert "Minimize cost; Secure IP rights; Retain key staff" in prompt

    def test_build_prompt_inner_thoughts_only_for_matching_role(self):
        """Inner thoughts section only includes entries for the target agent's role."""
        agent = _make_agent_config("Buyer", "Alice")
        history = [
            {"role": "Buyer", "turn_number": 1, "content": {"inner_thought": "My secret plan", "public_message": "Offer"}},
            {"role": "Seller", "turn_number": 1, "content": {"inner_thought": "Seller secret", "public_message": "Counter"}},
        ]
        state = _make_state(
            agents=[agent, _make_agent_config("Seller", "Bob")],
            history=history,
            milestone_summaries={"Buyer": [], "Seller": []},
        )
        prompt = _build_milestone_prompt(agent, state)
        assert "My secret plan" in prompt
        assert "Seller secret" not in prompt
