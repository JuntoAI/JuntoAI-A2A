"""Integration tests for @juntoai.org unlimited tokens behavior.

Validates: internal team members get unlimited token_balance and daily_limit
across auth/join, profile, and negotiation/start endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tier_calculator import UNLIMITED_TOKENS

pytestmark = pytest.mark.integration

INTERNAL_EMAIL = "engineer@juntoai.org"


# ---------------------------------------------------------------------------
# POST /api/v1/auth/join — internal user gets unlimited
# ---------------------------------------------------------------------------


class TestJoinWaitlistInternalEmail:
    """Internal @juntoai.org users get unlimited tokens on join."""

    @patch("app.routers.auth.settings")
    async def test_new_internal_user_gets_unlimited(
        self, mock_settings, test_client, mock_profile_client
    ):
        """New @juntoai.org user gets UNLIMITED_TOKENS balance and daily_limit."""
        mock_settings.RUN_MODE = "cloud"

        # Waitlist doc does not exist (new user)
        waitlist_doc = MagicMock()
        waitlist_doc.exists = False
        waitlist_ref = MagicMock()
        waitlist_ref.get = AsyncMock(return_value=waitlist_doc)
        waitlist_ref.set = AsyncMock()
        mock_profile_client._db.collection.return_value.document.return_value = (
            waitlist_ref
        )
        mock_profile_client.get_profile = AsyncMock(return_value=None)

        resp = await test_client.post(
            "/api/v1/auth/join",
            json={"email": INTERNAL_EMAIL},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == INTERNAL_EMAIL
        assert body["daily_limit"] == UNLIMITED_TOKENS
        assert body["token_balance"] == UNLIMITED_TOKENS

    @patch("app.routers.auth.settings")
    async def test_existing_internal_user_gets_unlimited(
        self, mock_settings, test_client, mock_profile_client
    ):
        """Existing @juntoai.org user always gets unlimited regardless of stored balance."""
        mock_settings.RUN_MODE = "cloud"

        # Waitlist doc exists with a low balance
        waitlist_doc = MagicMock()
        waitlist_doc.exists = True
        waitlist_doc.to_dict.return_value = {
            "token_balance": 5,
            "last_reset_date": "2099-12-31",  # not stale
        }
        waitlist_ref = MagicMock()
        waitlist_ref.get = AsyncMock(return_value=waitlist_doc)
        mock_profile_client._db.collection.return_value.document.return_value = (
            waitlist_ref
        )
        mock_profile_client.get_profile = AsyncMock(
            return_value={"email_verified": False, "profile_completed_at": None}
        )

        resp = await test_client.post(
            "/api/v1/auth/join",
            json={"email": INTERNAL_EMAIL},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["daily_limit"] == UNLIMITED_TOKENS
        assert body["token_balance"] == UNLIMITED_TOKENS


# ---------------------------------------------------------------------------
# GET /api/v1/profile/{email} — internal user gets unlimited
# ---------------------------------------------------------------------------


class TestProfileInternalEmail:
    """Internal @juntoai.org users see unlimited in profile response."""

    @patch("app.routers.profile.settings")
    async def test_profile_get_returns_unlimited(
        self, mock_settings, test_client, mock_profile_client
    ):
        """GET /profile for @juntoai.org email returns unlimited tokens."""
        mock_settings.RUN_MODE = "cloud"
        mock_settings.FRONTEND_URL = "http://localhost:3000"

        mock_profile_client.get_or_create_profile = AsyncMock(
            return_value={
                "display_name": "Team Dev",
                "email_verified": True,
                "profile_completed_at": None,
                "github_url": None,
                "linkedin_url": None,
                "created_at": "2024-01-01T00:00:00Z",
                "password_hash": None,
                "country": None,
                "google_oauth_id": None,
            }
        )

        resp = await test_client.get(f"/api/v1/profile/{INTERNAL_EMAIL}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["daily_limit"] == UNLIMITED_TOKENS
        assert body["token_balance"] == UNLIMITED_TOKENS


# ---------------------------------------------------------------------------
# Contrast: external email does NOT get unlimited
# ---------------------------------------------------------------------------


class TestExternalEmailNoUnlimited:
    """External emails never get unlimited tokens."""

    @patch("app.routers.auth.settings")
    async def test_external_user_gets_normal_limit(
        self, mock_settings, test_client, mock_profile_client
    ):
        """External user gets their tier-based daily_limit, not unlimited."""
        mock_settings.RUN_MODE = "cloud"

        waitlist_doc = MagicMock()
        waitlist_doc.exists = True
        waitlist_doc.to_dict.return_value = {
            "token_balance": 15,
            "last_reset_date": "2099-12-31",
        }
        waitlist_ref = MagicMock()
        waitlist_ref.get = AsyncMock(return_value=waitlist_doc)
        mock_profile_client._db.collection.return_value.document.return_value = (
            waitlist_ref
        )
        mock_profile_client.get_profile = AsyncMock(
            return_value={"email_verified": False, "profile_completed_at": None}
        )

        resp = await test_client.post(
            "/api/v1/auth/join",
            json={"email": "outsider@gmail.com"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["daily_limit"] == 20  # Tier 1
        assert body["token_balance"] != UNLIMITED_TOKENS
