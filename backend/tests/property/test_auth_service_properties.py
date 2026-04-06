"""Property-based tests for auth service password hashing.

Feature: 155_test-coverage-hardening
Property 4: Password hash round-trip — generate random strings (1-72 chars),
verify `verify_password(pw, hash_password(pw))` is True.

**Validates: Requirements 7.1**
"""

from __future__ import annotations

import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.auth_service import hash_password, verify_password

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Printable ASCII passwords 1-72 chars (bcrypt's max input length).
_password = st.text(
    alphabet=string.printable.strip(),
    min_size=1,
    max_size=72,
).filter(lambda s: len(s) >= 1)


# ---------------------------------------------------------------------------
# Feature: 155_test-coverage-hardening
# Property 4: Password hash round-trip
# **Validates: Requirements 7.1**
#
# For any string password (1-72 chars),
# verify_password(password, hash_password(password)) SHALL return True.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@given(password=_password)
@settings(max_examples=20, deadline=None)
def test_password_hash_round_trip(password: str):
    """**Validates: Requirements 7.1**

    For any password (1-72 printable ASCII chars), hashing then verifying
    with the original password returns True.
    """
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
