"""Unit tests for FirestoreSessionClient — mocked Firestore async client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.firestore_client import FirestoreSessionClient
from app.exceptions import SessionNotFoundError
from app.models.negotiation import NegotiationStateModel

pytestmark = pytest.mark.unit


def _make_state(**overrides) -> NegotiationStateModel:
    """Build a minimal valid NegotiationStateModel with sensible defaults."""
    defaults = {
        "session_id": "fs-001",
        "scenario_id": "test-scenario",
        "turn_count": 0,
        "max_turns": 10,
        "current_speaker": "Buyer",
        "deal_status": "Negotiating",
        "current_offer": 0.0,
        "history": [],
        "warning_count": 0,
        "hidden_context": {},
        "agreement_threshold": 1000.0,
        "active_toggles": [],
        "turn_order": ["Buyer", "Seller"],
        "turn_order_index": 0,
        "agent_states": {},
    }
    defaults.update(overrides)
    return NegotiationStateModel(**defaults)


@pytest.fixture()
def client(mock_firestore_async_client):
    """FirestoreSessionClient wired to the shared mock Firestore fixture."""
    return FirestoreSessionClient(db=mock_firestore_async_client)


# --- create_session calls Firestore set() with serialized state ---


async def test_create_session_calls_set_with_serialized_state(
    client, mock_firestore_async_client
):
    state = _make_state(session_id="create-001", turn_count=3, current_offer=500.0)

    await client.create_session(state)

    # Verify collection + document chain
    mock_firestore_async_client.collection.assert_called_with("negotiation_sessions")
    mock_firestore_async_client._collection_ref.document.assert_called_with("create-001")

    # Verify set() was awaited with the full model_dump()
    mock_firestore_async_client._doc_ref.set.assert_awaited_once_with(state.model_dump())


# --- get_session deserializes document snapshot to NegotiationStateModel ---


async def test_get_session_returns_negotiation_state_model(
    client, mock_firestore_async_client
):
    state_data = _make_state(
        session_id="get-001", turn_count=5, deal_status="Agreed", current_offer=750.0
    ).model_dump()

    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = state_data
    mock_firestore_async_client._doc_ref.get = AsyncMock(return_value=snapshot)

    result = await client.get_session("get-001")

    assert isinstance(result, NegotiationStateModel)
    assert result.session_id == "get-001"
    assert result.turn_count == 5
    assert result.deal_status == "Agreed"
    assert result.current_offer == 750.0


# --- get_session_doc returns raw dict from document snapshot ---


async def test_get_session_doc_returns_raw_dict(
    client, mock_firestore_async_client
):
    raw = {"session_id": "doc-001", "scenario_id": "s1", "turn_count": 2}

    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = raw
    mock_firestore_async_client._doc_ref.get = AsyncMock(return_value=snapshot)

    result = await client.get_session_doc("doc-001")

    assert result is raw
    assert result["session_id"] == "doc-001"
    assert result["turn_count"] == 2


# --- non-existent document raises SessionNotFoundError ---


async def test_get_session_raises_on_missing_document(
    client, mock_firestore_async_client
):
    snapshot = MagicMock()
    snapshot.exists = False
    mock_firestore_async_client._doc_ref.get = AsyncMock(return_value=snapshot)

    with pytest.raises(SessionNotFoundError):
        await client.get_session("ghost-session")


async def test_get_session_doc_raises_on_missing_document(
    client, mock_firestore_async_client
):
    snapshot = MagicMock()
    snapshot.exists = False
    mock_firestore_async_client._doc_ref.get = AsyncMock(return_value=snapshot)

    with pytest.raises(SessionNotFoundError):
        await client.get_session_doc("ghost-session")
