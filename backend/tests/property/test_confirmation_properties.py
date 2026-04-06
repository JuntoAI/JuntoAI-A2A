"""Property-based tests for the confirmation round logic.

Feature: negotiation-evaluator
Uses Hypothesis to verify correctness properties P1, P2, P3, P4, P9.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.graph import _dispatcher, _resolve_confirmation
from app.orchestrator.confirmation_node import _build_confirmation_messages
from app.orchestrator.state import NegotiationState
from app.orchestrator.stall_detector import StallDiagnosis

# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=1,
    max_size=30,
)

_role_name = st.text(
    alphabet=st.characters(whitelist_categories=("L",)),
    min_size=2,
    max_size=15,
)

_positive_price = st.floats(min_value=100.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)

_threshold = st.floats(min_value=100.0, max_value=50_000.0, allow_nan=False, allow_infinity=False)


def _make_agent_config(
    role: str,
    agent_type: str = "negotiator",
    model_id: str = "gemini-3-flash-preview",
) -> dict[str, Any]:
    return {
        "role": role,
        "name": role,
        "type": agent_type,
        "model_id": model_id,
        "persona_prompt": f"You are {role}.",
        "goals": [f"Goal for {role}"],
    }


def _make_full_state(
    agent_configs: list[dict[str, Any]],
    deal_status: str = "Negotiating",
    turn_count: int = 3,
    max_turns: int = 15,
    current_offer: float = 50000.0,
    agreement_threshold: float = 5000.0,
    history: list[dict[str, Any]] | None = None,
    confirmation_pending: list[str] | None = None,
    agent_states: dict[str, dict[str, Any]] | None = None,
) -> NegotiationState:
    """Build a full NegotiationState for testing dispatcher/resolve."""
    if agent_states is None:
        agent_states = {}
        for cfg in agent_configs:
            agent_states[cfg["role"]] = {
                "role": cfg["role"],
                "name": cfg["name"],
                "agent_type": cfg.get("type", "negotiator"),
                "model_id": cfg["model_id"],
                "last_proposed_price": 0.0,
                "warning_count": 0,
            }

    turn_order = [cfg["role"] for cfg in agent_configs]

    return NegotiationState(
        session_id="test-sess",
        scenario_id="test-scenario",
        turn_count=turn_count,
        max_turns=max_turns,
        current_speaker=turn_order[0] if turn_order else "",
        deal_status=deal_status,
        current_offer=current_offer,
        history=history or [],
        hidden_context={},
        warning_count=0,
        agreement_threshold=agreement_threshold,
        scenario_config={
            "id": "test-scenario",
            "agents": agent_configs,
            "negotiation_params": {
                "max_turns": max_turns,
                "agreement_threshold": agreement_threshold,
            },
        },
        turn_order=turn_order,
        turn_order_index=0,
        agent_states=agent_states,
        active_toggles=[],
        total_tokens_used=0,
        stall_diagnosis=None,
        custom_prompts={},
        model_overrides={},
        structured_memory_enabled=False,
        structured_memory_roles=[],
        agent_memories={},
        milestone_summaries_enabled=False,
        milestone_summaries={},
        sliding_window_size=3,
        milestone_interval=4,
        no_memory_roles=[],
        agent_calls=[],
        closure_status="",
        confirmation_pending=confirmation_pending or [],
    )



# ---------------------------------------------------------------------------
# Composite strategies
# ---------------------------------------------------------------------------


@st.composite
def converged_negotiator_state(draw):
    """Generate a state where negotiator prices have converged within threshold.

    Returns (state, threshold) where all negotiator prices are within threshold.
    """
    n_negotiators = draw(st.integers(min_value=2, max_value=5))
    base_price = draw(st.floats(min_value=1000.0, max_value=500_000.0, allow_nan=False, allow_infinity=False))
    threshold = draw(st.floats(min_value=500.0, max_value=10_000.0, allow_nan=False, allow_infinity=False))

    # Generate prices within threshold of each other
    prices = []
    for _ in range(n_negotiators):
        offset = draw(st.floats(min_value=0.0, max_value=threshold * 0.5, allow_nan=False, allow_infinity=False))
        prices.append(base_price + offset)

    roles = [f"Agent_{i}" for i in range(n_negotiators)]
    agent_configs = [_make_agent_config(role, "negotiator") for role in roles]

    agent_states = {}
    for role, price in zip(roles, prices):
        agent_states[role] = {
            "role": role,
            "name": role,
            "agent_type": "negotiator",
            "model_id": "gemini-3-flash-preview",
            "last_proposed_price": price,
            "warning_count": 0,
        }

    state = _make_full_state(
        agent_configs=agent_configs,
        deal_status="Negotiating",
        turn_count=draw(st.integers(min_value=1, max_value=10)),
        max_turns=15,
        current_offer=base_price,
        agreement_threshold=threshold,
        agent_states=agent_states,
    )
    return state


@st.composite
def mixed_agent_scenario(draw):
    """Generate a scenario config with mixed agent types (2-5 agents)."""
    n_negotiators = draw(st.integers(min_value=2, max_value=3))
    n_regulators = draw(st.integers(min_value=0, max_value=2))
    n_observers = draw(st.integers(min_value=0, max_value=1))

    configs = []
    for i in range(n_negotiators):
        configs.append(_make_agent_config(f"Negotiator_{i}", "negotiator"))
    for i in range(n_regulators):
        configs.append(_make_agent_config(f"Regulator_{i}", "regulator"))
    for i in range(n_observers):
        configs.append(_make_agent_config(f"Observer_{i}", "observer"))

    expected_negotiator_roles = [f"Negotiator_{i}" for i in range(n_negotiators)]
    return configs, expected_negotiator_roles


@st.composite
def confirmation_history_entries(draw):
    """Generate confirmation history entries with all accept/reject/condition combos.

    Returns (entries, turn_count) where entries all have matching turn_number.
    """
    n_negotiators = draw(st.integers(min_value=2, max_value=4))
    turn_count = draw(st.integers(min_value=1, max_value=10))

    entries = []
    for i in range(n_negotiators):
        accept = draw(st.booleans())
        has_conditions = draw(st.booleans()) if accept else False
        conditions = (
            draw(st.lists(_safe_text, min_size=1, max_size=3))
            if has_conditions
            else []
        )
        entries.append({
            "role": f"Agent_{i}",
            "agent_type": "confirmation",
            "turn_number": turn_count,
            "content": {
                "accept": accept,
                "final_statement": f"Statement from Agent_{i}",
                "conditions": conditions,
            },
        })
    return entries, turn_count


# ===========================================================================
# Property 1: Convergence triggers Confirming, never Agreed directly
# Feature: negotiation-evaluator
# **Validates: Requirements 1.1, 1.2**
# ===========================================================================


@settings(max_examples=100)
@given(state=converged_negotiator_state())
@pytest.mark.asyncio
async def test_convergence_triggers_confirming_not_agreed(state: NegotiationState):
    """When negotiator prices converge within threshold, dispatcher sets
    deal_status to 'Confirming', never directly to 'Agreed'.

    **Validates: Requirements 1.1, 1.2**
    """
    # Mock stall detector to not interfere
    with patch("app.orchestrator.graph.detect_stall") as mock_stall:
        mock_stall.return_value = StallDiagnosis(is_stalled=False)

        result = await _dispatcher(state)

    # The dispatcher should transition to Confirming
    assert result.get("deal_status") == "Confirming", (
        f"Expected 'Confirming' but got {result.get('deal_status')!r}"
    )
    assert result.get("deal_status") != "Agreed", (
        "Dispatcher must never set 'Agreed' directly on convergence"
    )
    assert "confirmation_pending" in result
    assert len(result["confirmation_pending"]) >= 2


# ===========================================================================
# Property 2: Confirmation pending contains exactly negotiator roles
# Feature: negotiation-evaluator
# **Validates: Requirements 1.3, 12.1**
# ===========================================================================


@settings(max_examples=100)
@given(data=mixed_agent_scenario())
@pytest.mark.asyncio
async def test_confirmation_pending_contains_only_negotiator_roles(
    data: tuple[list[dict], list[str]],
):
    """When dispatcher transitions to Confirming, confirmation_pending
    contains exactly the negotiator roles and no regulators/observers.

    **Validates: Requirements 1.3, 12.1**
    """
    agent_configs, expected_negotiator_roles = data

    # Set up converged prices for all negotiators
    agent_states = {}
    for cfg in agent_configs:
        agent_states[cfg["role"]] = {
            "role": cfg["role"],
            "name": cfg["name"],
            "agent_type": cfg["type"],
            "model_id": cfg["model_id"],
            "last_proposed_price": 50000.0 if cfg["type"] == "negotiator" else 0.0,
            "warning_count": 0,
        }

    state = _make_full_state(
        agent_configs=agent_configs,
        deal_status="Negotiating",
        turn_count=3,
        max_turns=15,
        current_offer=50000.0,
        agreement_threshold=1000.0,
        agent_states=agent_states,
    )

    with patch("app.orchestrator.graph.detect_stall") as mock_stall:
        mock_stall.return_value = StallDiagnosis(is_stalled=False)
        result = await _dispatcher(state)

    assert result.get("deal_status") == "Confirming"
    pending = result.get("confirmation_pending", [])
    assert sorted(pending) == sorted(expected_negotiator_roles), (
        f"Expected {sorted(expected_negotiator_roles)} but got {sorted(pending)}"
    )


# ===========================================================================
# Property 3: Confirmation resolution is deterministic and correct
# Feature: negotiation-evaluator
# **Validates: Requirements 2.1, 2.2, 2.3**
# ===========================================================================


@settings(max_examples=100)
@given(data=confirmation_history_entries())
def test_confirmation_resolution_deterministic_and_correct(
    data: tuple[list[dict], int],
):
    """For any set of confirmation entries, _resolve_confirmation produces
    exactly one of three mutually exclusive outcomes.

    **Validates: Requirements 2.1, 2.2, 2.3**
    """
    entries, turn_count = data

    agent_configs = [
        _make_agent_config(e["role"], "negotiator") for e in entries
    ]

    state = _make_full_state(
        agent_configs=agent_configs,
        deal_status="Confirming",
        turn_count=turn_count,
        history=entries,
        confirmation_pending=[],
    )

    result = _resolve_confirmation(state)

    all_accepted = all(e["content"]["accept"] for e in entries)

    # Two outcomes: all accepted → Agreed, any rejected → Negotiating
    if all_accepted:
        assert result["deal_status"] == "Agreed"
        assert result["closure_status"] == "Confirmed"
    else:
        assert result["deal_status"] == "Negotiating"
        assert result["closure_status"] == "Rejected"

    # All outcomes clear confirmation_pending
    assert result["confirmation_pending"] == []



# ===========================================================================
# Property 4: Confirmation node appends correct history entries
# Feature: negotiation-evaluator
# **Validates: Requirements 2.4, 3.3**
# ===========================================================================


@st.composite
def confirmation_node_scenario(draw):
    """Generate a scenario for testing confirmation_node history entries."""
    role = draw(_role_name)
    turn_count = draw(st.integers(min_value=0, max_value=20))
    accept = draw(st.booleans())
    conditions = draw(st.lists(_safe_text, min_size=0, max_size=3))

    agent_config = _make_agent_config(role, "negotiator")
    return role, turn_count, accept, conditions, agent_config


@settings(max_examples=100)
@given(scenario=confirmation_node_scenario())
def test_confirmation_node_appends_correct_history_entries(
    scenario: tuple[str, int, bool, list[str], dict],
):
    """After confirmation_node processes a role, the history entry has
    agent_type == 'confirmation', the correct role, and turn_number == turn_count.

    **Validates: Requirements 2.4, 3.3**
    """
    role, turn_count, accept, conditions, agent_config = scenario

    agent_configs = [agent_config]
    state = _make_full_state(
        agent_configs=agent_configs,
        deal_status="Confirming",
        turn_count=turn_count,
        confirmation_pending=[role],
    )

    # Mock model_router and LLM response
    import json
    from unittest.mock import patch, MagicMock
    from langchain_core.messages import AIMessage

    response_json = json.dumps({
        "accept": accept,
        "final_statement": f"Statement from {role}",
        "conditions": conditions,
    })

    mock_model = MagicMock()
    mock_model.invoke.return_value = AIMessage(content=response_json)

    with patch("app.orchestrator.confirmation_node.model_router") as mock_router:
        mock_router.get_model.return_value = mock_model

        from app.orchestrator.confirmation_node import confirmation_node
        result = confirmation_node(state)

    assert "history" in result
    assert len(result["history"]) == 1

    entry = result["history"][0]
    assert entry["agent_type"] == "confirmation"
    assert entry["role"] == role
    assert entry["turn_number"] == turn_count
    assert entry["content"]["accept"] == accept
    assert entry["content"]["conditions"] == conditions


# ===========================================================================
# Property 9: Confirmation prompt contains converged terms
# Feature: negotiation-evaluator
# **Validates: Requirements 1.4**
# ===========================================================================


@st.composite
def confirmation_prompt_scenario(draw):
    """Generate a scenario for testing confirmation prompt content."""
    role = draw(_role_name)
    current_offer = draw(st.floats(min_value=100.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False))
    turn_count = draw(st.integers(min_value=1, max_value=20))

    # Generate at least one history entry with a public_message
    public_msg = draw(_safe_text)
    history = [
        {
            "role": f"Other_{draw(st.integers(min_value=0, max_value=5))}",
            "agent_type": "negotiator",
            "turn_number": turn_count - 1,
            "content": {
                "public_message": public_msg,
                "proposed_price": current_offer,
                "inner_thought": "thinking",
            },
        }
    ]

    agent_config = _make_agent_config(role, "negotiator")
    return role, current_offer, turn_count, history, public_msg, agent_config


@settings(max_examples=100)
@given(scenario=confirmation_prompt_scenario())
def test_confirmation_prompt_contains_converged_terms(
    scenario: tuple[str, float, int, list[dict], str, dict],
):
    """The confirmation prompt must include current_offer, turn_count,
    and at least one public_message from history.

    **Validates: Requirements 1.4**
    """
    role, current_offer, turn_count, history, public_msg, agent_config = scenario

    state = _make_full_state(
        agent_configs=[agent_config],
        deal_status="Confirming",
        turn_count=turn_count,
        current_offer=current_offer,
        history=history,
        confirmation_pending=[role],
    )

    messages = _build_confirmation_messages(agent_config, state)

    # Combine all message content for checking
    all_content = " ".join(
        msg.content if isinstance(msg.content, str) else str(msg.content)
        for msg in messages
    )

    # Must contain current_offer value
    assert str(current_offer) in all_content, (
        f"Prompt must contain current_offer={current_offer}"
    )

    # Must contain turn_count
    assert str(turn_count) in all_content, (
        f"Prompt must contain turn_count={turn_count}"
    )

    # Must contain at least one public_message from history
    assert public_msg in all_content, (
        f"Prompt must contain public_message={public_msg!r}"
    )
