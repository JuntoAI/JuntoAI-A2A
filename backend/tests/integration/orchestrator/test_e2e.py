"""End-to-end integration tests for the orchestrator package.

Task 8.2: 2-agent e2e test (Buyer + Seller) with mocked LLMs.
Task 8.3: 4-agent e2e test (2 negotiators + 1 regulator + 1 observer).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.orchestrator import (
    NegotiationState,
    build_graph,
    create_initial_state,
    run_negotiation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agent_def(
    role: str,
    name: str,
    agent_type: str = "negotiator",
    model_id: str = "gemini-2.5-flash",
    **extra: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "role": role,
        "name": name,
        "type": agent_type,
        "model_id": model_id,
        "persona_prompt": f"You are {name}.",
        "goals": [f"Achieve the best outcome as {name}"],
    }
    base.update(extra)
    return base


def _negotiator_json(price: float, name: str = "agent") -> str:
    return json.dumps({
        "inner_thought": f"{name} thinking about {price}",
        "public_message": f"{name} proposes {price}",
        "proposed_price": price,
    })


def _regulator_json(status: str = "CLEAR") -> str:
    return json.dumps({
        "status": status,
        "reasoning": f"Regulatory review: {status}",
    })


def _observer_json() -> str:
    return json.dumps({
        "observation": "Observing the negotiation progress",
        "recommendation": "Continue as planned",
    })


def _make_mock_model(invoke_side_effect):
    """Create a MagicMock model with the given invoke side effect."""
    mock_model = MagicMock()
    mock_model.invoke.side_effect = invoke_side_effect
    return mock_model


# ---------------------------------------------------------------------------
# Task 8.2 — 2-agent e2e (Buyer + Seller, converging to agreement)
# ---------------------------------------------------------------------------


class TestTwoAgentE2E:
    """End-to-end: Buyer + Seller scenario reaching agreement."""

    @staticmethod
    def _scenario() -> dict[str, Any]:
        return {
            "id": "e2e-two-agent",
            "agents": [
                _agent_def("Buyer", "Alice"),
                _agent_def("Seller", "Bob"),
            ],
            "negotiation_params": {
                "max_turns": 5,
                "agreement_threshold": 5000.0,
                "turn_order": ["Buyer", "Seller"],
            },
        }

    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_two_agent_reaches_agreement(self, mock_router):
        """Buyer and Seller converge within threshold → Agreed."""
        buyer_calls = 0
        seller_calls = 0

        # Buyer: 100k → 140k → 148k
        # Seller: 200k → 160k → 150k
        # After turn 3: |150k - 148k| = 2k < 5k threshold → Agreed
        buyer_prices = [100_000.0, 140_000.0, 148_000.0]
        seller_prices = [200_000.0, 160_000.0, 150_000.0]

        def _invoke(messages):
            nonlocal buyer_calls, seller_calls
            system_content = messages[0].content if messages else ""
            if "Alice" in system_content:
                price = buyer_prices[min(buyer_calls, len(buyer_prices) - 1)]
                buyer_calls += 1
                return AIMessage(content=_negotiator_json(price, "Alice"))
            else:
                price = seller_prices[min(seller_calls, len(seller_prices) - 1)]
                seller_calls += 1
                return AIMessage(content=_negotiator_json(price, "Bob"))

        mock_router.get_model.return_value = _make_mock_model(_invoke)

        scenario = self._scenario()
        initial = create_initial_state("e2e-sess-1", scenario)

        snapshots: list[Any] = []
        async for snapshot in run_negotiation(initial, scenario):
            snapshots.append(snapshot)

        # Must yield at least some snapshots
        assert len(snapshots) > 0, "No snapshots yielded"

        # Extract terminal deal_status from snapshots
        # LangGraph astream yields dicts keyed by node name → state delta
        terminal_status = _extract_terminal_status(snapshots)
        assert terminal_status == "Agreed", (
            f"Expected 'Agreed', got '{terminal_status}'"
        )

    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_two_agent_snapshots_yielded(self, mock_router):
        """Verify multiple state snapshots are yielded during execution."""
        def _invoke(messages):
            # Both agents propose same price → immediate agreement after both go
            return AIMessage(content=_negotiator_json(100_000.0, "agent"))

        mock_router.get_model.return_value = _make_mock_model(_invoke)

        scenario = self._scenario()
        initial = create_initial_state("e2e-sess-2", scenario)

        snapshots: list[Any] = []
        async for snapshot in run_negotiation(initial, scenario):
            snapshots.append(snapshot)

        # dispatcher + agent + dispatcher + agent + dispatcher(agree) = multiple
        assert len(snapshots) >= 2, f"Expected >=2 snapshots, got {len(snapshots)}"

    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_two_agent_terminal_state_reached(self, mock_router):
        """Negotiation always reaches a terminal state (not stuck in Negotiating)."""
        call_count = 0

        def _invoke(messages):
            nonlocal call_count
            call_count += 1
            # Diverging prices → will hit max_turns → Failed
            system_content = messages[0].content if messages else ""
            if "Alice" in system_content:
                return AIMessage(content=_negotiator_json(10_000.0, "Alice"))
            return AIMessage(content=_negotiator_json(900_000.0, "Bob"))

        mock_router.get_model.return_value = _make_mock_model(_invoke)

        scenario = self._scenario()
        scenario["negotiation_params"]["max_turns"] = 2
        initial = create_initial_state("e2e-sess-3", scenario)

        snapshots: list[Any] = []
        async for snapshot in run_negotiation(initial, scenario):
            snapshots.append(snapshot)

        terminal_status = _extract_terminal_status(snapshots)
        assert terminal_status in ("Agreed", "Blocked", "Failed"), (
            f"Expected terminal status, got '{terminal_status}'"
        )


# ---------------------------------------------------------------------------
# Task 8.3 — 4-agent e2e (2 negotiators + 1 regulator + 1 observer)
# ---------------------------------------------------------------------------


class TestFourAgentE2E:
    """End-to-end: Buyer + Seller + Regulator + Analyst (observer)."""

    @staticmethod
    def _scenario() -> dict[str, Any]:
        return {
            "id": "e2e-four-agent",
            "agents": [
                _agent_def("Buyer", "Alice", agent_type="negotiator"),
                _agent_def("Seller", "Bob", agent_type="negotiator"),
                _agent_def(
                    "Regulator", "RegBot",
                    agent_type="regulator",
                    model_id="claude-sonnet-4",
                ),
                _agent_def(
                    "Analyst", "WatchBot",
                    agent_type="observer",
                    model_id="gemini-2.5-pro",
                ),
            ],
            "negotiation_params": {
                "max_turns": 5,
                "agreement_threshold": 5000.0,
                "turn_order": [
                    "Buyer", "Regulator", "Seller", "Regulator", "Analyst",
                ],
            },
        }

    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_four_agent_all_types_execute(self, mock_router):
        """All 4 agent types execute and appear in state snapshots."""
        buyer_calls = 0
        seller_calls = 0

        buyer_prices = [100_000.0, 148_000.0]
        seller_prices = [200_000.0, 150_000.0]

        def _invoke(messages):
            nonlocal buyer_calls, seller_calls
            system_content = messages[0].content if messages else ""

            if "Alice" in system_content:
                price = buyer_prices[min(buyer_calls, len(buyer_prices) - 1)]
                buyer_calls += 1
                return AIMessage(content=_negotiator_json(price, "Alice"))
            elif "Bob" in system_content:
                price = seller_prices[min(seller_calls, len(seller_prices) - 1)]
                seller_calls += 1
                return AIMessage(content=_negotiator_json(price, "Bob"))
            elif "RegBot" in system_content:
                return AIMessage(content=_regulator_json("CLEAR"))
            elif "WatchBot" in system_content:
                return AIMessage(content=_observer_json())
            else:
                # Fallback — shouldn't happen
                return AIMessage(content=_negotiator_json(100_000.0, "unknown"))

        mock_router.get_model.return_value = _make_mock_model(_invoke)

        scenario = self._scenario()
        initial = create_initial_state("e2e-sess-4", scenario)

        snapshots: list[Any] = []
        async for snapshot in run_negotiation(initial, scenario):
            snapshots.append(snapshot)

        assert len(snapshots) > 0, "No snapshots yielded"

        # Collect all roles that appeared in snapshot keys (node names)
        executed_roles = set()
        for s in snapshots:
            if isinstance(s, dict):
                for key in s:
                    if key in ("Buyer", "Seller", "Regulator", "Analyst"):
                        executed_roles.add(key)

        assert "Buyer" in executed_roles, "Buyer never executed"
        assert "Seller" in executed_roles, "Seller never executed"
        assert "Regulator" in executed_roles, "Regulator never executed"
        assert "Analyst" in executed_roles, "Analyst (observer) never executed"

    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_four_agent_reaches_terminal(self, mock_router):
        """4-agent scenario reaches a terminal deal_status."""
        buyer_calls = 0
        seller_calls = 0

        # Converging prices
        buyer_prices = [145_000.0, 149_000.0]
        seller_prices = [155_000.0, 150_000.0]

        def _invoke(messages):
            nonlocal buyer_calls, seller_calls
            system_content = messages[0].content if messages else ""

            if "Alice" in system_content:
                price = buyer_prices[min(buyer_calls, len(buyer_prices) - 1)]
                buyer_calls += 1
                return AIMessage(content=_negotiator_json(price, "Alice"))
            elif "Bob" in system_content:
                price = seller_prices[min(seller_calls, len(seller_prices) - 1)]
                seller_calls += 1
                return AIMessage(content=_negotiator_json(price, "Bob"))
            elif "RegBot" in system_content:
                return AIMessage(content=_regulator_json("CLEAR"))
            else:
                return AIMessage(content=_observer_json())

        mock_router.get_model.return_value = _make_mock_model(_invoke)

        scenario = self._scenario()
        initial = create_initial_state("e2e-sess-5", scenario)

        snapshots: list[Any] = []
        async for snapshot in run_negotiation(initial, scenario):
            snapshots.append(snapshot)

        terminal_status = _extract_terminal_status(snapshots)
        assert terminal_status in ("Agreed", "Blocked", "Failed"), (
            f"Expected terminal status, got '{terminal_status}'"
        )

    @patch("app.orchestrator.agent_node.model_router")
    @pytest.mark.asyncio
    async def test_four_agent_history_includes_all_roles(self, mock_router):
        """History entries include all 4 agent roles after execution."""
        buyer_calls = 0
        seller_calls = 0

        # First cycle: diverge so Analyst gets a turn. Second cycle: converge.
        buyer_prices = [100_000.0, 148_000.0]
        seller_prices = [200_000.0, 150_000.0]

        def _invoke(messages):
            nonlocal buyer_calls, seller_calls
            system_content = messages[0].content if messages else ""

            if "Alice" in system_content:
                price = buyer_prices[min(buyer_calls, len(buyer_prices) - 1)]
                buyer_calls += 1
                return AIMessage(content=_negotiator_json(price, "Alice"))
            elif "Bob" in system_content:
                price = seller_prices[min(seller_calls, len(seller_prices) - 1)]
                seller_calls += 1
                return AIMessage(content=_negotiator_json(price, "Bob"))
            elif "RegBot" in system_content:
                return AIMessage(content=_regulator_json("CLEAR"))
            else:
                return AIMessage(content=_observer_json())

        mock_router.get_model.return_value = _make_mock_model(_invoke)

        scenario = self._scenario()
        initial = create_initial_state("e2e-sess-6", scenario)

        snapshots: list[Any] = []
        async for snapshot in run_negotiation(initial, scenario):
            snapshots.append(snapshot)

        # Collect history entries from all snapshots
        all_history_roles = set()
        for s in snapshots:
            if isinstance(s, dict):
                for key, val in s.items():
                    if isinstance(val, dict) and "history" in val:
                        for entry in val["history"]:
                            if isinstance(entry, dict) and "role" in entry:
                                all_history_roles.add(entry["role"])

        # All 4 roles should appear in history
        assert "Buyer" in all_history_roles, "Buyer missing from history"
        assert "Seller" in all_history_roles, "Seller missing from history"
        assert "Regulator" in all_history_roles, "Regulator missing from history"
        assert "Analyst" in all_history_roles, "Analyst missing from history"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _extract_terminal_status(snapshots: list[Any]) -> str | None:
    """Walk snapshots to find the final deal_status.

    LangGraph ``astream`` yields dicts keyed by node name, where the value
    is the state delta produced by that node.  The dispatcher sets
    ``deal_status`` on terminal conditions.
    """
    last_status: str | None = None
    for s in snapshots:
        if not isinstance(s, dict):
            continue
        for _node_name, delta in s.items():
            if isinstance(delta, dict) and "deal_status" in delta:
                last_status = delta["deal_status"]
    return last_status
