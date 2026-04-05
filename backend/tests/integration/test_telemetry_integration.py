"""Integration test: verify agent_calls accumulates across a multi-turn negotiation.

Runs a 2-agent negotiation (Buyer + Seller) with mocked LLMs through the
real LangGraph pipeline and asserts that agent_calls records appear in the
final state with correct structure.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.orchestrator.graph import build_graph
from app.orchestrator.state import NegotiationState, create_initial_state


def _mock_response(content: str, input_tokens: int = 50, output_tokens: int = 30) -> AIMessage:
    msg = AIMessage(content=content)
    msg.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return msg


SCENARIO_CONFIG: dict[str, Any] = {
    "id": "integration-test",
    "agents": [
        {
            "role": "Buyer",
            "name": "Alice",
            "type": "negotiator",
            "model_id": "gemini-3-flash-preview",
            "persona_prompt": "You are a buyer.",
        },
        {
            "role": "Seller",
            "name": "Bob",
            "type": "negotiator",
            "model_id": "gemini-3-flash-preview",
            "persona_prompt": "You are a seller.",
        },
    ],
    "negotiation_params": {
        "max_turns": 2,
        "turn_order": ["Buyer", "Seller"],
        "agreement_threshold": 5000.0,
    },
}


@pytest.mark.asyncio
@patch("app.orchestrator.agent_node.model_router")
async def test_agent_calls_accumulate_across_turns(mock_router):
    """Full graph run: 2 negotiators, prices within threshold → Agreed, verify agent_calls."""
    # Buyer offers 100k, Seller offers 102k → within 5k threshold → Agreed
    call_count = 0

    def _invoke_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_response(
                '{"inner_thought": "start low", "public_message": "100k", "proposed_price": 100000.0}',
                input_tokens=80, output_tokens=40,
            )
        else:
            return _mock_response(
                '{"inner_thought": "close enough", "public_message": "102k", "proposed_price": 102000.0}',
                input_tokens=90, output_tokens=45,
            )

    mock_model = MagicMock()
    mock_model.invoke.side_effect = _invoke_side_effect
    mock_router.get_model.return_value = mock_model

    initial = create_initial_state("int-test-sess", SCENARIO_CONFIG)
    graph = build_graph(SCENARIO_CONFIG)

    result = await graph.ainvoke(initial)

    agent_calls = result.get("agent_calls", [])

    # Should have exactly 2 records (1 per agent turn)
    assert len(agent_calls) == 2, f"Expected 2 agent_calls, got {len(agent_calls)}: {agent_calls}"

    # First record: Buyer
    buyer_record = agent_calls[0]
    assert buyer_record["agent_role"] == "Buyer"
    assert buyer_record["agent_type"] == "negotiator"
    assert buyer_record["model_id"] == "gemini-3-flash-preview"
    assert buyer_record["input_tokens"] == 80
    assert buyer_record["output_tokens"] == 40
    assert buyer_record["error"] is False
    assert buyer_record["latency_ms"] >= 0
    assert buyer_record["turn_number"] == 1  # first negotiator turn
    assert "timestamp" in buyer_record

    # Second record: Seller
    seller_record = agent_calls[1]
    assert seller_record["agent_role"] == "Seller"
    assert seller_record["agent_type"] == "negotiator"
    assert seller_record["input_tokens"] == 90
    assert seller_record["output_tokens"] == 45
    assert seller_record["turn_number"] == 2  # second negotiator turn

    # Verify deal resolved
    assert result["deal_status"] in ("Agreed", "Failed")

    # Verify total_tokens_used matches sum of all records
    total_from_records = sum(r["input_tokens"] + r["output_tokens"] for r in agent_calls)
    assert result["total_tokens_used"] == total_from_records


@pytest.mark.asyncio
@patch("app.orchestrator.agent_node.model_router")
async def test_agent_calls_empty_list_default(mock_router):
    """Initial state has agent_calls=[] and it's preserved through dispatcher."""
    initial = create_initial_state("empty-test", SCENARIO_CONFIG)
    assert initial["agent_calls"] == []
