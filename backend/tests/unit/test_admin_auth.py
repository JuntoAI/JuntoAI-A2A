"""Unit tests for admin authentication, login, logout, and guards.

Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 9.1, 9.2, 9.4
"""

import os
import time
from unittest.mock import patch

import httpx
import pytest
from itsdangerous import URLSafeTimedSerializer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "test-admin-secret"
BASE_URL = "http://testserver"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_cookie(password: str = ADMIN_PASSWORD) -> str:
    """Create a properly signed admin_session cookie."""
    s = URLSafeTimedSerializer(password)
    return s.dumps("admin")


def _build_app_with_admin(password: str = ADMIN_PASSWORD, run_mode: str = "cloud"):
    """Build a fresh FastAPI app with admin routes registered.

    The main app conditionally registers admin routes based on
    settings.ADMIN_PASSWORD at import time. We patch the env vars
    and reload the module to get a clean app with the desired config.
    """
    import importlib

    with patch.dict(os.environ, {
        "ADMIN_PASSWORD": password,
        "RUN_MODE": run_mode,
        "ENVIRONMENT": "development",
    }):
        import app.config as config_mod
        importlib.reload(config_mod)

        import app.routers.admin as admin_mod
        importlib.reload(admin_mod)

        import app.main as main_mod
        importlib.reload(main_mod)

        return main_mod.app, admin_mod.rate_limiter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_app():
    """Provide a fresh app with admin routes registered (cloud mode)."""
    application, limiter = _build_app_with_admin(ADMIN_PASSWORD, "cloud")
    limiter._attempts.clear()
    yield application, limiter
    limiter._attempts.clear()


@pytest.fixture()
async def admin_client(admin_app):
    """Async httpx client against the admin-enabled app."""
    application, _ = admin_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url=BASE_URL,
    ) as client:
        yield client


@pytest.fixture()
def admin_limiter(admin_app):
    """Direct access to the rate limiter for the admin app."""
    _, limiter = admin_app
    return limiter


# ---------------------------------------------------------------------------
# Auth dependency tests (verify_admin_session)
# ---------------------------------------------------------------------------


class TestVerifyAdminSession:
    """Tests for the verify_admin_session dependency on authenticated endpoints."""

    async def test_missing_cookie_returns_401(self, admin_client):
        """Request without admin_session cookie → 401 Unauthorized."""
        resp = await admin_client.post("/api/v1/admin/logout")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"

    async def test_invalid_cookie_returns_401(self, admin_client):
        """Request with tampered/garbage cookie → 401 Unauthorized."""
        resp = await admin_client.post(
            "/api/v1/admin/logout",
            cookies={"admin_session": "totally-bogus-value"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"

    async def test_wrong_secret_cookie_returns_401(self, admin_client):
        """Cookie signed with a different secret → 401 Unauthorized."""
        bad_cookie = _make_valid_cookie(password="wrong-secret")
        resp = await admin_client.post(
            "/api/v1/admin/logout",
            cookies={"admin_session": bad_cookie},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"

    async def test_expired_cookie_returns_401(self, admin_app):
        """Cookie older than 8 hours → 401 Unauthorized."""
        application, _ = admin_app
        cookie = _make_valid_cookie()

        # Fast-forward time by >8 hours so itsdangerous considers it expired
        with patch("itsdangerous.timed.time") as mock_time:
            mock_time.return_value = time.time() + 28801  # 8h + 1s
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url=BASE_URL,
            ) as client:
                resp = await client.post(
                    "/api/v1/admin/logout",
                    cookies={"admin_session": cookie},
                )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"

    async def test_valid_cookie_passes(self, admin_client):
        """Request with a valid, non-expired cookie → endpoint executes (200)."""
        cookie = _make_valid_cookie()
        resp = await admin_client.post(
            "/api/v1/admin/logout",
            cookies={"admin_session": cookie},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Login endpoint tests (POST /admin/login)
# ---------------------------------------------------------------------------


class TestAdminLogin:
    """Tests for POST /api/v1/admin/login."""

    async def test_correct_password_returns_200_with_cookie(self, admin_client):
        """Correct password → 200 + admin_session cookie set."""
        resp = await admin_client.post(
            "/api/v1/admin/login",
            json={"password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Logged in"

        # Verify the cookie is set in the response
        cookie_header = resp.headers.get("set-cookie", "")
        assert "admin_session=" in cookie_header
        assert "httponly" in cookie_header.lower()
        assert "samesite=strict" in cookie_header.lower()

    async def test_wrong_password_returns_401(self, admin_client):
        """Wrong password → 401 Invalid password."""
        resp = await admin_client.post(
            "/api/v1/admin/login",
            json={"password": "wrong-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid password"

    async def test_empty_password_returns_422(self, admin_client):
        """Empty password string → 422 (Pydantic min_length=1 validation)."""
        resp = await admin_client.post(
            "/api/v1/admin/login",
            json={"password": ""},
        )
        assert resp.status_code == 422

    async def test_rate_limited_returns_429(self, admin_client, admin_limiter):
        """More than 10 attempts from same IP → 429."""
        # Fire 10 wrong-password attempts to fill the rate limiter
        for _ in range(10):
            await admin_client.post(
                "/api/v1/admin/login",
                json={"password": "wrong"},
            )

        # 11th attempt should be rate limited
        resp = await admin_client.post(
            "/api/v1/admin/login",
            json={"password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Too many login attempts"

    async def test_correct_password_also_rate_limited(self, admin_client, admin_limiter):
        """Even correct password is rejected when rate limited."""
        for _ in range(10):
            await admin_client.post(
                "/api/v1/admin/login",
                json={"password": "wrong"},
            )

        resp = await admin_client.post(
            "/api/v1/admin/login",
            json={"password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Logout endpoint tests (POST /admin/logout)
# ---------------------------------------------------------------------------


class TestAdminLogout:
    """Tests for POST /api/v1/admin/logout."""

    async def test_logout_clears_cookie_and_returns_200(self, admin_client):
        """Valid session → 200 + admin_session cookie cleared."""
        cookie = _make_valid_cookie()
        resp = await admin_client.post(
            "/api/v1/admin/logout",
            cookies={"admin_session": cookie},
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Logged out"

        # Cookie should be deleted (max-age=0 or expires in the past)
        cookie_header = resp.headers.get("set-cookie", "")
        assert "admin_session=" in cookie_header
        assert 'max-age=0' in cookie_header.lower() or "expires=" in cookie_header.lower()

    async def test_logout_without_cookie_returns_401(self, admin_client):
        """No session cookie → 401 (auth dependency rejects)."""
        resp = await admin_client.post("/api/v1/admin/logout")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Cloud-only guard tests (RUN_MODE=local → 503)
# ---------------------------------------------------------------------------


class TestCloudOnlyGuard:
    """Tests for require_cloud_mode dependency."""

    async def test_login_returns_503_in_local_mode(self):
        """POST /admin/login → 503 when RUN_MODE=local."""
        application, _ = _build_app_with_admin(ADMIN_PASSWORD, "local")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url=BASE_URL,
        ) as client:
            resp = await client.post(
                "/api/v1/admin/login",
                json={"password": ADMIN_PASSWORD},
            )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Admin dashboard is not available in local mode"

    async def test_logout_returns_503_in_local_mode(self):
        """POST /admin/logout → 503 when RUN_MODE=local."""
        application, _ = _build_app_with_admin(ADMIN_PASSWORD, "local")
        cookie = _make_valid_cookie()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url=BASE_URL,
        ) as client:
            resp = await client.post(
                "/api/v1/admin/logout",
                cookies={"admin_session": cookie},
            )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Admin dashboard is not available in local mode"


# ---------------------------------------------------------------------------
# Conditional registration test (ADMIN_PASSWORD empty → 404)
# ---------------------------------------------------------------------------


class TestConditionalRegistration:
    """Tests for admin router conditional registration in main.py."""

    async def test_admin_routes_not_registered_when_password_empty(self):
        """When ADMIN_PASSWORD is empty, admin routes should not exist (404)."""
        application, _ = _build_app_with_admin(password="", run_mode="cloud")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url=BASE_URL,
        ) as client:
            resp = await client.post(
                "/api/v1/admin/login",
                json={"password": "anything"},
            )
        assert resp.status_code == 404
