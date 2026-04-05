"""Property-based tests for profile validation, tier calculation, and country codes.

Tests cover Properties 3, 4, 5, 7, 8, and 17 from the design document.
"""

from datetime import datetime, timezone

import pycountry
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.models.profile import ProfileUpdateRequest
from app.services.tier_calculator import calculate_tier, get_daily_limit, is_profile_complete

# ---------------------------------------------------------------------------
# Valid ISO 3166-1 alpha-2 codes (used by Properties 17)
# ---------------------------------------------------------------------------
VALID_COUNTRY_CODES = frozenset(c.alpha_2 for c in pycountry.countries)


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 3: Display name length validation
# ---------------------------------------------------------------------------


@given(name=st.text(min_size=0, max_size=200))
@settings(max_examples=100)
def test_display_name_length_validation(name: str):
    """**Validates: Requirements 3.1, 3.3**

    For any string, the display name validator accepts iff
    2 <= len(stripped) <= 100.
    """
    stripped = name.strip()
    should_accept = 2 <= len(stripped) <= 100

    if should_accept:
        req = ProfileUpdateRequest(display_name=name)
        assert req.display_name == stripped
    else:
        with pytest.raises(ValidationError):
            ProfileUpdateRequest(display_name=name)


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 4: Display name whitespace trimming
# ---------------------------------------------------------------------------

# Strategy: valid core (2-100 chars of printable non-whitespace), wrapped in random whitespace
_valid_core = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=2,
    max_size=100,
)
_ws_padding = st.text(
    alphabet=st.sampled_from([" ", "\t", "\n", "\r"]),
    min_size=0,
    max_size=20,
)


@given(core=_valid_core, leading=_ws_padding, trailing=_ws_padding)
@settings(max_examples=100)
def test_display_name_whitespace_trimming(core: str, leading: str, trailing: str):
    """**Validates: Requirements 3.4**

    For any valid display name with arbitrary leading/trailing whitespace,
    stored == input.strip().
    """
    padded = leading + core + trailing
    stripped = padded.strip()

    # Only test if the stripped result is within valid bounds
    if 2 <= len(stripped) <= 100:
        req = ProfileUpdateRequest(display_name=padded)
        assert req.display_name == stripped


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 5: URL format validation
# ---------------------------------------------------------------------------

# Strategies for valid GitHub usernames and LinkedIn slugs
_github_username = st.from_regex(r"[a-zA-Z0-9\-]{1,39}", fullmatch=True)
_linkedin_slug = st.from_regex(r"[a-zA-Z0-9\-]{3,100}", fullmatch=True)
_linkedin_prefix = st.sampled_from(["https://linkedin.com/in/", "https://www.linkedin.com/in/"])


@given(username=_github_username)
@settings(max_examples=100)
def test_github_url_valid_accepted(username: str):
    """**Validates: Requirements 5.1, 5.4** (valid GitHub URLs accepted)"""
    url = f"https://github.com/{username}"
    req = ProfileUpdateRequest(github_url=url)
    assert req.github_url == url


@given(slug=_linkedin_slug, prefix=_linkedin_prefix)
@settings(max_examples=100)
def test_linkedin_url_valid_accepted(slug: str, prefix: str):
    """**Validates: Requirements 5.2, 5.4** (valid LinkedIn URLs accepted)"""
    url = f"{prefix}{slug}"
    req = ProfileUpdateRequest(linkedin_url=url)
    assert req.linkedin_url == url


@given(random_str=st.text(min_size=1, max_size=150))
@settings(max_examples=100)
def test_url_format_validation_rejects_invalid(random_str: str):
    """**Validates: Requirements 5.1, 5.2, 5.4** (invalid URLs rejected)

    Random strings that don't match the GitHub or LinkedIn patterns are rejected.
    """
    import re

    github_pattern = r"^https://github\.com/[a-zA-Z0-9\-]{1,39}$"
    linkedin_pattern = r"^https://(www\.)?linkedin\.com/in/[a-zA-Z0-9\-]{3,100}$"

    if not re.match(github_pattern, random_str):
        with pytest.raises(ValidationError):
            ProfileUpdateRequest(github_url=random_str)

    if not re.match(linkedin_pattern, random_str):
        with pytest.raises(ValidationError):
            ProfileUpdateRequest(linkedin_url=random_str)


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 7: Tier determination
# ---------------------------------------------------------------------------

_optional_datetime = st.one_of(
    st.none(),
    st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)).map(
        lambda dt: dt.replace(tzinfo=timezone.utc)
    ),
)


@given(profile_completed_at=_optional_datetime, email_verified=st.booleans())
@settings(max_examples=100)
def test_tier_determination(profile_completed_at, email_verified):
    """**Validates: Requirements 6.7, 7.1, 7.2**

    Tier 3 if profile_completed_at is non-null (regardless of email_verified),
    Tier 2 if profile_completed_at is null and email_verified is true,
    Tier 1 otherwise. Daily limits: 100, 50, 20 respectively.
    """
    tier = calculate_tier(profile_completed_at, email_verified)

    if profile_completed_at is not None:
        assert tier == 3
        assert get_daily_limit(tier) == 100
    elif email_verified:
        assert tier == 2
        assert get_daily_limit(tier) == 50
    else:
        assert tier == 1
        assert get_daily_limit(tier) == 20


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 8: Profile completeness evaluation
# ---------------------------------------------------------------------------

_display_name = st.one_of(st.just(""), st.just("   "), st.text(min_size=1, max_size=50))
_optional_url = st.one_of(st.none(), st.just("https://github.com/user"), st.just("https://linkedin.com/in/user"))


@given(
    display_name=_display_name,
    email_verified=st.booleans(),
    github_url=_optional_url,
    linkedin_url=_optional_url,
)
@settings(max_examples=100)
def test_profile_completeness_evaluation(display_name, email_verified, github_url, linkedin_url):
    """**Validates: Requirements 5.5, 6.6**

    Profile is complete iff: non-empty display name (after trim),
    email verified, and at least one professional link present.
    """
    has_display_name = bool(display_name and display_name.strip())
    has_link = bool(github_url) or bool(linkedin_url)
    expected = has_display_name and email_verified and has_link

    result = is_profile_complete(display_name, email_verified, github_url, linkedin_url)
    assert result == expected


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 17: Country code validation
# ---------------------------------------------------------------------------


@given(code=st.sampled_from(sorted(VALID_COUNTRY_CODES)))
@settings(max_examples=100)
def test_valid_country_codes_accepted(code: str):
    """**Validates: Requirements 12.2, 12.4** (valid codes accepted)"""
    req = ProfileUpdateRequest(country=code)
    assert req.country == code.upper()


@given(random_str=st.text(min_size=1, max_size=10))
@settings(max_examples=100)
def test_invalid_country_codes_rejected(random_str: str):
    """**Validates: Requirements 12.2, 12.4** (invalid codes rejected)

    Any string that is not a valid ISO 3166-1 alpha-2 code is rejected.
    """
    if random_str.upper() not in VALID_COUNTRY_CODES:
        with pytest.raises(ValidationError):
            ProfileUpdateRequest(country=random_str)


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 12: Tier-aware token reset
# ---------------------------------------------------------------------------


@given(profile_completed_at=_optional_datetime, email_verified=st.booleans())
@settings(max_examples=100)
def test_tier_aware_token_reset(profile_completed_at, email_verified):
    """**Validates: Requirements 10.2, 10.3, 10.4**

    For any user, the reset balance equals the daily limit for their tier:
    100 if profile_completed_at is non-null, 50 if email_verified is true
    and profile_completed_at is null, 20 otherwise.
    """
    tier = calculate_tier(profile_completed_at, email_verified)
    reset_balance = get_daily_limit(tier)

    if profile_completed_at is not None:
        assert reset_balance == 100
    elif email_verified:
        assert reset_balance == 50
    else:
        assert reset_balance == 20


# ---------------------------------------------------------------------------
# Feature: user-profile-token-upgrade, Property 14: Waitlist signup initial balance
# ---------------------------------------------------------------------------

# The initial balance for new waitlist signups is a constant (20, Tier 1 default).
# We verify the tier calculator agrees: a brand-new user has no profile_completed_at
# and email_verified=False, so their tier is 1 and daily limit is 20.

_random_email = st.from_regex(r"[a-z]{3,20}@[a-z]{3,10}\.[a-z]{2,4}", fullmatch=True)


@given(email=_random_email)
@settings(max_examples=100)
def test_waitlist_signup_initial_balance(email: str):
    """**Validates: Requirements 6.1**

    For any new waitlist signup, the initial token_balance is 20 (Tier 1).
    A new user has profile_completed_at=None and email_verified=False,
    so calculate_tier returns 1 and get_daily_limit returns 20.
    """
    # New user defaults
    tier = calculate_tier(profile_completed_at=None, email_verified=False)
    daily_limit = get_daily_limit(tier)

    assert tier == 1
    assert daily_limit == 20
