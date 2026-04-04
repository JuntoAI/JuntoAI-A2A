"""Property-based tests for auth validation, bcrypt round-trip, and Google OAuth uniqueness.

Tests cover Properties 15, 16, and 18 from the design document.
"""

from __future__ import annotations

import asyncio
import string
import tempfile
import os

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from app.models.auth import SetPasswordRequest
from app.services.auth_service import hash_password, verify_password, check_google_oauth_id_unique
from app.db.profile_client import SQLiteProfileClient


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 15: Password length validation
# ---------------------------------------------------------------------------


@given(password=st.text(min_size=0, max_size=200))
@settings(max_examples=100)
def test_password_length_validation(password: str):
    """**Validates: Requirements 11.2, 11.4**

    For any string, the password validator accepts iff 8 <= len(s) <= 128.
    Strings outside this range are rejected with a validation error.
    """
    should_accept = 8 <= len(password) <= 128

    if should_accept:
        req = SetPasswordRequest(email="test@test.com", password=password)
        assert req.password == password
    else:
        with pytest.raises(ValidationError):
            SetPasswordRequest(email="test@test.com", password=password)


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 16: Bcrypt password hash round-trip
# ---------------------------------------------------------------------------

# Printable ASCII strategy to avoid bcrypt encoding issues
_printable_ascii = st.text(
    alphabet=string.printable.strip(),  # printable minus whitespace-only chars
    min_size=8,
    max_size=128,
).filter(lambda s: len(s) >= 8)


@given(password=_printable_ascii)
@settings(max_examples=100, deadline=None)
def test_bcrypt_hash_round_trip(password: str):
    """**Validates: Requirements 11.3, 11.7, 11.8**

    For any valid password (8-128 printable ASCII chars):
    1. Hashing then verifying the original password returns True.
    2. Verifying a different password against the same hash returns False.
    """
    hashed = hash_password(password)

    # Original password must match
    assert verify_password(password, hashed) is True

    # A different password must NOT match — ensure it differs within the
    # first 72 bytes (bcrypt's input limit) so the comparison is meaningful.
    if len(password) < 72:
        different = password + "X"
    else:
        # Flip a character within the first 72 bytes
        different = ("X" if password[0] != "X" else "Y") + password[1:]
    assert verify_password(different, hashed) is False


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 18: Google OAuth ID uniqueness constraint
# ---------------------------------------------------------------------------

# Strategy for distinct email pairs
_email = st.from_regex(r"[a-z]{3,10}@[a-z]{3,8}\.com", fullmatch=True)


@given(
    email1=_email,
    email2=_email,
    google_oauth_id=st.text(min_size=5, max_size=30, alphabet=string.ascii_lowercase + string.digits),
)
@settings(max_examples=100)
def test_google_oauth_id_uniqueness(email1: str, email2: str, google_oauth_id: str):
    """**Validates: Requirements 13.5**

    For two distinct emails and one google_oauth_id: linking to the first email
    succeeds, then checking uniqueness for the second email returns False (conflict).
    """
    assume(email1 != email2)

    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            client = SQLiteProfileClient(db_path=db_path)

            # Create both profiles
            await client.get_or_create_profile(email1)
            await client.get_or_create_profile(email2)

            # Link google_oauth_id to first email
            await client.set_google_oauth_id(email1, google_oauth_id)

            # Uniqueness check for the SAME email should pass (it's their own)
            is_unique_same = await check_google_oauth_id_unique(
                google_oauth_id, email1, client
            )
            assert is_unique_same is True

            # Uniqueness check for a DIFFERENT email should fail (conflict)
            is_unique_different = await check_google_oauth_id_unique(
                google_oauth_id, email2, client
            )
            assert is_unique_different is False

    asyncio.run(_run())
