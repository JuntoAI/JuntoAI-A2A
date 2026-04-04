"""Integration tests for auth endpoints.

Validates: Requirements 9.7, 9.8, 9.9, 9.10, 9.11, 9.12,
           11.3, 11.7, 11.8, 11.10, 11.11,
           13.3, 13.4, 13.5, 13.7, 13.8, 13.9, 13.10
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _force_cloud_mode():
    """Force RUN_MODE=cloud so waitlist helpers use the mocked Firestore path."""
    with patch("app.routers.auth.settings") as mock_settings:
        mock_settings.RUN_MODE = "cloud"
        yield mock_settings


# ---------------------------------------------------------------------------
# POST /api/v1/auth/set-password
# ---------------------------------------------------------------------------


class TestSetPassword:
    """POST /api/v1/auth/set-password — hash and store password."""

    async def test_valid_password(self, test_client, mock_profile_client):
        """Valid password (8-128 chars) is hashed and stored."""
        mock_profile_client.get_or_create_profile = AsyncMock(
            return_value={"password_hash": None}
        )
        mock_profile_client.update_password_hash = AsyncMock()

        resp = await test_client.post(
            "/api/v1/auth/set-password",
            json={"email": "user@example.com", "password": "securepass123"},
        )

        assert resp.status_code == 200
        assert resp.json()["message"] == "Password set successfully"
        mock_profile_client.update_password_hash.assert_awaited_once()

    async def test_invalid_password_too_short(self, test_client, mock_profile_client):
        """Password shorter than 8 chars returns 422."""
        resp = await test_client.post(
            "/api/v1/auth/set-password",
            json={"email": "user@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    async def test_invalid_password_too_long(self, test_client, mock_profile_client):
        """Password longer than 128 chars returns 422."""
        resp = await test_client.post(
            "/api/v1/auth/set-password",
            json={"email": "user@example.com", "password": "x" * 129},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    """POST /api/v1/auth/login — password verification."""

    async def test_correct_password(self, test_client, mock_profile_client):
        """Correct password returns session data with tier info."""
        from app.services.auth_service import hash_password

        hashed = hash_password("correctpass1")
        mock_profile_client.get_profile = AsyncMock(
            return_value={
                "password_hash": hashed,
                "email_verified": False,
                "profile_completed_at": None,
            }
        )

        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "correctpass1"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "user@example.com"
        assert body["tier"] == 1
        assert body["daily_limit"] == 20
        assert "token_balance" in body

    async def test_wrong_password_returns_401(
        self, test_client, mock_profile_client
    ):
        """Wrong password returns 401."""
        from app.services.auth_service import hash_password

        hashed = hash_password("correctpass1")
        mock_profile_client.get_profile = AsyncMock(
            return_value={
                "password_hash": hashed,
                "email_verified": False,
                "profile_completed_at": None,
            }
        )

        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "wrongpassword"},
        )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid password"

    async def test_no_password_set_returns_400(
        self, test_client, mock_profile_client
    ):
        """Login attempt with no password set returns 400."""
        mock_profile_client.get_profile = AsyncMock(
            return_value={
                "password_hash": None,
                "email_verified": False,
                "profile_completed_at": None,
            }
        )

        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "anypassword1"},
        )

        assert resp.status_code == 400
        assert "no password" in resp.json()["detail"].lower()

    async def test_no_profile_returns_400(self, test_client, mock_profile_client):
        """Login attempt with no profile at all returns 400."""
        mock_profile_client.get_profile = AsyncMock(return_value=None)

        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "anypassword1"},
        )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/v1/auth/check-email/{email}
# ---------------------------------------------------------------------------


class TestCheckEmail:
    """GET /api/v1/auth/check-email/{email} — has_password check."""

    async def test_has_password_true(self, test_client, mock_profile_client):
        """Profile with password_hash returns has_password=true."""
        mock_profile_client.get_profile = AsyncMock(
            return_value={"password_hash": "$2b$12$somehash"}
        )

        resp = await test_client.get(
            "/api/v1/auth/check-email/user@example.com"
        )

        assert resp.status_code == 200
        assert resp.json()["has_password"] is True

    async def test_has_password_false_no_hash(
        self, test_client, mock_profile_client
    ):
        """Profile without password_hash returns has_password=false."""
        mock_profile_client.get_profile = AsyncMock(
            return_value={"password_hash": None}
        )

        resp = await test_client.get(
            "/api/v1/auth/check-email/user@example.com"
        )

        assert resp.status_code == 200
        assert resp.json()["has_password"] is False

    async def test_has_password_false_no_profile(
        self, test_client, mock_profile_client
    ):
        """No profile at all returns has_password=false."""
        mock_profile_client.get_profile = AsyncMock(return_value=None)

        resp = await test_client.get(
            "/api/v1/auth/check-email/nobody@example.com"
        )

        assert resp.status_code == 200
        assert resp.json()["has_password"] is False


# ---------------------------------------------------------------------------
# POST /api/v1/auth/google/link
# ---------------------------------------------------------------------------


class TestGoogleLink:
    """POST /api/v1/auth/google/link — link Google account."""

    async def test_valid_token_links_account(
        self, test_client, mock_profile_client
    ):
        """Valid Google token links the account successfully."""
        mock_profile_client.get_or_create_profile = AsyncMock(return_value={})
        mock_profile_client.get_profile_by_google_oauth_id = AsyncMock(
            return_value=None
        )
        mock_profile_client.set_google_oauth_id = AsyncMock()

        with patch("app.routers.auth.validate_google_token") as mock_validate:
            mock_validate.return_value = {
                "sub": "google-sub-123",
                "email": "user@gmail.com",
            }

            resp = await test_client.post(
                "/api/v1/auth/google/link",
                json={
                    "id_token": "valid-google-token",
                    "email": "user@example.com",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["google_oauth_id"] == "google-sub-123"
        assert body["google_email"] == "user@gmail.com"

    async def test_409_conflict_when_already_linked(
        self, test_client, mock_profile_client
    ):
        """Google account already linked to another profile returns 409."""
        mock_profile_client.get_or_create_profile = AsyncMock(return_value={})
        mock_profile_client.get_profile_by_google_oauth_id = AsyncMock(
            return_value={"_email": "other@example.com"}
        )

        with patch("app.routers.auth.validate_google_token") as mock_validate:
            mock_validate.return_value = {
                "sub": "google-sub-123",
                "email": "user@gmail.com",
            }

            resp = await test_client.post(
                "/api/v1/auth/google/link",
                json={
                    "id_token": "valid-google-token",
                    "email": "user@example.com",
                },
            )

        assert resp.status_code == 409
        assert "already linked" in resp.json()["detail"].lower()

    async def test_invalid_google_token_returns_401(
        self, test_client, mock_profile_client
    ):
        """Invalid Google token returns 401."""
        with patch("app.routers.auth.validate_google_token") as mock_validate:
            mock_validate.side_effect = ValueError("Invalid Google ID token")

            resp = await test_client.post(
                "/api/v1/auth/google/link",
                json={
                    "id_token": "bad-token",
                    "email": "user@example.com",
                },
            )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/auth/google/login
# ---------------------------------------------------------------------------


class TestGoogleLogin:
    """POST /api/v1/auth/google/login — Google OAuth login."""

    async def test_valid_linked_account(self, test_client, mock_profile_client):
        """Valid Google token with linked account returns session data."""
        mock_profile_client.get_profile_by_google_oauth_id = AsyncMock(
            return_value={
                "_email": "user@example.com",
                "email_verified": True,
                "profile_completed_at": None,
            }
        )

        with patch("app.routers.auth.validate_google_token") as mock_validate:
            mock_validate.return_value = {
                "sub": "google-sub-123",
                "email": "user@gmail.com",
            }

            resp = await test_client.post(
                "/api/v1/auth/google/login",
                json={"id_token": "valid-google-token"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "user@example.com"
        assert body["tier"] == 2
        assert body["daily_limit"] == 50

    async def test_404_no_linked_account(self, test_client, mock_profile_client):
        """Google login with no linked account returns 404."""
        mock_profile_client.get_profile_by_google_oauth_id = AsyncMock(
            return_value=None
        )

        with patch("app.routers.auth.validate_google_token") as mock_validate:
            mock_validate.return_value = {
                "sub": "google-sub-unknown",
                "email": "unknown@gmail.com",
            }

            resp = await test_client.post(
                "/api/v1/auth/google/login",
                json={"id_token": "valid-google-token"},
            )

        assert resp.status_code == 404
        assert "no linked account" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# DELETE /api/v1/auth/google/link/{email}
# ---------------------------------------------------------------------------


class TestGoogleUnlink:
    """DELETE /api/v1/auth/google/link/{email} — unlink Google account."""

    async def test_unlink_success(self, test_client, mock_profile_client):
        """Unlinking a Google account succeeds."""
        mock_profile_client.get_profile = AsyncMock(
            return_value={"google_oauth_id": "google-sub-123"}
        )
        mock_profile_client.clear_google_oauth_id = AsyncMock()

        resp = await test_client.delete(
            "/api/v1/auth/google/link/user@example.com"
        )

        assert resp.status_code == 200
        assert "unlinked" in resp.json()["message"].lower()
        mock_profile_client.clear_google_oauth_id.assert_awaited_once()

    async def test_unlink_404_no_profile(self, test_client, mock_profile_client):
        """Unlinking from non-existent profile returns 404."""
        mock_profile_client.get_profile = AsyncMock(return_value=None)

        resp = await test_client.delete(
            "/api/v1/auth/google/link/nobody@example.com"
        )

        assert resp.status_code == 404
