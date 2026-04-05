"""Email verification service.

Generates UUID-based verification tokens with 24h TTL, stores them via
the injected profile client, and sends verification emails via Amazon SES
(cloud mode) or logs the link (local mode).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings

logger = logging.getLogger(__name__)

_TOKEN_TTL_HOURS = 24


class EmailVerifier:
    """Orchestrates email verification: token generation, email delivery, and validation."""

    def __init__(self, profile_client) -> None:
        self._profile_client = profile_client

    # ── Public API ────────────────────────────────────────────────

    async def generate_and_send_verification(self, email: str, base_url: str) -> str:
        """Generate a verification token, persist it, and send the verification email.

        Returns the generated token string.
        """
        token = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=_TOKEN_TTL_HOURS)

        await self._profile_client.create_verification_token(
            token=token,
            email=email,
            created_at=now,
            expires_at=expires_at,
        )

        verification_link = f"{base_url}/profile/verify?token={token}"

        if settings.RUN_MODE == "local":
            logger.info(
                "LOCAL MODE — verification link for %s: %s",
                email,
                verification_link,
            )
        else:
            await self._send_ses_email(email, verification_link)

        return token

    async def verify_token(self, token: str) -> dict:
        """Validate a verification token.

        Checks existence, checks expiry, marks the email as verified in the
        profile, and deletes the consumed token.

        Returns ``{"success": True, "email": "<email>"}`` on success.

        Raises:
            TokenNotFoundError: token does not exist.
            TokenExpiredError: token has expired.
        """
        token_doc = await self._profile_client.get_verification_token(token)
        if token_doc is None:
            raise TokenNotFoundError(token)

        email = token_doc["email"]
        expires_at = token_doc["expires_at"]

        # Normalise expires_at to a tz-aware datetime for comparison
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at:
            raise TokenExpiredError(token)

        # Mark email verified on the profile
        await self._profile_client.update_profile(email, {"email_verified": True})

        # Consume the token
        await self._profile_client.delete_verification_token(token)

        return {"success": True, "email": email}

    # ── SES helpers ───────────────────────────────────────────────

    @staticmethod
    async def _send_ses_email(recipient: str, verification_link: str) -> None:
        """Send a verification email via Amazon SES (boto3).

        Uses default IAM credentials from the backend service account.
        """
        import boto3
        from botocore.exceptions import ClientError

        ses = boto3.client("ses", region_name=settings.AWS_SES_REGION)

        subject = "Verify your email — JuntoAI"
        body_text = (
            f"Click the link below to verify your email address:\n\n"
            f"{verification_link}\n\n"
            f"This link expires in {_TOKEN_TTL_HOURS} hours."
        )
        body_html = (
            f"<p>Click the link below to verify your email address:</p>"
            f'<p><a href="{verification_link}">Verify Email</a></p>'
            f"<p>This link expires in {_TOKEN_TTL_HOURS} hours.</p>"
        )

        try:
            ses.send_email(
                Source=settings.SES_SENDER_EMAIL,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body_text, "Charset": "UTF-8"},
                        "Html": {"Data": body_html, "Charset": "UTF-8"},
                    },
                },
            )
        except ClientError as exc:
            logger.error("SES send_email failed for %s: %s", recipient, exc)
            raise SESDeliveryError(recipient) from exc


# ── Custom exceptions ─────────────────────────────────────────────


class TokenNotFoundError(Exception):
    """Raised when a verification token does not exist."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(f"Verification token not found: {token}")


class TokenExpiredError(Exception):
    """Raised when a verification token has expired."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(f"Verification token expired: {token}")


class SESDeliveryError(Exception):
    """Raised when Amazon SES fails to deliver the verification email."""

    def __init__(self, recipient: str) -> None:
        self.recipient = recipient
        super().__init__(f"Failed to send verification email to {recipient}")
