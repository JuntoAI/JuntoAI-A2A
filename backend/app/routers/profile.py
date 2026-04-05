"""Profile management endpoints.

Provides CRUD operations for user profiles, email verification,
and tier upgrade logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import get_profile_client
from app.models.profile import ProfileResponse, ProfileUpdateRequest
from app.services.email_verifier import (
    EmailVerifier,
    SESDeliveryError,
    TokenExpiredError,
    TokenNotFoundError,
)
from app.services.tier_calculator import (
    calculate_tier,
    get_daily_limit,
    is_profile_complete,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_profile_response(
    profile: dict, tier: int, daily_limit: int, token_balance: int
) -> ProfileResponse:
    """Build a ``ProfileResponse`` from a raw profile dict + tier info."""
    return ProfileResponse(
        display_name=profile.get("display_name", ""),
        email_verified=profile.get("email_verified", False),
        github_url=profile.get("github_url"),
        linkedin_url=profile.get("linkedin_url"),
        profile_completed_at=profile.get("profile_completed_at"),
        created_at=profile.get("created_at"),
        password_hash_set=profile.get("password_hash") is not None,
        country=profile.get("country"),
        google_oauth_id=profile.get("google_oauth_id"),
        tier=tier,
        daily_limit=daily_limit,
        token_balance=token_balance,
    )


async def _get_waitlist_token_balance(profile_client, email: str) -> int:
    """Read the current token_balance from the waitlist document.

    Returns the balance, defaulting to 20 (Tier 1) if the document
    doesn't exist or the field is missing.
    """
    email_key = email.lower().strip()

    if settings.RUN_MODE == "local":
        # SQLite: read from the waitlist table via a direct query
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
        # Firestore: access waitlist collection via the shared db
        waitlist_ref = profile_client._db.collection("waitlist").document(email_key)
        doc = await waitlist_ref.get()
        if doc.exists:
            return doc.to_dict().get("token_balance", 20)
        return 20


async def _update_waitlist_token_balance(
    profile_client, email: str, new_balance: int
) -> None:
    """Set the token_balance on the waitlist document."""
    email_key = email.lower().strip()

    if settings.RUN_MODE == "local":
        import aiosqlite

        db_path = settings.SQLITE_DB_PATH
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(
                "UPDATE waitlist SET token_balance = ? WHERE email = ?",
                (new_balance, email_key),
            )
            await conn.commit()
    else:
        waitlist_ref = profile_client._db.collection("waitlist").document(email_key)
        await waitlist_ref.update({"token_balance": new_balance})


# ---------------------------------------------------------------------------
# GET /profile/{email} — get-or-create profile
# ---------------------------------------------------------------------------


@router.get("/profile/{email}")
async def get_profile(email: str, profile_client=Depends(get_profile_client)):
    """Return the profile for *email*, creating one with defaults if needed."""
    profile = await profile_client.get_or_create_profile(email)

    tier = calculate_tier(
        profile.get("profile_completed_at"), profile.get("email_verified", False)
    )
    daily_limit = get_daily_limit(tier)
    token_balance = await _get_waitlist_token_balance(profile_client, email)

    return _build_profile_response(profile, tier, daily_limit, token_balance)


# ---------------------------------------------------------------------------
# PUT /profile/{email} — update profile fields
# ---------------------------------------------------------------------------


@router.put("/profile/{email}")
async def update_profile(
    email: str,
    body: ProfileUpdateRequest,
    profile_client=Depends(get_profile_client),
):
    """Validate and update profile fields.

    After updating, evaluates profile completeness. If the profile is
    newly complete (``profile_completed_at`` was null), sets the timestamp
    and upgrades the waitlist ``token_balance`` to ``max(current, 100)``.
    """
    # 1. Check profile exists
    existing = await profile_client.get_profile(email)
    if existing is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Profile not found for {email}"},
        )

    # 2. Build update dict from non-None fields
    update_fields: dict = {}
    if body.display_name is not None:
        update_fields["display_name"] = body.display_name
    if body.github_url is not None:
        update_fields["github_url"] = body.github_url
    if body.linkedin_url is not None:
        update_fields["linkedin_url"] = body.linkedin_url
    if body.country is not None:
        update_fields["country"] = body.country

    # 3. Apply update
    if update_fields:
        await profile_client.update_profile(email, update_fields)

    # 4. Re-read profile to evaluate completeness with latest data
    profile = await profile_client.get_profile(email)

    was_already_complete = existing.get("profile_completed_at") is not None
    now_complete = is_profile_complete(
        profile.get("display_name", ""),
        profile.get("email_verified", False),
        profile.get("github_url"),
        profile.get("linkedin_url"),
    )

    # 5. Tier upgrade if newly complete
    if now_complete and not was_already_complete:
        now_ts = datetime.now(timezone.utc)
        await profile_client.update_profile(
            email, {"profile_completed_at": now_ts}
        )
        profile["profile_completed_at"] = now_ts

        # Upgrade waitlist token_balance to max(current, 100)
        current_balance = await _get_waitlist_token_balance(profile_client, email)
        new_balance = max(current_balance, 100)
        if new_balance != current_balance:
            await _update_waitlist_token_balance(profile_client, email, new_balance)

    # 6. Compute tier and return
    tier = calculate_tier(
        profile.get("profile_completed_at"), profile.get("email_verified", False)
    )
    daily_limit = get_daily_limit(tier)
    token_balance = await _get_waitlist_token_balance(profile_client, email)

    return _build_profile_response(profile, tier, daily_limit, token_balance)


# ---------------------------------------------------------------------------
# POST /profile/{email}/verify-email — send verification email
# ---------------------------------------------------------------------------


@router.post("/profile/{email}/verify-email")
async def verify_email(
    email: str,
    profile_client=Depends(get_profile_client),
):
    """Generate a verification token and send a verification email."""
    verifier = EmailVerifier(profile_client)

    # Use the configured frontend URL for verification links
    base_url = settings.FRONTEND_URL.rstrip("/")

    try:
        token = await verifier.generate_and_send_verification(email, base_url)
    except SESDeliveryError:
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to send verification email. Please try again."},
        )

    return {"message": "Verification email sent", "token": token}


# ---------------------------------------------------------------------------
# GET /profile/verify/{token} — validate verification token
# ---------------------------------------------------------------------------


@router.get("/profile/verify/{token}")
async def verify_token(token: str, profile_client=Depends(get_profile_client)):
    """Validate a verification token and mark the email as verified.

    On success, upgrades the waitlist ``token_balance`` to
    ``max(current, 50)`` if ``profile_completed_at`` is still null
    (i.e. user hasn't already reached Tier 3).
    """
    verifier = EmailVerifier(profile_client)

    try:
        result = await verifier.verify_token(token)
    except TokenNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"detail": "Invalid verification link"},
        )
    except TokenExpiredError:
        return JSONResponse(
            status_code=410,
            content={"detail": "Verification link has expired", "resend": True},
        )

    email = result["email"]

    # Tier 2 upgrade: bump token_balance to max(current, 50)
    # only if profile hasn't already reached Tier 3
    profile = await profile_client.get_profile(email)
    if profile and profile.get("profile_completed_at") is None:
        current_balance = await _get_waitlist_token_balance(profile_client, email)
        new_balance = max(current_balance, 50)
        if new_balance != current_balance:
            await _update_waitlist_token_balance(profile_client, email, new_balance)

    return {"message": "Email verified successfully", "email": email}
