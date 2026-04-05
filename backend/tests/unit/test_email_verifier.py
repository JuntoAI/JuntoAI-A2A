"""Unit tests for the EmailVerifier service.

Covers token generation, local-mode logging, SES sending (mocked),
token validation (valid, expired, not found), and profile update on verify.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_verifier import (
    EmailVerifier,
    SESDeliveryError,
    TokenExpiredError,
    TokenNotFoundError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_profile_client():
    """Profile client with async mocks for verification token CRUD + update_profile."""
    client = MagicMock()
    client.create_verification_token = AsyncMock()
    client.get_verification_token = AsyncMock()
    client.delete_verification_token = AsyncMock()
    client.update_profile = AsyncMock()
    return client


@pytest.fixture()
def verifier(mock_profile_client):
    return EmailVerifier(mock_profile_client)


# ---------------------------------------------------------------------------
# generate_and_send_verification — local mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_token_stores_with_24h_ttl(verifier, mock_profile_client):
    """Token is persisted with expires_at = created_at + 24h."""
    with patch("app.services.email_verifier.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        token = await verifier.generate_and_send_verification(
            "user@example.com", "https://app.juntoai.com"
        )

    assert token  # non-empty UUID string
    call_args = mock_profile_client.create_verification_token.call_args
    assert call_args is not None
    _, kwargs = call_args
    assert kwargs["email"] == "user@example.com"
    assert kwargs["token"] == token
    delta = kwargs["expires_at"] - kwargs["created_at"]
    assert delta == timedelta(hours=24)


@pytest.mark.asyncio
async def test_generate_token_local_mode_logs_link(verifier, mock_profile_client, caplog):
    """In local mode, the verification link is logged instead of sent via SES."""
    with patch("app.services.email_verifier.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        import logging

        with caplog.at_level(logging.INFO, logger="app.services.email_verifier"):
            token = await verifier.generate_and_send_verification(
                "user@example.com", "https://app.juntoai.com"
            )

    assert f"/profile/verify?token={token}" in caplog.text


@pytest.mark.asyncio
async def test_generate_token_unique_across_calls(mock_profile_client):
    """Each call produces a distinct token."""
    verifier = EmailVerifier(mock_profile_client)
    tokens = set()
    with patch("app.services.email_verifier.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        for _ in range(20):
            t = await verifier.generate_and_send_verification("a@b.com", "http://x")
            tokens.add(t)
    assert len(tokens) == 20


# ---------------------------------------------------------------------------
# generate_and_send_verification — cloud mode (SES)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_token_cloud_mode_calls_ses(verifier, mock_profile_client):
    """In cloud mode, SES send_email is invoked."""
    mock_ses = MagicMock()
    mock_ses.send_email = MagicMock()

    with (
        patch("app.services.email_verifier.settings") as mock_settings,
        patch("boto3.client", return_value=mock_ses) as mock_boto3_client,
    ):
        mock_settings.RUN_MODE = "cloud"

        token = await verifier.generate_and_send_verification(
            "user@example.com", "https://app.juntoai.com"
        )

    mock_ses.send_email.assert_called_once()
    call_kwargs = mock_ses.send_email.call_args[1]
    assert call_kwargs["Destination"]["ToAddresses"] == ["user@example.com"]
    assert token in call_kwargs["Message"]["Body"]["Html"]["Data"]


@pytest.mark.asyncio
async def test_generate_token_ses_failure_raises(verifier, mock_profile_client):
    """SES ClientError is wrapped in SESDeliveryError."""
    from botocore.exceptions import ClientError

    mock_ses = MagicMock()
    mock_ses.send_email.side_effect = ClientError(
        {"Error": {"Code": "MessageRejected", "Message": "bad"}}, "SendEmail"
    )

    with (
        patch("app.services.email_verifier.settings") as mock_settings,
        patch("boto3.client", return_value=mock_ses),
    ):
        mock_settings.RUN_MODE = "cloud"

        with pytest.raises(SESDeliveryError):
            await verifier.generate_and_send_verification(
                "user@example.com", "https://app.juntoai.com"
            )


# ---------------------------------------------------------------------------
# verify_token — success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_token_success(verifier, mock_profile_client):
    """Valid, non-expired token marks email verified and deletes the token."""
    now = datetime.now(timezone.utc)
    mock_profile_client.get_verification_token.return_value = {
        "email": "user@example.com",
        "created_at": now - timedelta(hours=1),
        "expires_at": now + timedelta(hours=23),
    }

    result = await verifier.verify_token("some-uuid-token")

    assert result == {"success": True, "email": "user@example.com"}
    mock_profile_client.update_profile.assert_awaited_once_with(
        "user@example.com", {"email_verified": True}
    )
    mock_profile_client.delete_verification_token.assert_awaited_once_with(
        "some-uuid-token"
    )


# ---------------------------------------------------------------------------
# verify_token — expired
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_token_expired_raises(verifier, mock_profile_client):
    """Expired token raises TokenExpiredError."""
    past = datetime.now(timezone.utc) - timedelta(hours=25)
    mock_profile_client.get_verification_token.return_value = {
        "email": "user@example.com",
        "created_at": past - timedelta(hours=24),
        "expires_at": past,
    }

    with pytest.raises(TokenExpiredError):
        await verifier.verify_token("expired-token")

    # Profile should NOT be updated
    mock_profile_client.update_profile.assert_not_awaited()
    mock_profile_client.delete_verification_token.assert_not_awaited()


# ---------------------------------------------------------------------------
# verify_token — not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_token_not_found_raises(verifier, mock_profile_client):
    """Non-existent token raises TokenNotFoundError."""
    mock_profile_client.get_verification_token.return_value = None

    with pytest.raises(TokenNotFoundError):
        await verifier.verify_token("nonexistent-token")


# ---------------------------------------------------------------------------
# verify_token — ISO string expires_at (SQLite local mode)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_token_handles_iso_string_expires_at(verifier, mock_profile_client):
    """expires_at stored as ISO string (SQLite) is parsed correctly."""
    now = datetime.now(timezone.utc)
    mock_profile_client.get_verification_token.return_value = {
        "email": "user@example.com",
        "created_at": (now - timedelta(hours=1)).isoformat(),
        "expires_at": (now + timedelta(hours=23)).isoformat(),
    }

    result = await verifier.verify_token("string-token")
    assert result["success"] is True
    assert result["email"] == "user@example.com"
