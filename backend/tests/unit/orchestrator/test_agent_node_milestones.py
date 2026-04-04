"""Unit tests for prompt builder milestone integration (Task 8.3).

Tests:
- Prompt with milestones enabled and milestones present
- Prompt with milestones enabled but no milestones yet
- Prompt with milestones disabled (spec 100 behavior)
- Configurable sliding window size
- Milestone summary formatting
"""

from __future__ import annotations

from typing import Any

from app.orchestrator.agent_node import _build_prompt
from app.orchestrator.outputs import AgentMemory
from app.orchestrator.state import NegotiationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(
    role: str = "Buyer",
    name: str = "Alice",
    agent_type: str = "negotiator",
) -> dict[str, Any]:
    return {
        "role": role,
        "name": name,
        "type": agent_type,
        "model_id": "gemini-3-flash-preview",
        "persona_prompt": f"You are {name}.",
    }


def _turn_label(n: int) -> str:
    """Return the zero-padded turn label used in history entries."""
    return f"turn-{n:03d}"


def _make_history(count: int, roles: list[str] | None = None) -> list[dict[str, Any]]:
    """Generate a list of history entries.

    Uses zero-padded turn numbers (e.g. 'turn-001') to avoid substring
    collisions like 'turn 1' matching 'turn 10'.
    """
    if roles is None:
        roles = ["Buyer", "Seller"]
    entries = []
    for i in range(count):
        r = roles[i % len(roles)]
        label = _turn_label(i + 1)
        entries.append({
            "role": r,
            "agent_type": "negotiator",
            "turn_number": i + 1,
            "content": {
                "inner_thought": f"Thought {label}",
                "public_message": f"Message from {label}",
                "proposed_price": 100000.0 + i * 1000,
            },
        })
    return entries


def _make_state(
    history_count: int = 10,
    structured_memory_enabled: bool = True,
    milestone_summaries_enabled: bool = False,
    milestones: dict[str, list[dict[str, Any]]] | None = None,
    sliding_window_size: int = 3,
    milestone_interval: int = 4,
) -> NegotiationState:
    role = "Buyer"
    other = "Seller"
    history = _make_history(history_count, [role, other])

    return NegotiationState(
        session_id="s",
        scenario_id="s",
        turn_count=history_count,
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
                _make_agent_config(role),
                _make_agent_config(other, "Bob"),
            ],
            "negotiation_params": {"max_turns": 100},
        },
        turn_order=[role, other],
        turn_order_index=0,
        agent_states={
            role: {"role": role, "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
            other: {"role": other, "name": "Bob", "agent_type": "negotiator", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
        },
        active_toggles=[],
        total_tokens_used=0,
        stall_diagnosis=None,
        custom_prompts={},
        model_overrides={},
        structured_memory_enabled=structured_memory_enabled,
        structured_memory_roles=[role, other] if structured_memory_enabled else [],
        agent_memories={role: AgentMemory().model_dump(), other: AgentMemory().model_dump()} if structured_memory_enabled else {},
        milestone_summaries_enabled=milestone_summaries_enabled,
        milestone_summaries=milestones or {},
        sliding_window_size=sliding_window_size,
        milestone_interval=milestone_interval,
    )


def _msg(n: int) -> str:
    """Return the expected message string for turn n."""
    return f"Message from {_turn_label(n)}"


# ===========================================================================
# Tests
# ===========================================================================


class TestPromptWithMilestonesPresent:
    """Milestones enabled + milestones exist: full history excluded,
    milestones included, sliding window included.

    Requirements: 4.1, 4.2, 4.5
    """

    def test_full_history_excluded(self):
        """Early history entries should NOT appear in the prompt."""
        milestones = {
            "Buyer": [
                {"turn_number": 4, "summary": "After 4 turns, positions established."},
            ],
        }
        state = _make_state(
            history_count=12,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
            sliding_window_size=3,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        # Turn 1 message should NOT be in the prompt
        assert _msg(1) not in user
        # Turn 5 message should NOT be in the prompt (outside window)
        assert _msg(5) not in user

    def test_milestones_included(self):
        """Milestone summaries should appear in the prompt."""
        milestones = {
            "Buyer": [
                {"turn_number": 4, "summary": "Positions established after 4 turns."},
                {"turn_number": 8, "summary": "Significant progress on salary."},
            ],
        }
        state = _make_state(
            history_count=12,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        assert "Strategic summary as of turn 4:" in user
        assert "Positions established after 4 turns." in user
        assert "Strategic summary as of turn 8:" in user
        assert "Significant progress on salary." in user

    def test_sliding_window_included(self):
        """Last N entries should appear in the prompt."""
        milestones = {
            "Buyer": [{"turn_number": 4, "summary": "Summary."}],
        }
        state = _make_state(
            history_count=12,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
            sliding_window_size=3,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        # Last 3 entries (turns 10, 11, 12) should be present
        assert _msg(10) in user
        assert _msg(11) in user
        assert _msg(12) in user

    def test_milestone_section_between_memory_and_window(self):
        """Milestones should appear after structured memory and before sliding window.

        Requirements: 4.5
        """
        milestones = {
            "Buyer": [{"turn_number": 4, "summary": "Summary at turn 4."}],
        }
        mem = AgentMemory()
        mem.my_offers = [100000.0, 110000.0]
        state = _make_state(
            history_count=12,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
        )
        state["agent_memories"]["Buyer"] = mem.model_dump()
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        mem_pos = user.find("Structured memory:")
        milestone_pos = user.find("Milestone summaries:")
        window_pos = user.find("Recent negotiation messages:")

        assert mem_pos >= 0, "Structured memory section not found"
        assert milestone_pos >= 0, "Milestone summaries section not found"
        assert window_pos >= 0, "Recent negotiation messages section not found"
        assert mem_pos < milestone_pos < window_pos, (
            f"Ordering wrong: memory@{mem_pos}, milestones@{milestone_pos}, window@{window_pos}"
        )


class TestPromptWithMilestonesEnabledNoMilestones:
    """Milestones enabled but no milestones yet: full history included.

    Requirements: 4.3
    """

    def test_full_history_as_sliding_window(self):
        """When no milestones exist yet, behave like spec 100."""
        state = _make_state(
            history_count=10,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones={"Buyer": []},
            sliding_window_size=3,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        # Should include the sliding window (last 3)
        assert _msg(8) in user
        assert _msg(9) in user
        assert _msg(10) in user
        # Should NOT include milestone summaries section
        assert "Milestone summaries:" not in user

    def test_no_milestone_section_when_empty(self):
        """No milestone summaries section should appear."""
        state = _make_state(
            history_count=5,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones={},
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        assert "Milestone summaries:" not in user
        assert "Strategic summary" not in user


class TestPromptWithMilestonesDisabled:
    """Milestones disabled: spec 100 behavior unchanged.

    Requirements: 8.3, 9.1
    """

    def test_spec100_behavior_structured_memory(self):
        """With structured memory on but milestones off, use sliding window."""
        state = _make_state(
            history_count=10,
            structured_memory_enabled=True,
            milestone_summaries_enabled=False,
            sliding_window_size=3,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        # Sliding window: last 3 entries
        assert "Recent negotiation messages:" in user
        assert _msg(8) in user
        assert _msg(9) in user
        assert _msg(10) in user
        # Early history excluded
        assert _msg(1) not in user
        # No milestone section
        assert "Milestone summaries:" not in user

    def test_spec100_behavior_no_structured_memory(self):
        """With both structured memory and milestones off, full history mode."""
        state = _make_state(
            history_count=5,
            structured_memory_enabled=False,
            milestone_summaries_enabled=False,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        # Full history mode
        assert "Negotiation history so far:" in user
        assert _msg(1) in user
        assert _msg(5) in user
        assert "Milestone summaries:" not in user


class TestConfigurableSlidingWindowSize:
    """Configurable sliding window size.

    Requirements: 4.4
    """

    def test_window_size_5(self):
        """sliding_window_size=5 includes last 5 entries."""
        milestones = {
            "Buyer": [{"turn_number": 4, "summary": "Summary."}],
        }
        state = _make_state(
            history_count=12,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
            sliding_window_size=5,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        # Last 5 entries (turns 8-12) should be present
        assert _msg(8) in user
        assert _msg(9) in user
        assert _msg(10) in user
        assert _msg(11) in user
        assert _msg(12) in user
        # Turn 7 should NOT be present
        assert _msg(7) not in user

    def test_window_size_1(self):
        """sliding_window_size=1 includes only the last entry."""
        milestones = {
            "Buyer": [{"turn_number": 4, "summary": "Summary."}],
        }
        state = _make_state(
            history_count=10,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
            sliding_window_size=1,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        # Only last entry
        assert _msg(10) in user
        assert _msg(9) not in user

    def test_default_window_size_when_absent(self):
        """When sliding_window_size is absent from state, default to 3."""
        milestones = {
            "Buyer": [{"turn_number": 4, "summary": "Summary."}],
        }
        state = _make_state(
            history_count=10,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
            sliding_window_size=3,
        )
        # Remove the key to simulate absent field
        del state["sliding_window_size"]  # type: ignore[misc]
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        # Default 3: last 3 entries
        assert _msg(8) in user
        assert _msg(9) in user
        assert _msg(10) in user
        assert _msg(7) not in user

    def test_window_size_without_milestones(self):
        """Configurable window size works even without milestones (spec 100 path)."""
        state = _make_state(
            history_count=10,
            structured_memory_enabled=True,
            milestone_summaries_enabled=False,
            sliding_window_size=5,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        # Last 5 entries should be present
        assert _msg(6) in user
        assert _msg(10) in user
        # Turn 5 should NOT be present
        assert _msg(5) not in user


class TestMilestoneSummaryFormatting:
    """Milestone summary formatting.

    Requirements: 4.5
    """

    def test_format_strategic_summary_label(self):
        """Each milestone should be formatted as 'Strategic summary as of turn N:'."""
        milestones = {
            "Buyer": [
                {"turn_number": 4, "summary": "First milestone content."},
                {"turn_number": 8, "summary": "Second milestone content."},
                {"turn_number": 12, "summary": "Third milestone content."},
            ],
        }
        state = _make_state(
            history_count=15,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        assert "Strategic summary as of turn 4: First milestone content." in user
        assert "Strategic summary as of turn 8: Second milestone content." in user
        assert "Strategic summary as of turn 12: Third milestone content." in user

    def test_chronological_order(self):
        """Milestones should appear in chronological order."""
        milestones = {
            "Buyer": [
                {"turn_number": 4, "summary": "First."},
                {"turn_number": 8, "summary": "Second."},
            ],
        }
        state = _make_state(
            history_count=12,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        pos_first = user.find("Strategic summary as of turn 4:")
        pos_second = user.find("Strategic summary as of turn 8:")
        assert pos_first < pos_second, "Milestones should be in chronological order"

    def test_milestone_section_header(self):
        """The milestone section should have a 'Milestone summaries:' header."""
        milestones = {
            "Buyer": [{"turn_number": 4, "summary": "Content."}],
        }
        state = _make_state(
            history_count=8,
            structured_memory_enabled=True,
            milestone_summaries_enabled=True,
            milestones=milestones,
        )
        config = _make_agent_config()
        _, user = _build_prompt(config, state)

        assert "Milestone summaries:" in user
