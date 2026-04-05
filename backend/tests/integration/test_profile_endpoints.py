"""Integration tests for profile endpoints.

Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 12.6, 12.7
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _force_cloud_mode():
    """Force RUN_MODE=cloud so waitlist helpers use the mocked Firestore path."""
    with patch("app.routers.profile.settings") as mock_settings:
        mock_settings.RUN_MODE = "cloud"
        yield mock_settings


# ---------------------------------------------------------------------------
# GET /api/v1/profile/{email}
# ---------------------------------------------------------------------------


class TestGetProfile:
    """GET /api/v1/profile/{email} — get-or-create profile."""

    async def test_creates_new_profile_with_defaults(
        self, test_client, mock_profile_client
    ):
        """New profile returns all default fields including password_hash, country, google_oauth_id."""
        defaults = {
            "display_name": "",
            "email_verified": False,
            "github_url": None,
            "linkedin_url": None,
            "profile_completed_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "password_hash": None,
            "country": None,
            "google_oauth_id": None,
        }
        mock_profile_client.get_or_create_profile = AsyncMock(return_value=defaults)

        resp = await test_client.get("/api/v1/profile/new@example.com")

        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == ""
        assert body["email_verified"] is False
        assert body["github_url"] is None
        assert body["linkedin_url"] is None
        assert body["profile_completed_at"] is None
        assert body["password_hash_set"] is False
        assert body["country"] is None
        assert body["google_oauth_id"] is None
        assert body["tier"] == 1
        assert body["daily_limit"] == 20

    async def test_returns_existing_profile(self, test_client, mock_profile_client):
        """Existing profile with modifications is returned as-is."""
        existing = {
            "display_name": "Alice",
            "email_verified": True,
            "github_url": "https://github.com/alice",
            "linkedin_url": None,
            "profile_completed_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "password_hash": "$2b$12$somehash",
            "country": "US",
            "google_oauth_id": "google-123",
        }
        mock_profile_client.get_or_create_profile = AsyncMock(return_value=existing)

        resp = await test_client.get("/api/v1/profile/alice@example.com")

        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "Alice"
        assert body["email_verified"] is True
        assert body["password_hash_set"] is True
        assert body["country"] == "US"
        assert body["google_oauth_id"] == "google-123"
        assert body["tier"] == 3
        assert body["daily_limit"] == 100


# ---------------------------------------------------------------------------
# PUT /api/v1/profile/{email}
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    """PUT /api/v1/profile/{email} — update profile fields."""

    async def test_valid_update_with_country(self, test_client, mock_profile_client):
        """Valid update including country field succeeds."""
        existing = {
            "display_name": "",
            "email_verified": False,
            "github_url": None,
            "linkedin_url": None,
            "profile_completed_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "password_hash": None,
            "country": None,
            "google_oauth_id": None,
        }
        updated = {**existing, "display_name": "Bob", "country": "DE"}
        mock_profile_client.get_profile = AsyncMock(
            side_effect=[existing, updated]
        )
        mock_profile_client.update_profile = AsyncMock()

        resp = await test_client.put(
            "/api/v1/profile/bob@example.com",
            json={"display_name": "Bob", "country": "DE"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "Bob"
        assert body["country"] == "DE"

    async def test_invalid_country_code_returns_422(
        self, test_client, mock_profile_client
    ):
        """Invalid country code triggers Pydantic validation error."""
        resp = await test_client.put(
            "/api/v1/profile/bob@example.com",
            json={"country": "ZZ"},
        )
        assert resp.status_code == 422

    async def test_tier_upgrade_on_profile_completion(
        self, test_client, mock_profile_client
    ):
        """Profile becoming complete triggers tier 3 upgrade."""
        existing = {
            "display_name": "Carol",
            "email_verified": True,
            "github_url": None,
            "linkedin_url": None,
            "profile_completed_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "password_hash": None,
            "country": None,
            "google_oauth_id": None,
        }
        completed = {
            **existing,
            "github_url": "https://github.com/carol",
            "profile_completed_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_profile_client.get_profile = AsyncMock(
            side_effect=[existing, completed]
        )
        mock_profile_client.update_profile = AsyncMock()

        resp = await test_client.put(
            "/api/v1/profile/carol@example.com",
            json={"github_url": "https://github.com/carol"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["tier"] == 3
        assert body["daily_limit"] == 100

    async def test_404_for_nonexistent_profile(
        self, test_client, mock_profile_client
    ):
        """PUT on a non-existent profile returns 404."""
        mock_profile_client.get_profile = AsyncMock(return_value=None)

        resp = await test_client.put(
            "/api/v1/profile/nobody@example.com",
            json={"display_name": "Nobody"},
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/profile/{email}/verify-email
# ---------------------------------------------------------------------------


class TestVerifyEmail:
    """POST /api/v1/profile/{email}/verify-email — send verification email."""

    async def test_sends_verification_email(
        self, test_client, mock_profile_client, _force_cloud_mode
    ):
        """Verification email is sent and token returned."""
        mock_profile_client.create_verification_token = AsyncMock()
        # Override to local so the email verifier logs instead of calling SES
        _force_cloud_mode.RUN_MODE = "local"

        resp = await test_client.post(
            "/api/v1/profile/user@example.com/verify-email"
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Verification email sent"
        assert "token" in body


# ---------------------------------------------------------------------------
# GET /api/v1/profile/verify/{token}
# ---------------------------------------------------------------------------


class TestVerifyToken:
    """GET /api/v1/profile/verify/{token} — validate verification token."""

    async def test_valid_token(self, test_client, mock_profile_client):
        """Valid, non-expired token marks email as verified."""
        now = datetime.now(timezone.utc)
        token_doc = {
            "email": "user@example.com",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=24)).isoformat(),
        }
        mock_profile_client.get_verification_token = AsyncMock(
            return_value=token_doc
        )
        mock_profile_client.update_profile = AsyncMock()
        mock_profile_client.delete_verification_token = AsyncMock()
        mock_profile_client.get_profile = AsyncMock(
            return_value={
                "display_name": "",
                "email_verified": True,
                "github_url": None,
                "linkedin_url": None,
                "profile_completed_at": None,
                "created_at": now.isoformat(),
                "password_hash": None,
                "country": None,
                "google_oauth_id": None,
            }
        )

        resp = await test_client.get("/api/v1/profile/verify/valid-token-123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Email verified successfully"
        assert body["email"] == "user@example.com"

    async def test_expired_token(self, test_client, mock_profile_client):
        """Expired token returns 410."""
        now = datetime.now(timezone.utc)
        token_doc = {
            "email": "user@example.com",
            "created_at": (now - timedelta(hours=48)).isoformat(),
            "expires_at": (now - timedelta(hours=24)).isoformat(),
        }
        mock_profile_client.get_verification_token = AsyncMock(
            return_value=token_doc
        )

        resp = await test_client.get("/api/v1/profile/verify/expired-token")

        assert resp.status_code == 410
        body = resp.json()
        assert "expired" in body["detail"].lower()

    async def test_invalid_token(self, test_client, mock_profile_client):
        """Non-existent token returns 404."""
        mock_profile_client.get_verification_token = AsyncMock(return_value=None)

        resp = await test_client.get("/api/v1/profile/verify/bad-token")

        assert resp.status_code == 404
        body = resp.json()
        assert "invalid" in body["detail"].lower()
