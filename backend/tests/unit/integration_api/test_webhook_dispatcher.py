"""Unit tests for the Webhook Dispatcher.

Tests cover:
- 3 retries with correct delays in cloud mode
- Single attempt in local mode
- Failure logging after all retries exhausted
- HMAC signature included in X-A2A-Signature header

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.webhook_dispatcher import WebhookDispatcher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dispatcher():
    """Create a WebhookDispatcher instance."""
    return WebhookDispatcher()


@pytest.fixture()
def sample_payload():
    """A sample webhook payload dict."""
    return {
        "event": "simulation.completed",
        "session_id": "abc123",
        "scenario_id": "talent_war",
        "status": "completed",
        "outcome": {"deal_status": "Agreed", "final_offer": 125000},
        "viewer_url": "https://app.juntoai.org/share/xyz",
        "timestamp": "2024-01-15T10:30:00Z",
    }


# ---------------------------------------------------------------------------
# Test: 3 retries with correct delays in cloud mode (Requirement 11.3)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cloud_mode_retries_three_times_on_failure(dispatcher, sample_payload):
    """In cloud mode, failed delivery retries 3 times with delays [5, 30, 120]."""
    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        with patch("app.services.webhook_dispatcher.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await dispatcher.deliver(
                callback_url="https://example.com/webhook",
                payload=sample_payload,
                api_key_raw="a2a_live_testkey123",
                local_mode=False,
            )

    assert result is False
    # 4 total attempts: 1 initial + 3 retries
    assert mock_client.post.call_count == 4
    # 3 sleep calls with correct delays
    assert mock_sleep.call_count == 3
    mock_sleep.assert_any_call(5)
    mock_sleep.assert_any_call(30)
    mock_sleep.assert_any_call(120)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cloud_mode_succeeds_on_second_attempt(dispatcher, sample_payload):
    """In cloud mode, if second attempt succeeds, no further retries."""
    fail_response = MagicMock()
    fail_response.status_code = 503

    success_response = MagicMock()
    success_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[fail_response, success_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        with patch("app.services.webhook_dispatcher.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await dispatcher.deliver(
                callback_url="https://example.com/webhook",
                payload=sample_payload,
                api_key_raw="a2a_live_testkey123",
                local_mode=False,
            )

    assert result is True
    assert mock_client.post.call_count == 2
    # Only 1 sleep (after first failure)
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_once_with(5)


# ---------------------------------------------------------------------------
# Test: Single attempt in local mode (Requirement 11.5)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_local_mode_single_attempt_no_retries(dispatcher, sample_payload):
    """In local mode, only one attempt is made regardless of failure."""
    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        with patch("app.services.webhook_dispatcher.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await dispatcher.deliver(
                callback_url="http://localhost:8080/webhook",
                payload=sample_payload,
                api_key_raw="a2a_live_testkey123",
                local_mode=True,
            )

    assert result is False
    assert mock_client.post.call_count == 1
    mock_sleep.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_local_mode_success_on_first_attempt(dispatcher, sample_payload):
    """In local mode, successful delivery returns True."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        result = await dispatcher.deliver(
            callback_url="http://localhost:8080/webhook",
            payload=sample_payload,
            api_key_raw="a2a_live_testkey123",
            local_mode=True,
        )

    assert result is True
    assert mock_client.post.call_count == 1


# ---------------------------------------------------------------------------
# Test: Failure logging after all retries exhausted (Requirement 11.4)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failure_logged_after_retries_exhausted(dispatcher, sample_payload):
    """After all retries fail, an error is logged and False is returned."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        with patch("app.services.webhook_dispatcher.asyncio.sleep", new_callable=AsyncMock):
            with patch("app.services.webhook_dispatcher.logger") as mock_logger:
                result = await dispatcher.deliver(
                    callback_url="https://example.com/webhook",
                    payload=sample_payload,
                    api_key_raw="a2a_live_testkey123",
                    local_mode=False,
                )

    assert result is False
    # Verify error was logged after all attempts exhausted
    mock_logger.error.assert_called()
    error_call_args = mock_logger.error.call_args[0][0]
    assert "failed after" in error_call_args.lower() or "ceasing" in error_call_args.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_network_error_triggers_retry(dispatcher, sample_payload):
    """Network errors (OSError, httpx.HTTPError) trigger retries in cloud mode."""
    success_response = MagicMock()
    success_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=[OSError("Network unreachable"), success_response]
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        with patch("app.services.webhook_dispatcher.asyncio.sleep", new_callable=AsyncMock):
            result = await dispatcher.deliver(
                callback_url="https://example.com/webhook",
                payload=sample_payload,
                api_key_raw="a2a_live_testkey123",
                local_mode=False,
            )

    assert result is True
    assert mock_client.post.call_count == 2


# ---------------------------------------------------------------------------
# Test: HMAC signature included in X-A2A-Signature header (Requirement 11.2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hmac_signature_in_header(dispatcher, sample_payload):
    """The X-A2A-Signature header contains sha256=<hex digest> of the payload."""
    api_key = "a2a_live_mysecretkey12345"

    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient", return_value=mock_client):
        await dispatcher.deliver(
            callback_url="https://example.com/webhook",
            payload=sample_payload,
            api_key_raw=api_key,
            local_mode=False,
        )

    # Extract the headers from the post call
    call_kwargs = mock_client.post.call_args[1]
    headers = call_kwargs["headers"]

    assert "X-A2A-Signature" in headers
    signature_header = headers["X-A2A-Signature"]
    assert signature_header.startswith("sha256=")

    # Verify the signature matches what we'd compute manually
    payload_bytes = call_kwargs["content"]
    expected_sig = hmac.new(
        api_key.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()
    assert signature_header == f"sha256={expected_sig}"


@pytest.mark.unit
def test_compute_signature_matches_hmac(dispatcher):
    """compute_signature produces the same result as manual hmac computation."""
    payload = b'{"event":"test","data":"hello"}'
    secret = "my_secret_key"

    result = WebhookDispatcher.compute_signature(payload, secret)
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert result == expected


@pytest.mark.unit
def test_verify_signature_correct(dispatcher):
    """verify_signature returns True for a correctly computed signature."""
    payload = b'{"session_id":"abc123"}'
    secret = "test_api_key"

    signature = WebhookDispatcher.compute_signature(payload, secret)
    assert WebhookDispatcher.verify_signature(payload, secret, signature) is True


@pytest.mark.unit
def test_verify_signature_wrong_key(dispatcher):
    """verify_signature returns False when the key doesn't match."""
    payload = b'{"session_id":"abc123"}'
    secret = "correct_key"
    wrong_key = "wrong_key"

    signature = WebhookDispatcher.compute_signature(payload, secret)
    assert WebhookDispatcher.verify_signature(payload, wrong_key, signature) is False


@pytest.mark.unit
def test_verify_signature_tampered_payload(dispatcher):
    """verify_signature returns False when the payload is tampered."""
    payload = b'{"session_id":"abc123"}'
    tampered = b'{"session_id":"hacked"}'
    secret = "test_key"

    signature = WebhookDispatcher.compute_signature(payload, secret)
    assert WebhookDispatcher.verify_signature(tampered, secret, signature) is False
