"""Authentication service — password hashing, Google token validation, OAuth ID checks."""

from __future__ import annotations

import logging

import bcrypt
import requests

logger = logging.getLogger(__name__)


def _truncate_for_bcrypt(password: str) -> bytes:
    """Truncate password to 72 bytes (bcrypt's maximum input length)."""
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt and return the hash as a string."""
    return bcrypt.hashpw(_truncate_for_bcrypt(password), bcrypt.gensalt()).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(_truncate_for_bcrypt(password), stored_hash.encode())


def validate_google_token(id_token: str) -> dict:
    """Validate a Google ID token via Google's tokeninfo endpoint.

    Returns the token claims dict (including ``sub`` and ``email``)
    on success.  Raises ``ValueError`` if the token is invalid.
    """
    resp = requests.get(
        f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}",
        timeout=10,
    )
    if resp.status_code != 200:
        raise ValueError("Invalid Google ID token")
    claims = resp.json()
    if "sub" not in claims:
        raise ValueError("Invalid Google ID token: missing sub claim")
    return claims


async def check_google_oauth_id_unique(
    google_oauth_id: str, exclude_email: str, profile_client
) -> bool:
    """Return True if *google_oauth_id* is not linked to any profile other than *exclude_email*."""
    existing = await profile_client.get_profile_by_google_oauth_id(google_oauth_id)
    if existing is None:
        return True
    # If the found profile belongs to the same email, it's fine
    return existing.get("_email", "").lower() == exclude_email.lower()
