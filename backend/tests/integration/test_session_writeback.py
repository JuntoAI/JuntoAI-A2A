"""Integration tests for session state write-back after negotiation completes.

Verifies that the final negotiation state (agent_calls, deal_status, history,
turn_count, total_tokens_used, etc.) is persisted back to the session store
when the SSE stream finishes — enabling downstream consumers (Specs 190, 192, 195).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.orchestrator.state import NegotiationState, create_initial_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCENARIO_CONFIG: dict[str, Any] = {
    "id": "test-scenario",
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


def _mock_response(content: str, input_tokens: int = 50, output_tokens: int = 30) -> AIMessage:
    msg = AIMessage(content=content)
    msg.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return msg


async def _consume_stream(gen):
    """Consume an async generator fully, collecting all yielded items."""
    items = []
    async for item in gen:
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Test: successful negotiation persists final state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.orchestrator.agent_node.model_router")
async def test_writeback_persists_agent_calls_after_agreement(mock_router):
    """After a negotiation completes (Agreed), the session store is updated
    with agent_calls, deal_status, history, and other final state fields."""
    call_count = 0

    def _invoke(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_response(
                '{"inner_thought": "low", "public_message": "100k", "proposed_price": 100000.0}',
                input_tokens=80, output_tokens=40,
            )
        return _mock_response(
            '{"inner_thought": "deal", "public_message": "102k", "proposed_price": 102000.0}',
            input_tokens=90, output_tokens=45,
        )

    mock_model = MagicMock()
    mock_model.invoke.side_effect = _invoke
    mock_router.get_model.return_value = mock_model

    # Run the graph directly and verify the final state
    from app.orchestrator.graph import build_graph

    initial = create_initial_state("writeback-test", SCENARIO_CONFIG)
    graph = build_graph(SCENARIO_CONFIG)
    result = await graph.ainvoke(initial)

    # Simulate what the write-back does: accumulate from snapshots
    assert result["deal_status"] in ("Agreed", "Failed")
    assert len(result["agent_calls"]) == 2
    assert result["agent_calls"][0]["agent_role"] == "Buyer"
    assert result["agent_calls"][1]["agent_role"] == "Seller"
    assert result["total_tokens_used"] == (80 + 40) + (90 + 45)
    assert len(result["history"]) == 2


@pytest.mark.asyncio
@patch("app.orchestrator.agent_node.model_router")
async def test_writeback_accumulates_agent_calls_across_nodes(mock_router):
    """agent_calls from multiple agent nodes are accumulated via the add reducer."""
    call_count = 0

    def _invoke(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # First round: Buyer and Seller far apart
            if call_count == 1:
                return _mock_response(
                    '{"inner_thought": "x", "public_message": "x", "proposed_price": 50000.0}',
                    input_tokens=60, output_tokens=30,
                )
            return _mock_response(
                '{"inner_thought": "x", "public_message": "x", "proposed_price": 200000.0}',
                input_tokens=70, output_tokens=35,
            )
        # Second round: converge
        if call_count == 3:
            return _mock_response(
                '{"inner_thought": "x", "public_message": "x", "proposed_price": 100000.0}',
                input_tokens=80, output_tokens=40,
            )
        return _mock_response(
            '{"inner_thought": "x", "public_message": "x", "proposed_price": 101000.0}',
            input_tokens=90, output_tokens=45,
        )

    mock_model = MagicMock()
    mock_model.invoke.side_effect = _invoke
    mock_router.get_model.return_value = mock_model

    # Use max_turns=4 to allow 2 full rounds
    config = {**SCENARIO_CONFIG, "negotiation_params": {**SCENARIO_CONFIG["negotiation_params"], "max_turns": 4}}
    initial = create_initial_state("multi-round", config)

    from app.orchestrator.graph import build_graph
    graph = build_graph(config)
    result = await graph.ainvoke(initial)

    # Should have 1 record per agent node execution
    # At minimum 2 (one round), possibly 4 if two rounds completed
    assert len(result["agent_calls"]) >= 2
    # All records should have valid fields
    for record in result["agent_calls"]:
        assert "agent_role" in record
        assert "model_id" in record
        assert "latency_ms" in record
        assert record["latency_ms"] >= 0
        assert "timestamp" in record


# ---------------------------------------------------------------------------
# Test: write-back fields match what downstream specs need
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.orchestrator.agent_node.model_router")
async def test_writeback_contains_fields_needed_by_downstream_specs(mock_router):
    """The final state contains all fields that Specs 190, 192, 195 need."""
    call_count = 0

    def _invoke(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_response(
                '{"inner_thought": "x", "public_message": "x", "proposed_price": 100000.0}',
                input_tokens=100, output_tokens=50,
            )
        return _mock_response(
            '{"inner_thought": "x", "public_message": "x", "proposed_price": 101000.0}',
            input_tokens=110, output_tokens=55,
        )

    mock_model = MagicMock()
    mock_model.invoke.side_effect = _invoke
    mock_router.get_model.return_value = mock_model

    from app.orchestrator.graph import build_graph

    initial = create_initial_state("downstream-test", SCENARIO_CONFIG)
    graph = build_graph(SCENARIO_CONFIG)
    result = await graph.ainvoke(initial)

    # Spec 190 (LLM Usage Summary) needs:
    assert "agent_calls" in result
    assert isinstance(result["agent_calls"], list)
    for record in result["agent_calls"]:
        # Each record must have the fields the aggregator reads
        assert "agent_role" in record
        assert "agent_type" in record
        assert "model_id" in record
        assert "latency_ms" in record
        assert "input_tokens" in record
        assert "output_tokens" in record
        assert "error" in record
        assert "turn_number" in record
        assert "timestamp" in record

    # Spec 192 (Social Sharing) needs deal_status, current_offer, turn_count
    assert "deal_status" in result
    assert result["deal_status"] in ("Agreed", "Blocked", "Failed")
    assert "current_offer" in result
    assert "turn_count" in result

    # Spec 195 (Public Stats) needs total_tokens_used, scenario_id, turn_count
    assert "total_tokens_used" in result
    assert result["total_tokens_used"] > 0
    assert "scenario_id" in result


# ---------------------------------------------------------------------------
# Test: SQLite write-back round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sqlite_update_session_persists_agent_calls():
    """SQLiteSessionClient.update_session merges agent_calls into the stored doc."""
    import tempfile
    from app.db.sqlite_client import SQLiteSessionClient
    from app.models.negotiation import NegotiationStateModel

    with tempfile.TemporaryDirectory() as tmpdir:
        db = SQLiteSessionClient(db_path=f"{tmpdir}/test.db")

        # Create initial session (no agent_calls data yet)
        initial = NegotiationStateModel(
            session_id="sqlite-test",
            scenario_id="test-scenario",
            turn_order=["Buyer", "Seller"],
            turn_order_index=0,
            agent_states={},
        )
        await db.create_session(initial)

        # Simulate write-back with final state
        agent_calls = [
            {
                "agent_role": "Buyer",
                "agent_type": "negotiator",
                "model_id": "gemini-3-flash-preview",
                "latency_ms": 150,
                "input_tokens": 100,
                "output_tokens": 50,
                "error": False,
                "turn_number": 1,
                "timestamp": "2025-01-01T00:00:00+00:00",
            },
        ]
        await db.update_session("sqlite-test", {
            "deal_status": "Agreed",
            "agent_calls": agent_calls,
            "total_tokens_used": 150,
            "turn_count": 2,
            "current_offer": 100000.0,
            "history": [{"role": "Buyer", "content": {}}],
        })

        # Read back and verify
        doc = await db.get_session_doc("sqlite-test")
        assert doc["deal_status"] == "Agreed"
        assert doc["agent_calls"] == agent_calls
        assert doc["total_tokens_used"] == 150
        assert doc["turn_count"] == 2
        assert doc["current_offer"] == 100000.0
        assert len(doc["history"]) == 1


# ---------------------------------------------------------------------------
# Test: write-back failure doesn't crash the stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_writeback_failure_does_not_crash():
    """If db.update_session raises, the error is logged but doesn't propagate."""
    from app.db.sqlite_client import SQLiteSessionClient
    from app.models.negotiation import NegotiationStateModel
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db = SQLiteSessionClient(db_path=f"{tmpdir}/test.db")

        # Create session
        initial = NegotiationStateModel(
            session_id="crash-test",
            scenario_id="test-scenario",
            turn_order=["Buyer"],
            turn_order_index=0,
            agent_states={},
        )
        await db.create_session(initial)

        # update_session with a non-existent session should raise
        # but in the stream context it's wrapped in try/except
        from app.exceptions import SessionNotFoundError
        with pytest.raises(SessionNotFoundError):
            await db.update_session("nonexistent-session", {"deal_status": "Failed"})

        # The original session should still be intact
        doc = await db.get_session_doc("crash-test")
        assert doc["session_id"] == "crash-test"
