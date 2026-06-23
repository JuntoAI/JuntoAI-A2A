"""Unit tests for @juntoai.org unlimited tokens feature.

Validates: internal team members get unlimited token access regardless of tier.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.tier_calculator import (
    INTERNAL_DOMAIN,
    UNLIMITED_TOKENS,
    get_daily_limit,
    is_internal_email,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# is_internal_email — deterministic cases
# ---------------------------------------------------------------------------


class TestIsInternalEmail:
    """Validates the is_internal_email helper."""

    def test_standard_internal_email(self):
        assert is_internal_email("dev@juntoai.org") is True

    def test_internal_email_case_insensitive(self):
        assert is_internal_email("Dev@JuntoAI.ORG") is True

    def test_internal_email_with_whitespace(self):
        assert is_internal_email("  admin@juntoai.org  ") is True

    def test_external_email_rejected(self):
        assert is_internal_email("user@example.com") is False

    def test_similar_domain_rejected(self):
        """Subdomains or lookalikes must not pass."""
        assert is_internal_email("user@notjuntoai.org") is False
        assert is_internal_email("user@juntoai.org.evil.com") is False
        assert is_internal_email("user@sub.juntoai.org") is False

    def test_empty_string(self):
        assert is_internal_email("") is False

    def test_no_at_sign(self):
        assert is_internal_email("juntoai.org") is False


# ---------------------------------------------------------------------------
# get_daily_limit — unlimited for internal emails
# ---------------------------------------------------------------------------


class TestGetDailyLimitUnlimited:
    """Validates get_daily_limit returns UNLIMITED_TOKENS for internal emails."""

    @pytest.mark.parametrize("tier", [1, 2, 3])
    def test_internal_email_gets_unlimited_regardless_of_tier(self, tier):
        result = get_daily_limit(tier, email="anyone@juntoai.org")
        assert result == UNLIMITED_TOKENS

    @pytest.mark.parametrize("tier,expected", [(1, 20), (2, 50), (3, 100)])
    def test_external_email_gets_tier_limit(self, tier, expected):
        result = get_daily_limit(tier, email="user@gmail.com")
        assert result == expected

    def test_no_email_uses_tier_limit(self):
        """Backward-compatible: no email param → normal tier behavior."""
        assert get_daily_limit(1) == 20
        assert get_daily_limit(2) == 50
        assert get_daily_limit(3) == 100

    def test_none_email_uses_tier_limit(self):
        assert get_daily_limit(1, email=None) == 20


# ---------------------------------------------------------------------------
# Property-based: any @juntoai.org email always gets unlimited
# ---------------------------------------------------------------------------


_local_parts = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00"),
    min_size=1,
    max_size=30,
)


@given(local_part=_local_parts, tier=st.integers(min_value=1, max_value=3))
@settings(max_examples=100)
def test_any_internal_local_part_gets_unlimited(local_part, tier):
    """Any valid local-part @juntoai.org always yields UNLIMITED_TOKENS."""
    email = f"{local_part}@{INTERNAL_DOMAIN}"
    assert get_daily_limit(tier, email=email) == UNLIMITED_TOKENS
    assert is_internal_email(email) is True


_external_domains = st.sampled_from([
    "gmail.com", "outlook.com", "yahoo.com", "company.co", "example.org",
])


@given(
    local_part=_local_parts,
    domain=_external_domains,
    tier=st.sampled_from([1, 2, 3]),
)
@settings(max_examples=100)
def test_external_emails_never_get_unlimited(local_part, domain, tier):
    """Non-juntoai.org emails always get normal tier-based limits."""
    email = f"{local_part}@{domain}"
    result = get_daily_limit(tier, email=email)
    assert result != UNLIMITED_TOKENS
    assert is_internal_email(email) is False
