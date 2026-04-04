"""Property-based tests for agent node milestone integration.

P4: Prompt size is bounded when milestones exist
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.agent_node import _build_prompt
from app.orchestrator.outputs import AgentMemory
from app.orchestrator.state import NegotiationState


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_role = st.text(min_size=1, max_size=10, alphabet=st.characters(categories=("L",)))


def _make_history_entry(role: str, turn: int) -> dict[str, Any]:
    """Create a realistic history entry.

    Uses zero-padded turn labels to avoid substring collisions.
    """
    label = f"turn-{turn:03d}"
    return {
        "role": role,
        "agent_type": "negotiator",
        "turn_number": turn,
        "content": {
            "inner_thought": f"Thinking about {label}",
            "public_message": f"I propose terms for {label}",
            "proposed_price": 100000.0 + turn * 1000,
        },
    }


def _make_milestone(turn: int) -> dict[str, Any]:
    return {
        "turn_number": turn,
        "summary": f"Summary of negotiation progress as of turn {turn}. Key positions established.",
    }


@st.composite
def st_state_with_milestones_varying_history(
    draw: st.DrawFn,
) -> tuple[dict[str, Any], NegotiationState, int]:
    """Generate states with varying history lengths but fixed milestones.

    Returns (agent_config, state, history_length).
    """
    history_len = draw(st.integers(min_value=10, max_value=50))
    sliding_window_size = 3

    role = "Buyer"
    other_role = "Seller"

    agent_config: dict[str, Any] = {
        "role": role,
        "name": "Alice",
        "type": "negotiator",
        "model_id": "gemini-3-flash-preview",
        "persona_prompt": "You are a buyer.",
    }

    # Build history with alternating roles
    history: list[dict[str, Any]] = []
    for i in range(history_len):
        r = role if i % 2 == 0 else other_role
        history.append(_make_history_entry(r, i + 1))

    # Fixed milestones (2 milestones at turns 4 and 8)
    milestones = [_make_milestone(4), _make_milestone(8)]

    state = NegotiationState(
        session_id="s",
        scenario_id="s",
        turn_count=history_len,
        max_turns=100,
        current_speaker=role,
        deal_status="Negotiating",
        current_offer=150000.0,
        history=history,
        hidden_context={},
        warning_count=0,
        agreement_threshold=5000.0,
        scenario_config={
            "id": "test",
            "agents": [
                agent_config,
                {"role": other_role, "name": "Bob", "type": "negotiator", "model_id": "gemini-3-flash-preview"},
            ],
            "negotiation_params": {"max_turns": 100},
        },
        turn_order=[role, other_role],
        turn_order_index=0,
        agent_states={
            role: {"role": role, "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
            other_role: {"role": other_role, "name": "Bob", "agent_type": "negotiator", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
        },
        active_toggles=[],
        total_tokens_used=0,
        stall_diagnosis=None,
        custom_prompts={},
        model_overrides={},
        structured_memory_enabled=True,
        structured_memory_roles=[role, other_role],
        agent_memories={role: AgentMemory().model_dump(), other_role: AgentMemory().model_dump()},
        milestone_summaries_enabled=True,
        milestone_summaries={role: milestones, other_role: milestones},
        sliding_window_size=sliding_window_size,
        milestone_interval=4,
    )
    return agent_config, state, history_len


# ===========================================================================
# P4: Prompt size is bounded when milestones exist
# **Validates: Requirements 8.1, 8.2**
# ===========================================================================


class TestP4PromptTokenBoundedness:
    """When milestones exist, the user message length does not grow with
    history length — only sliding window + milestones are included."""

    @settings(max_examples=50)
    @given(data=st_state_with_milestones_varying_history())
    def test_user_message_bounded_with_milestones(
        self, data: tuple[dict[str, Any], NegotiationState, int],
    ):
        """**Validates: Requirements 8.1, 8.2**

        Generate states with varying history lengths (10-50) but fixed
        milestone summaries. Assert that the user message length does not
        grow with history length when milestones exist.
        """
        agent_config, state, history_len = data
        _, user_message = _build_prompt(agent_config, state)

        # The user message should NOT contain entries from early history
        # (beyond the sliding window). Check that only the last
        # sliding_window_size entries appear.
        sliding_window_size = state.get("sliding_window_size", 3)
        history = state.get("history", [])

        # Entries outside the sliding window should NOT be in the prompt
        if len(history) > sliding_window_size:
            excluded_entry = history[0]
            excluded_msg = excluded_entry["content"]["public_message"]
            assert excluded_msg not in user_message, (
                f"History entry from turn 1 should be excluded when milestones exist, "
                f"but found '{excluded_msg}' in user message"
            )

        # Milestone summaries SHOULD be present
        assert "Strategic summary as of turn 4:" in user_message
        assert "Strategic summary as of turn 8:" in user_message

        # Sliding window entries SHOULD be present
        last_entry = history[-1]
        last_msg = last_entry["content"]["public_message"]
        assert last_msg in user_message, (
            f"Last history entry should be in sliding window, "
            f"but '{last_msg}' not found in user message"
        )

    @settings(max_examples=30)
    @given(data=st_state_with_milestones_varying_history())
    def test_user_message_length_stable(
        self, data: tuple[dict[str, Any], NegotiationState, int],
    ):
        """**Validates: Requirements 8.1, 8.2**

        The user message length should be approximately the same regardless
        of history length when milestones exist. We verify this by checking
        that the message length is bounded by a reasonable constant.
        """
        agent_config, state, history_len = data
        _, user_message = _build_prompt(agent_config, state)

        # With 2 fixed milestones and a sliding window of 3, the user
        # message should be bounded. We use a generous upper bound that
        # accounts for structured memory, milestones, sliding window,
        # and current state info — but NOT proportional to history_len.
        # A 50-entry history with full inclusion would be ~5000+ chars.
        # With milestones, it should stay well under 3000.
        max_expected_length = 3000
        assert len(user_message) < max_expected_length, (
            f"User message length {len(user_message)} exceeds bound "
            f"{max_expected_length} with history_len={history_len}. "
            f"Full history may be leaking into the prompt."
        )
