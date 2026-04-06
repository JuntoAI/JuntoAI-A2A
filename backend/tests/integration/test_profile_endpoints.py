"""Integration tests for profile endpoints.

Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 12.6, 12.7
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_verifier import SESDeliveryError


@pytest.fixture(autouse=True)
def _force_cloud_mode():
    """Force RUN_MODE=cloud so waitlist helpers use the mocked Firestore path."""
    with patch("app.routers.profile.settings") as mock_settings:
        mock_settings.RUN_MODE = "cloud"
        mock_settings.FRONTEND_URL = "http://localhost:3000"
        yield mock_settings


# ---------------------------------------------------------------------------
# GET /api/v1/profile/{email}
# ---------------------------------------------------------------------------


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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


# ---------------------------------------------------------------------------
# Additional coverage: email verification request edge cases
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestVerifyEmailEdgeCases:
    """POST /api/v1/profile/{email}/verify-email — additional paths."""

    async def test_ses_failure_returns_502(
        self, test_client, mock_profile_client, _force_cloud_mode
    ):
        """SES delivery failure returns 502 with retry message."""
        _force_cloud_mode.RUN_MODE = "cloud"
        mock_profile_client.create_verification_token = AsyncMock()

        with patch(
            "app.routers.profile.EmailVerifier.generate_and_send_verification",
            new_callable=AsyncMock,
            side_effect=SESDeliveryError("user@example.com"),
        ):
            resp = await test_client.post(
                "/api/v1/profile/user@example.com/verify-email"
            )

        assert resp.status_code == 502
        body = resp.json()
        assert "failed to send" in body["detail"].lower()

    async def test_verify_email_returns_token(
        self, test_client, mock_profile_client, _force_cloud_mode
    ):
        """Cloud-mode verify-email returns a token on success."""
        _force_cloud_mode.RUN_MODE = "cloud"
        mock_profile_client.create_verification_token = AsyncMock()

        with patch(
            "app.routers.profile.EmailVerifier.generate_and_send_verification",
            new_callable=AsyncMock,
            return_value="fake-token-uuid",
        ):
            resp = await test_client.post(
                "/api/v1/profile/user@example.com/verify-email"
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["token"] == "fake-token-uuid"
        assert body["message"] == "Verification email sent"


# ---------------------------------------------------------------------------
# Additional coverage: profile creation on first access
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestProfileCreationOnFirstAccess:
    """GET /api/v1/profile/{email} — profile auto-creation behaviour."""

    async def test_first_access_creates_profile_and_reads_waitlist_balance(
        self, test_client, mock_profile_client
    ):
        """First access creates a profile via get_or_create_profile and reads token_balance from waitlist."""
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

        resp = await test_client.get("/api/v1/profile/brand-new@example.com")

        assert resp.status_code == 200
        body = resp.json()
        # Profile was auto-created with defaults
        assert body["display_name"] == ""
        assert body["email_verified"] is False
        assert body["tier"] == 1
        assert body["daily_limit"] == 20
        # token_balance comes from the mocked waitlist doc (100 in conftest)
        assert body["token_balance"] == 100
        # Verify get_or_create_profile was called with the email
        mock_profile_client.get_or_create_profile.assert_awaited_once_with(
            "brand-new@example.com"
        )

    async def test_first_access_with_missing_waitlist_doc_gets_default_balance(
        self, test_client, mock_profile_client
    ):
        """When waitlist doc doesn't exist, token_balance defaults to 20."""
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

        # Override the waitlist doc mock to simulate non-existent doc
        waitlist_doc = MagicMock()
        waitlist_doc.exists = False
        waitlist_ref = MagicMock()
        waitlist_ref.get = AsyncMock(return_value=waitlist_doc)
        mock_profile_client._db.collection.return_value.document.return_value = (
            waitlist_ref
        )

        resp = await test_client.get("/api/v1/profile/no-waitlist@example.com")

        assert resp.status_code == 200
        body = resp.json()
        assert body["token_balance"] == 20
        assert body["tier"] == 1
