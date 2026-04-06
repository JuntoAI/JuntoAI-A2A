"""Unit tests for app.services.auth_service — password hashing, Google token
validation, and Google OAuth ID uniqueness checks.

Requirements: 7.1, 7.2, 7.3
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.auth_service import (
    check_google_oauth_id_unique,
    hash_password,
    validate_google_token,
    verify_password,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# hash_password / verify_password round-trip (Req 7.1)
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    """Tests for hash_password and verify_password."""

    def test_round_trip_succeeds(self):
        """hash then verify with the same password returns True."""
        pw = "correct-horse-battery-staple"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_wrong_password_returns_false(self):
        """verify_password with a different password returns False."""
        hashed = hash_password("real-password")
        assert verify_password("wrong-password", hashed) is False

    def test_bcrypt_72_byte_truncation(self):
        """Passwords >72 bytes hash identically to their first 72 bytes."""
        long_pw = "A" * 100  # 100 ASCII chars = 100 bytes
        prefix_pw = "A" * 72  # bcrypt's max input length

        hashed = hash_password(long_pw)
        # The 72-byte prefix should verify against the hash of the 100-char pw
        assert verify_password(prefix_pw, hashed) is True
        # And vice-versa
        hashed_prefix = hash_password(prefix_pw)
        assert verify_password(long_pw, hashed_prefix) is True


# ---------------------------------------------------------------------------
# validate_google_token (Req 7.2)
# ---------------------------------------------------------------------------


class TestValidateGoogleToken:
    """Tests for validate_google_token with mocked requests.get."""

    @patch("app.services.auth_service.requests.get")
    def test_valid_token_returns_claims(self, mock_get: MagicMock):
        """Status 200 with valid claims (including 'sub') returns the claims dict."""
        claims = {"sub": "google-uid-123", "email": "user@example.com", "aud": "client-id"}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = claims
        mock_get.return_value = mock_resp

        result = validate_google_token("fake-id-token")

        assert result == claims
        mock_get.assert_called_once()

    @patch("app.services.auth_service.requests.get")
    def test_missing_sub_raises_value_error(self, mock_get: MagicMock):
        """Status 200 but missing 'sub' claim raises ValueError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"email": "user@example.com"}  # no 'sub'
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError, match="missing sub"):
            validate_google_token("fake-id-token")

    @patch("app.services.auth_service.requests.get")
    def test_non_200_raises_value_error(self, mock_get: MagicMock):
        """Status 401 (or any non-200) raises ValueError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError, match="Invalid Google ID token"):
            validate_google_token("bad-token")


# ---------------------------------------------------------------------------
# check_google_oauth_id_unique (Req 7.3)
# ---------------------------------------------------------------------------


class TestCheckGoogleOauthIdUnique:
    """Tests for check_google_oauth_id_unique with mocked profile client."""

    @pytest.mark.asyncio
    async def test_no_existing_profile_returns_true(self):
        """When no profile is linked to the OAuth ID, returns True."""
        pc = MagicMock()
        pc.get_profile_by_google_oauth_id = AsyncMock(return_value=None)

        result = await check_google_oauth_id_unique("oauth-123", "me@example.com", pc)
        assert result is True

    @pytest.mark.asyncio
    async def test_existing_profile_same_email_returns_true(self):
        """When the linked profile belongs to the same email, returns True."""
        pc = MagicMock()
        pc.get_profile_by_google_oauth_id = AsyncMock(
            return_value={"_email": "me@example.com"}
        )

        result = await check_google_oauth_id_unique("oauth-123", "me@example.com", pc)
        assert result is True

    @pytest.mark.asyncio
    async def test_existing_profile_different_email_returns_false(self):
        """When the linked profile belongs to a different email, returns False."""
        pc = MagicMock()
        pc.get_profile_by_google_oauth_id = AsyncMock(
            return_value={"_email": "other@example.com"}
        )

        result = await check_google_oauth_id_unique("oauth-123", "me@example.com", pc)
        assert result is False
