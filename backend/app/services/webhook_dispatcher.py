"""Webhook Dispatcher — HMAC-SHA256 signed callback delivery with retry logic."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Default retry delays (seconds) for cloud mode — overridden by settings when available
_DEFAULT_RETRY_DELAYS = [5, 30, 120]


class WebhookDispatcher:
    """Delivers HMAC-SHA256 signed webhook callbacks to external systems."""

    @staticmethod
    def compute_signature(payload_bytes: bytes, secret: str) -> str:
        """Compute HMAC-SHA256 hex digest of payload using the secret.

        Args:
            payload_bytes: The raw bytes of the payload to sign.
            secret: The secret key (API key) used for HMAC computation.

        Returns:
            Hex digest string of the HMAC-SHA256 signature.
        """
        return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    @staticmethod
    def verify_signature(payload_bytes: bytes, secret: str, signature: str) -> bool:
        """Verify an HMAC-SHA256 signature using constant-time comparison.

        Args:
            payload_bytes: The raw bytes of the payload that was signed.
            secret: The secret key (API key) used for HMAC computation.
            signature: The signature to verify against.

        Returns:
            True if the signature is valid, False otherwise.
        """
        expected = WebhookDispatcher.compute_signature(payload_bytes, secret)
        return hmac.compare_digest(expected, signature)

    async def deliver(
        self,
        callback_url: str,
        payload: dict,
        api_key_raw: str,
        local_mode: bool = False,
    ) -> bool:
        """Deliver a webhook payload to the callback URL with HMAC-SHA256 signature.

        In cloud mode: retries up to 3 times with exponential backoff (5s, 30s, 120s).
        In local mode: single attempt, no retries.

        Args:
            callback_url: The URL to POST the webhook payload to.
            payload: The dict payload to serialize and send.
            api_key_raw: The raw API key used as the HMAC secret.
            local_mode: If True, single attempt without retries.

        Returns:
            True if delivery succeeded (2xx response), False otherwise.
        """
        # Serialize payload to JSON bytes
        payload_bytes = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")

        # Compute HMAC-SHA256 signature
        signature = self.compute_signature(payload_bytes, api_key_raw)

        headers = {
            "Content-Type": "application/json",
            "X-A2A-Signature": f"sha256={signature}",
        }

        # Determine retry delays
        if local_mode:
            retry_delays: list[int] = []
        else:
            retry_delays = getattr(settings, "WEBHOOK_RETRY_DELAYS", _DEFAULT_RETRY_DELAYS)

        # Total attempts = 1 (initial) + len(retry_delays) retries
        max_attempts = 1 + len(retry_delays)

        for attempt in range(max_attempts):
            try:
                logger.info(
                    "Webhook delivery attempt %d/%d to %s",
                    attempt + 1,
                    max_attempts,
                    callback_url,
                )

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        callback_url,
                        content=payload_bytes,
                        headers=headers,
                    )

                if 200 <= response.status_code < 300:
                    logger.info(
                        "Webhook delivered successfully to %s (status %d)",
                        callback_url,
                        response.status_code,
                    )
                    return True

                # Non-2xx response — treat as failure
                logger.warning(
                    "Webhook delivery to %s returned status %d (attempt %d/%d)",
                    callback_url,
                    response.status_code,
                    attempt + 1,
                    max_attempts,
                )

            except (httpx.HTTPError, OSError) as exc:
                logger.warning(
                    "Webhook delivery to %s failed with error: %s (attempt %d/%d)",
                    callback_url,
                    str(exc),
                    attempt + 1,
                    max_attempts,
                )

            # If there are more retries available, wait before the next attempt
            if attempt < len(retry_delays):
                delay = retry_delays[attempt]
                logger.info("Retrying webhook delivery in %d seconds...", delay)
                await asyncio.sleep(delay)

        # All attempts exhausted
        logger.error(
            "Webhook delivery to %s failed after %d attempts. Ceasing delivery.",
            callback_url,
            max_attempts,
        )
        return False
