"""Pure functions for tier determination and profile completeness evaluation.

No side effects — all functions are deterministic based on inputs.
"""

from datetime import datetime

TIER_LIMITS: dict[int, int] = {1: 20, 2: 50, 3: 100}


def calculate_tier(
    profile_completed_at: datetime | None, email_verified: bool
) -> int:
    """Return tier (1, 2, or 3) based on profile state.

    - Tier 3: profile_completed_at is set (permanent, regardless of other fields)
    - Tier 2: email verified but profile not yet completed
    - Tier 1: default / unverified
    """
    if profile_completed_at is not None:
        return 3
    if email_verified:
        return 2
    return 1


def get_daily_limit(tier: int) -> int:
    """Return daily token limit for a given tier. Defaults to 20 for unknown tiers."""
    return TIER_LIMITS.get(tier, 20)


def is_profile_complete(
    display_name: str,
    email_verified: bool,
    github_url: str | None,
    linkedin_url: str | None,
) -> bool:
    """Check if profile meets Tier 3 requirements.

    All three conditions must be met:
    1. display_name is non-empty after trimming
    2. email_verified is true
    3. At least one professional link (GitHub or LinkedIn) is present
    """
    has_display_name = bool(display_name and display_name.strip())
    has_professional_link = bool(github_url) or bool(linkedin_url)
    return has_display_name and email_verified and has_professional_link
