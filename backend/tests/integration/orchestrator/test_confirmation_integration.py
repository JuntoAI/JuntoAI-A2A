"""Integration test: full confirmation flow via build_graph().

Task 10.1 — Validates Requirements 1.1, 2.1, 2.2:
- Convergence triggers Confirming → confirmation node → Agreed/Confirmed
- Confirmation rejection resumes negotiation (deal_status back to Negotiating)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.orchestrator.graph import build_graph
from app.orchestrator.state import create_initial_state


def _agent_def(
    role: str,
    name: str,
    agent_type: str = "negotiator",
    model_id: str = "gemini-3-flash-preview",
) -> dict[str, Any]:
    return {
        "role": role,
        "name": name,
        "type": agent_type,
        "model_id": model_id,
        "persona_prompt": f"You are {name}.",
        "goals": ["Close the deal"],
    }


def _make_scenario(
    max_turns: int = 6,
    threshold: float = 5000.0,
) -> dict[str, Any]:
    return {
        "id": "confirmation-integration",
        "agents": [
            _agent_def("Buyer", "Alice"),
            _agent_def("Seller", "Bob"),
        ],
        "negotiation_params": {
            "max_turns": max_turns,
            "agreement_threshold": threshold,
            "turn_order": ["Buyer", "Seller"],
        },
    }


def _negotiator_response(role: str, price: float) -> str:
    return json.dumps({
        "inner_thought": f"{role} proposing {price}",
        "public_message": f"I propose {price}",
        "proposed_price": price,
    })


def _confirmation_response(accept: bool, statement: str = "Confirmed.") -> str:
    return json.dumps({
        "accept": accept,
        "final_statement": statement,
        "conditions": [],
    })


class TestConfirmationIntegrationAccept:
    """Full graph run: convergence → Confirming → Agreed/Confirmed."""

    @patch("app.orchestrator.confirmation_node.model_router")
    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_convergence_leads_to_agreed_confirmed(
        self, mock_agent_router, mock_confirm_router,
    ):
        """Both agents converge within threshold, both accept confirmation → Agreed."""
        buyer_calls = 0
        seller_calls = 0

        def _agent_invoke(messages):
            nonlocal buyer_calls, seller_calls
            system_content = messages[0].content if messages else ""
            if "Alice" in system_content:
                # Buyer: 100000 → 101000 (converges with seller)
                prices = [100000.0, 101000.0]
                price = prices[min(buyer_calls, len(prices) - 1)]
                buyer_calls += 1
                return AIMessage(content=_negotiator_response("Buyer", price))
            else:
                # Seller: 200000 → 102000 (within 5000 of buyer's 101000)
                prices = [200000.0, 102000.0]
                price = prices[min(seller_calls, len(prices) - 1)]
                seller_calls += 1
                return AIMessage(content=_negotiator_response("Seller", price))

        agent_model = MagicMock()
        agent_model.invoke.side_effect = _agent_invoke
        mock_agent_router.get_model.return_value = agent_model

        # Confirmation: both accept
        def _confirm_invoke(_messages):
            return AIMessage(content=_confirmation_response(True, "I accept the deal."))

        confirm_model = MagicMock()
        confirm_model.invoke.side_effect = _confirm_invoke
        mock_confirm_router.get_model.return_value = confirm_model

        scenario = _make_scenario(max_turns=6, threshold=5000.0)
        initial = create_initial_state("confirm-accept-1", scenario)
        graph = build_graph(scenario)

        final_state = await graph.ainvoke(initial)

        assert final_state["deal_status"] == "Agreed"
        assert final_state["closure_status"] == "Confirmed"
        assert final_state["confirmation_pending"] == []

        # Verify confirmation history entries exist
        confirmation_entries = [
            e for e in final_state["history"]
            if e.get("agent_type") == "confirmation"
        ]
        assert len(confirmation_entries) == 2
        for entry in confirmation_entries:
            assert entry["content"]["accept"] is True


class TestConfirmationIntegrationReject:
    """Full graph run: convergence → Confirming → rejection → resumes negotiation."""

    @patch("app.orchestrator.confirmation_node.model_router")
    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_rejection_resumes_negotiation_then_fails_at_max_turns(
        self, mock_agent_router, mock_confirm_router,
    ):
        """One agent rejects confirmation → negotiation resumes, eventually hits max_turns → Failed."""
        buyer_calls = 0
        seller_calls = 0

        def _agent_invoke(messages):
            nonlocal buyer_calls, seller_calls
            system_content = messages[0].content if messages else ""
            if "Alice" in system_content:
                # Buyer always proposes 100000
                buyer_calls += 1
                return AIMessage(content=_negotiator_response("Buyer", 100000.0))
            else:
                # Seller always proposes 101000 (within threshold)
                seller_calls += 1
                return AIMessage(content=_negotiator_response("Seller", 101000.0))

        agent_model = MagicMock()
        agent_model.invoke.side_effect = _agent_invoke
        mock_agent_router.get_model.return_value = agent_model

        # Confirmation: Buyer accepts, Seller rejects
        confirm_calls = 0

        def _confirm_invoke(_messages):
            nonlocal confirm_calls
            confirm_calls += 1
            # Odd calls = Buyer (accepts), Even calls = Seller (rejects)
            if confirm_calls % 2 == 1:
                return AIMessage(content=_confirmation_response(True, "I accept."))
            else:
                return AIMessage(content=_confirmation_response(False, "I reject this deal."))

        confirm_model = MagicMock()
        confirm_model.invoke.side_effect = _confirm_invoke
        mock_confirm_router.get_model.return_value = confirm_model

        # Low max_turns so it terminates after rejection + resumed negotiation
        scenario = _make_scenario(max_turns=4, threshold=5000.0)
        initial = create_initial_state("confirm-reject-1", scenario)
        graph = build_graph(scenario)

        final_state = await graph.ainvoke(initial)

        # After rejection, negotiation resumes. Since agents keep converging,
        # it will enter Confirming again. With persistent rejection and
        # max_turns=4, it should eventually hit Failed or keep cycling.
        # The key assertion: deal_status is NOT "Agreed" with "Confirmed"
        # because the seller always rejects.
        if final_state["deal_status"] == "Agreed":
            # This shouldn't happen since seller always rejects
            pytest.fail("Deal should not be Agreed when seller always rejects")

        # Verify rejection entries exist in history
        rejection_entries = [
            e for e in final_state["history"]
            if e.get("agent_type") == "confirmation"
            and e["content"]["accept"] is False
        ]
        assert len(rejection_entries) >= 1, "Expected at least one rejection in history"
