"""Authentication endpoints — password login, Google OAuth link/login."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import get_profile_client
from app.models.auth import (
    CheckEmailResponse,
    GoogleTokenRequest,
    LoginRequest,
    LoginResponse,
    SetPasswordRequest,
)
from app.services.auth_service import (
    check_google_oauth_id_unique,
    hash_password,
    validate_google_token,
    verify_password,
)
from app.services.tier_calculator import calculate_tier, get_daily_limit

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_waitlist_token_balance(profile_client, email: str) -> int:
    """Read the current token_balance from the waitlist document."""
    email_key = email.lower().strip()

    if settings.RUN_MODE == "local":
        import aiosqlite

        db_path = settings.SQLITE_DB_PATH
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute(
                "SELECT token_balance FROM waitlist WHERE email = ?",
                (email_key,),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 20
    else:
        waitlist_ref = profile_client._db.collection("waitlist").document(email_key)
        doc = await waitlist_ref.get()
        if doc.exists:
            return doc.to_dict().get("token_balance", 20)
        return 20


def _build_login_response(
    email: str, profile: dict, token_balance: int
) -> LoginResponse:
    """Build a ``LoginResponse`` from profile data."""
    tier = calculate_tier(
        profile.get("profile_completed_at"), profile.get("email_verified", False)
    )
    daily_limit = get_daily_limit(tier)
    return LoginResponse(
        email=email,
        tier=tier,
        daily_limit=daily_limit,
        token_balance=token_balance,
    )


# ---------------------------------------------------------------------------
# POST /auth/set-password
# ---------------------------------------------------------------------------


@router.post("/auth/set-password")
async def set_password(
    body: SetPasswordRequest,
    profile_client=Depends(get_profile_client),
):
    """Hash the password with bcrypt and store it on the profile."""
    profile = await profile_client.get_or_create_profile(body.email)

    hashed = hash_password(body.password)
    await profile_client.update_password_hash(body.email, hashed)

    return {"message": "Password set successfully"}


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post("/auth/login")
async def login(
    body: LoginRequest,
    profile_client=Depends(get_profile_client),
):
    """Verify password and return session data."""
    profile = await profile_client.get_profile(body.email)
    if profile is None:
        return JSONResponse(
            status_code=400,
            content={"detail": "No password set for this account"},
        )

    stored_hash = profile.get("password_hash")
    if not stored_hash:
        return JSONResponse(
            status_code=400,
            content={"detail": "No password set for this account"},
        )

    if not verify_password(body.password, stored_hash):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid password"},
        )

    token_balance = await _get_waitlist_token_balance(profile_client, body.email)
    return _build_login_response(body.email, profile, token_balance)


# ---------------------------------------------------------------------------
# GET /auth/check-email/{email}
# ---------------------------------------------------------------------------


@router.get("/auth/check-email/{email}")
async def check_email(
    email: str,
    profile_client=Depends(get_profile_client),
):
    """Return whether the email has a password set."""
    profile = await profile_client.get_profile(email)
    has_password = bool(profile and profile.get("password_hash"))
    return CheckEmailResponse(has_password=has_password)


# ---------------------------------------------------------------------------
# POST /auth/google/link
# ---------------------------------------------------------------------------


@router.post("/auth/google/link")
async def google_link(
    body: GoogleTokenRequest,
    profile_client=Depends(get_profile_client),
):
    """Validate Google ID token, check uniqueness, store google_oauth_id."""
    try:
        claims = validate_google_token(body.id_token)
    except ValueError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid Google ID token"},
        )

    google_oauth_id = claims["sub"]
    email = body.email
    if not email:
        return JSONResponse(
            status_code=400,
            content={"detail": "Email is required for linking"},
        )

    # Ensure profile exists
    await profile_client.get_or_create_profile(email)

    # Check uniqueness
    is_unique = await check_google_oauth_id_unique(
        google_oauth_id, email, profile_client
    )
    if not is_unique:
        return JSONResponse(
            status_code=409,
            content={"detail": "Google account already linked to another profile"},
        )

    await profile_client.set_google_oauth_id(email, google_oauth_id)
    return {
        "google_oauth_id": google_oauth_id,
        "google_email": claims.get("email"),
    }


# ---------------------------------------------------------------------------
# POST /auth/google/login
# ---------------------------------------------------------------------------


@router.post("/auth/google/login")
async def google_login(
    body: GoogleTokenRequest,
    profile_client=Depends(get_profile_client),
):
    """Validate Google ID token, look up profile by google_oauth_id, return session."""
    try:
        claims = validate_google_token(body.id_token)
    except ValueError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid Google ID token"},
        )

    google_oauth_id = claims["sub"]
    profile = await profile_client.get_profile_by_google_oauth_id(google_oauth_id)
    if profile is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "No linked account found for this Google account"},
        )

    email = profile.get("_email", "")
    token_balance = await _get_waitlist_token_balance(profile_client, email)
    return _build_login_response(email, profile, token_balance)


# ---------------------------------------------------------------------------
# DELETE /auth/google/link/{email}
# ---------------------------------------------------------------------------


@router.delete("/auth/google/link/{email}")
async def google_unlink(
    email: str,
    profile_client=Depends(get_profile_client),
):
    """Remove google_oauth_id from the profile."""
    profile = await profile_client.get_profile(email)
    if profile is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Profile not found for {email}"},
        )

    await profile_client.clear_google_oauth_id(email)
    return {"message": "Google account unlinked successfully"}
