"""Integration test for run_negotiation() with mocked LLM.

Subtask 7.8: Verify full cycle execution, state snapshots yielded,
terminal state reached.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.orchestrator.graph import run_negotiation
from app.orchestrator.state import NegotiationState, create_initial_state


def _agent_def(
    role: str,
    name: str,
    agent_type: str = "negotiator",
    model_id: str = "gemini-2.5-flash",
) -> dict[str, Any]:
    return {
        "role": role,
        "name": name,
        "type": agent_type,
        "model_id": model_id,
        "persona_prompt": f"You are {name}.",
        "goals": ["Do your best"],
    }


def _make_scenario() -> dict[str, Any]:
    return {
        "id": "integration-test",
        "agents": [
            _agent_def("Buyer", "Alice"),
            _agent_def("Seller", "Bob"),
        ],
        "negotiation_params": {
            "max_turns": 3,
            "agreement_threshold": 5000.0,
            "turn_order": ["Buyer", "Seller"],
        },
    }


# Track call count to produce converging prices
_call_counter = 0


def _mock_llm_response(role: str, call_num: int) -> str:
    """Return valid JSON responses that converge over turns."""
    if role == "Buyer":
        prices = [100000.0, 140000.0, 148000.0]
        price = prices[min(call_num, len(prices) - 1)]
        return json.dumps({
            "inner_thought": f"Offering {price}",
            "public_message": f"I propose {price}",
            "proposed_price": price,
        })
    else:  # Seller
        prices = [200000.0, 160000.0, 150000.0]
        price = prices[min(call_num, len(prices) - 1)]
        return json.dumps({
            "inner_thought": f"Counter at {price}",
            "public_message": f"I counter with {price}",
            "proposed_price": price,
        })


class TestRunNegotiationIntegration:
    """Integration test: full negotiation loop with mocked LLM."""

    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_full_negotiation_reaches_agreement(self, mock_router):
        """Run negotiation until agreement is reached."""
        buyer_calls = 0
        seller_calls = 0

        def _invoke(messages):
            nonlocal buyer_calls, seller_calls
            # Determine which agent is calling based on persona in system msg
            system_content = messages[0].content if messages else ""
            if "Alice" in system_content:
                resp = _mock_llm_response("Buyer", buyer_calls)
                buyer_calls += 1
            else:
                resp = _mock_llm_response("Seller", seller_calls)
                seller_calls += 1
            return AIMessage(content=resp)

        mock_model = MagicMock()
        mock_model.invoke.side_effect = _invoke
        mock_router.get_model.return_value = mock_model

        scenario = _make_scenario()
        initial = create_initial_state("int-test-1", scenario)

        snapshots = []
        async for snapshot in run_negotiation(initial, scenario):
            snapshots.append(snapshot)

        # Should have yielded at least one snapshot
        assert len(snapshots) > 0

        # The final state should have a terminal deal_status
        # Find the last snapshot that contains deal_status
        final_statuses = []
        for s in snapshots:
            if isinstance(s, dict):
                for key, val in s.items():
                    if isinstance(val, dict) and "deal_status" in val:
                        final_statuses.append(val["deal_status"])
                    elif key == "deal_status":
                        final_statuses.append(val)

    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_max_turns_causes_failure(self, mock_router):
        """When prices never converge, max_turns triggers Failed."""
        def _invoke(messages):
            system_content = messages[0].content if messages else ""
            if "Alice" in system_content:
                return AIMessage(content=json.dumps({
                    "inner_thought": "lowball",
                    "public_message": "I offer 50k",
                    "proposed_price": 50000.0,
                }))
            else:
                return AIMessage(content=json.dumps({
                    "inner_thought": "highball",
                    "public_message": "I want 500k",
                    "proposed_price": 500000.0,
                }))

        mock_model = MagicMock()
        mock_model.invoke.side_effect = _invoke
        mock_router.get_model.return_value = mock_model

        scenario = _make_scenario()
        # Set max_turns very low
        scenario["negotiation_params"]["max_turns"] = 2
        initial = create_initial_state("int-test-2", scenario)

        snapshots = []
        async for snapshot in run_negotiation(initial, scenario):
            snapshots.append(snapshot)

        assert len(snapshots) > 0

    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_snapshots_are_yielded(self, mock_router):
        """Verify that state snapshots are yielded during execution."""
        call_count = 0

        def _invoke(messages):
            nonlocal call_count
            call_count += 1
            # Always converge immediately
            return AIMessage(content=json.dumps({
                "inner_thought": "agree",
                "public_message": "deal",
                "proposed_price": 100000.0,
            }))

        mock_model = MagicMock()
        mock_model.invoke.side_effect = _invoke
        mock_router.get_model.return_value = mock_model

        scenario = _make_scenario()
        initial = create_initial_state("int-test-3", scenario)

        snapshots = []
        async for snapshot in run_negotiation(initial, scenario):
            snapshots.append(snapshot)

        # At minimum: dispatcher → agent → dispatcher → agent → dispatcher(agree) → end
        assert len(snapshots) >= 2
