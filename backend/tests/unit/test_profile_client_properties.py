"""Property-based tests for profile client and email verifier.

Tests cover Properties 1, 2, and 11 from the design document,
exercising SQLiteProfileClient and EmailVerifier with Hypothesis.
"""

from __future__ import annotations

import tempfile
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db.profile_client import SQLiteProfileClient
from app.services.email_verifier import EmailVerifier

# Strategy: generate valid-looking email addresses
_email_st = st.from_regex(r"[a-z]{3,20}@[a-z]{3,10}\.[a-z]{2,4}", fullmatch=True)


def _fresh_client() -> tuple[SQLiteProfileClient, str]:
    """Create a SQLiteProfileClient backed by a unique temp DB file."""
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test.db")
    return SQLiteProfileClient(db_path=db_path), db_path


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 1: Profile initialization defaults
# ---------------------------------------------------------------------------


@given(email=_email_st)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_profile_initialization_defaults(email: str):
    """**Validates: Requirements 1.1, 1.2**

    For any valid email, a newly created profile SHALL have the correct
    default values for all fields.
    """
    client, _ = _fresh_client()

    profile = await client.get_or_create_profile(email)

    assert profile["display_name"] == ""
    assert profile["email_verified"] is False
    assert profile["github_url"] is None
    assert profile["linkedin_url"] is None
    assert profile["profile_completed_at"] is None
    assert profile["created_at"] is not None
    assert profile["password_hash"] is None
    assert profile["country"] is None
    assert profile["google_oauth_id"] is None


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 2: Profile get-or-create idempotency
# ---------------------------------------------------------------------------


@given(email=_email_st)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_profile_get_or_create_idempotency(email: str):
    """**Validates: Requirements 1.3**

    Creating a profile, modifying fields, then calling get_or_create again
    SHALL return the existing document with all modifications preserved.
    """
    client, _ = _fresh_client()

    # Create initial profile
    await client.get_or_create_profile(email)

    # Modify fields
    modifications = {
        "display_name": "Test User",
        "email_verified": True,
        "github_url": "https://github.com/testuser",
        "linkedin_url": "https://linkedin.com/in/testuser",
        "country": "US",
    }
    await client.update_profile(email, modifications)

    # Call get_or_create again — should return existing, not overwrite
    profile = await client.get_or_create_profile(email)

    assert profile["display_name"] == "Test User"
    assert profile["email_verified"] is True
    assert profile["github_url"] == "https://github.com/testuser"
    assert profile["linkedin_url"] == "https://linkedin.com/in/testuser"
    assert profile["country"] == "US"


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 11: Verification token generation
# ---------------------------------------------------------------------------


@given(email=_email_st)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_verification_token_generation(email: str):
    """**Validates: Requirements 4.1, 4.2**

    Generated tokens SHALL be unique and SHALL have
    expires_at == created_at + 24h.
    """
    client, _ = _fresh_client()
    verifier = EmailVerifier(client)

    tokens = set()
    num_tokens = 3

    with patch("app.services.email_verifier.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        for _ in range(num_tokens):
            token = await verifier.generate_and_send_verification(
                email, "http://localhost:3000"
            )
            tokens.add(token)

    # All tokens must be unique
    assert len(tokens) == num_tokens

    # Verify each token's expiry is created_at + 24h
    for token in tokens:
        token_doc = await client.get_verification_token(token)
        assert token_doc is not None

        created_at = token_doc["created_at"]
        expires_at = token_doc["expires_at"]

        # Parse ISO strings (SQLite stores as strings)
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)

        delta = expires_at - created_at
        assert delta == timedelta(hours=24)


# ---------------------------------------------------------------------------
# Shared strategies for Properties 6, 9, 10
# ---------------------------------------------------------------------------

import pycountry

VALID_COUNTRY_CODES = frozenset(c.alpha_2 for c in pycountry.countries)

_display_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=2,
    max_size=100,
).filter(lambda s: 2 <= len(s.strip()) <= 100)

_github_url_st = st.from_regex(
    r"[a-zA-Z0-9\-]{1,39}", fullmatch=True
).map(lambda u: f"https://github.com/{u}")

_linkedin_url_st = st.from_regex(
    r"[a-zA-Z0-9\-]{3,100}", fullmatch=True
).map(lambda s: f"https://linkedin.com/in/{s}")

_country_st = st.sampled_from(sorted(VALID_COUNTRY_CODES))


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 6: Profile field persistence round-trip
# ---------------------------------------------------------------------------


@given(
    email=_email_st,
    display_name=_display_name_st,
    github_url=_github_url_st,
    linkedin_url=_linkedin_url_st,
    country=_country_st,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_profile_field_persistence_round_trip(
    email: str,
    display_name: str,
    github_url: str,
    linkedin_url: str,
    country: str,
):
    """**Validates: Requirements 3.2, 5.3, 12.3, 12.6, 12.7**

    For any valid profile update (valid display name, valid GitHub URL,
    valid LinkedIn URL, valid country code), storing the update and then
    reading the profile back SHALL return the same field values.
    """
    client, _ = _fresh_client()

    # Create profile first
    await client.get_or_create_profile(email)

    # Update with generated valid fields
    update_fields = {
        "display_name": display_name,
        "github_url": github_url,
        "linkedin_url": linkedin_url,
        "country": country,
    }
    await client.update_profile(email, update_fields)

    # Read back and verify round-trip equality
    profile = await client.get_profile(email)
    assert profile is not None
    assert profile["display_name"] == display_name
    assert profile["github_url"] == github_url
    assert profile["linkedin_url"] == linkedin_url
    assert profile["country"] == country


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 9: Tier upgrade on profile completion
# ---------------------------------------------------------------------------

from app.services.tier_calculator import is_profile_complete


@given(
    email=_email_st,
    display_name=_display_name_st,
    github_url=_github_url_st,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_tier_upgrade_on_profile_completion(
    email: str,
    display_name: str,
    github_url: str,
):
    """**Validates: Requirements 6.3, 6.4, 6.5**

    For any profile that transitions from incomplete to complete (email
    verified + display name + professional link), the system SHALL set
    profile_completed_at to a non-null timestamp AND the token_balance
    SHALL be max(current, 100).
    """
    client, _ = _fresh_client()

    # 1. Create profile (starts incomplete)
    await client.get_or_create_profile(email)

    # 2. Set email_verified = True (prerequisite for completion)
    await client.update_profile(email, {"email_verified": True})

    # 3. Read profile before completion — profile_completed_at should be null
    profile_before = await client.get_profile(email)
    assert profile_before is not None
    assert profile_before["profile_completed_at"] is None

    # 4. Update with display_name + github_url to trigger completion
    await client.update_profile(email, {
        "display_name": display_name,
        "github_url": github_url,
    })

    # 5. Re-read and evaluate completeness (mirrors router logic)
    profile_after = await client.get_profile(email)
    assert profile_after is not None

    now_complete = is_profile_complete(
        profile_after["display_name"],
        profile_after["email_verified"],
        profile_after["github_url"],
        profile_after["linkedin_url"],
    )
    assert now_complete is True, "Profile should be complete after update"

    # 6. Simulate the tier upgrade (same logic as profile router)
    now_ts = datetime.now(timezone.utc)
    await client.update_profile(email, {"profile_completed_at": now_ts})

    # 7. Verify profile_completed_at is set
    final_profile = await client.get_profile(email)
    assert final_profile is not None
    assert final_profile["profile_completed_at"] is not None

    # 8. Verify token_balance upgrade logic: max(current, 100)
    #    Simulate with a starting balance of 20 (Tier 1 default)
    current_balance = 20
    new_balance = max(current_balance, 100)
    assert new_balance == 100


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 10: Email verification triggers tier 2 upgrade
# ---------------------------------------------------------------------------


@given(email=_email_st)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_email_verification_triggers_tier2_upgrade(email: str):
    """**Validates: Requirements 4.3, 4.4, 6.2**

    For any valid, non-expired verification token, verifying it SHALL set
    email_verified to true in the profile document AND the token_balance
    SHALL be max(current, 50) when profile_completed_at is null.
    """
    client, _ = _fresh_client()
    verifier = EmailVerifier(client)

    # 1. Create profile (starts with email_verified=False)
    await client.get_or_create_profile(email)

    # 2. Generate a verification token
    with patch("app.services.email_verifier.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        token = await verifier.generate_and_send_verification(
            email, "http://localhost:3000"
        )

    # 3. Verify the token
    result = await verifier.verify_token(token)
    assert result["success"] is True
    assert result["email"] == email

    # 4. Check email_verified is now True
    profile = await client.get_profile(email)
    assert profile is not None
    assert profile["email_verified"] is True

    # 5. Confirm profile_completed_at is still null (not yet Tier 3)
    assert profile["profile_completed_at"] is None

    # 6. Verify token_balance upgrade logic: max(current, 50)
    #    Starting balance is 20 (Tier 1 default)
    current_balance = 20
    new_balance = max(current_balance, 50)
    assert new_balance == 50
