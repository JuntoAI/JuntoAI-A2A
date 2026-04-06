"""Unit tests for ProfileClient — mocked Firestore async client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.profile_client import ProfileClient

pytestmark = pytest.mark.unit


@pytest.fixture()
def client(mock_firestore_async_client):
    """ProfileClient wired to the shared mock Firestore fixture."""
    return ProfileClient(db=mock_firestore_async_client)


# --- get_or_create_profile: profile does NOT exist → creates with defaults ---


async def test_get_or_create_profile_creates_when_missing(
    client, mock_firestore_async_client,
):
    snapshot = MagicMock()
    snapshot.exists = False
    mock_firestore_async_client._doc_ref.get = AsyncMock(return_value=snapshot)

    result = await client.get_or_create_profile("new@example.com")

    # Should have called collection("profiles").document(email)
    mock_firestore_async_client.collection.assert_any_call("profiles")
    mock_firestore_async_client._collection_ref.document.assert_called_with(
        "new@example.com"
    )

    # Should have called set() with default fields
    mock_firestore_async_client._doc_ref.set.assert_awaited_once()
    set_arg = mock_firestore_async_client._doc_ref.set.call_args[0][0]
    assert set_arg["display_name"] == ""
    assert set_arg["email_verified"] is False
    assert set_arg["password_hash"] is None
    assert set_arg["google_oauth_id"] is None
    assert "created_at" in set_arg

    # Return value matches the defaults
    assert result["display_name"] == ""
    assert result["email_verified"] is False


# --- get_or_create_profile: profile exists → returns existing ---


async def test_get_or_create_profile_returns_existing(
    client, mock_firestore_async_client,
):
    existing = {
        "display_name": "Alice",
        "email_verified": True,
        "password_hash": "hashed",
        "google_oauth_id": "g-123",
    }
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = existing
    mock_firestore_async_client._doc_ref.get = AsyncMock(return_value=snapshot)

    result = await client.get_or_create_profile("alice@example.com")

    # Should NOT call set() — profile already exists
    mock_firestore_async_client._doc_ref.set.assert_not_awaited()

    assert result is existing
    assert result["display_name"] == "Alice"
    assert result["email_verified"] is True


# --- get_profile: returns None for non-existent email ---


async def test_get_profile_returns_none_when_missing(
    client, mock_firestore_async_client,
):
    snapshot = MagicMock()
    snapshot.exists = False
    mock_firestore_async_client._doc_ref.get = AsyncMock(return_value=snapshot)

    result = await client.get_profile("ghost@example.com")

    assert result is None


# --- get_profile: returns dict for existing email ---


async def test_get_profile_returns_dict_when_exists(
    client, mock_firestore_async_client,
):
    profile_data = {
        "display_name": "Bob",
        "email_verified": True,
        "country": "DE",
    }
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = profile_data
    mock_firestore_async_client._doc_ref.get = AsyncMock(return_value=snapshot)

    result = await client.get_profile("bob@example.com")

    assert result is profile_data
    assert result["display_name"] == "Bob"
    assert result["country"] == "DE"


# --- update_profile: calls Firestore update() with correct fields ---


async def test_update_profile_calls_firestore_update(
    client, mock_firestore_async_client,
):
    fields = {"display_name": "Updated", "country": "US"}

    await client.update_profile("user@example.com", fields)

    mock_firestore_async_client._collection_ref.document.assert_called_with(
        "user@example.com"
    )
    mock_firestore_async_client._doc_ref.update.assert_awaited_once_with(fields)
