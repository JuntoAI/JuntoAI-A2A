"""Shared fixtures for orchestrator integration tests.

Auto-mocks the confirmation_node's model_router so integration tests
that mock only agent_node.model_router don't hit the real LLM when the
graph transitions into the confirmation phase.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


@pytest.fixture(autouse=True)
def _mock_confirmation_model_router():
    """Always accept during confirmation phase in integration tests.

    Tests in this directory mock ``app.orchestrator.agent_node.model_router``
    for the negotiator loop, but the confirmation node holds its own
    reference to ``model_router``. Without this fixture, reaching the
    confirmation phase would trigger a real network call.
    """

    def _accept_invoke(_messages):
        return AIMessage(
            content=json.dumps(
                {
                    "accept": True,
                    "final_statement": "I accept the deal.",
                    "conditions": [],
                }
            )
        )

    mock_model = MagicMock()
    mock_model.invoke.side_effect = _accept_invoke

    with patch(
        "app.orchestrator.confirmation_node.model_router"
    ) as mock_router:
        mock_router.get_model.return_value = mock_model
        yield mock_router
