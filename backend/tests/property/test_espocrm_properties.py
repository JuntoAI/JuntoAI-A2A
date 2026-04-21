"""Property-based tests for the EspoCRM contact sync service.

Feature: 360_espocrm-contact-sync

Tests Properties 1-7 as defined in the design document.
All httpx calls are mocked — no real HTTP calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.services.espocrm_service import build_contact_payload, sync_contact

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

_waitlist_data_with_signed_up = st.one_of(
    st.fixed_dictionaries({}),
    st.fixed_dictionaries({"signed_up_at": st.just("2025-01-01T00:00:00+00:00")}),
)
_profile_data = st.one_of(
    st.none(),
    st.fixed_dictionaries({}),
    st.fixed_dictionaries({"display_name": st.text(max_size=100)}),
)

# ---------------------------------------------------------------------------
# Feature: 360_espocrm-contact-sync, Property 1
# Email normalisation round-trip
# **Validates: Requirements 2.1, 2.10**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@given(email=st.emails())
@settings(max_examples=100, deadline=None)
def test_email_normalisation_round_trip(email: str) -> None:
    """Property 1: Email normalisation round-trip.

    For any valid email string, build_contact_payload SHALL produce a payload
    where emailAddress equals email.lower().strip().

    Validates: Requirements 2.1, 2.10
    """
    payload = build_contact_payload(email, {}, None)
    assert payload["emailAddress"] == email.lower().strip()


# ---------------------------------------------------------------------------
# Feature: 360_espocrm-contact-sync, Property 2
# All required fields always present
# **Validates: Requirements 2.11**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@given(
    email=st.emails(),
    waitlist_data=_waitlist_data_with_signed_up,
    profile_data=_profile_data,
)
@settings(max_examples=100, deadline=None)
def test_all_required_fields_always_present(
    email: str,
    waitlist_data: dict,
    profile_data: "dict | None",
) -> None:
    """Property 2: All required fields always present.

    For any valid email string and any dict inputs, build_contact_payload SHALL
    produce a payload containing all nine required keys.

    Validates: Requirements 2.11
    """
    required_keys = {
        "emailAddress",
        "firstName",
        "lastName",
        "cJuntoaiServices",
        "cJuntoaiRegisteredAt",
        "cJuntoaiMarketingEmail",
        "cJuntoaiConsentTimestamp",
        "accountId",
        "teamsIds",
        "cLinkedIn",
        "addressCountry",
    }
    payload = build_contact_payload(email, waitlist_data, profile_data)
    missing = required_keys - payload.keys()
    assert not missing, f"Missing keys: {missing}"


# ---------------------------------------------------------------------------
# Feature: 360_espocrm-contact-sync, Property 3
# Hardcoded field invariants
# **Validates: Requirements 2.4, 2.6, 2.8, 2.9**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@given(
    email=st.emails(),
    waitlist_data=_waitlist_data_with_signed_up,
    profile_data=_profile_data,
)
@settings(max_examples=100, deadline=None)
def test_hardcoded_field_invariants(
    email: str,
    waitlist_data: dict,
    profile_data: "dict | None",
) -> None:
    """Property 3: Hardcoded field invariants.

    For any input, build_contact_payload SHALL produce a payload where:
    - cJuntoaiServices == ["a2a"]
    - cJuntoaiMarketingEmail is True
    - accountId == settings.ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID
    - teamsIds == [settings.ESPOCRM_JUNTOAI_TEAM_ID]

    Validates: Requirements 2.4, 2.6, 2.8, 2.9
    """
    from app.config import settings

    payload = build_contact_payload(email, waitlist_data, profile_data)

    assert payload["cJuntoaiServices"] == ["a2a"]
    assert payload["cJuntoaiMarketingEmail"] is True
    assert payload["accountId"] == settings.ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID
    assert payload["teamsIds"] == [settings.ESPOCRM_JUNTOAI_TEAM_ID]


# ---------------------------------------------------------------------------
# Feature: 360_espocrm-contact-sync, Property 4
# Name splitting from display_name
# **Validates: Requirements 2.2**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@given(
    email=st.emails(),
    display_name=st.text(min_size=3).filter(lambda s: " " in s.strip()),
)
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
def test_name_splitting_from_display_name(email: str, display_name: str) -> None:
    """Property 4: Name splitting from display_name.

    For any display_name containing at least one space, build_contact_payload
    SHALL set firstName to the substring before the first space and lastName
    to the remainder after the first space.

    Validates: Requirements 2.2
    """
    profile_data = {"display_name": display_name}
    payload = build_contact_payload(email, {}, profile_data)

    stripped = display_name.strip()
    if " " in stripped:
        expected_first, expected_last = stripped.split(" ", 1)
        assert payload["firstName"] == expected_first
        assert payload["lastName"] == expected_last


# ---------------------------------------------------------------------------
# Feature: 360_espocrm-contact-sync, Property 5
# Name fallback from email local part
# **Validates: Requirements 2.3**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@given(email=st.emails())
@settings(max_examples=100, deadline=None)
def test_name_fallback_from_email_local_part(email: str) -> None:
    """Property 5: Name fallback from email local part.

    For any email string and profile_data=None, build_contact_payload SHALL
    set firstName to the local part of the email (before @) and lastName to "".

    Validates: Requirements 2.3
    """
    payload = build_contact_payload(email, {}, None)

    normalised = email.lower().strip()
    expected_first = normalised.split("@")[0]

    assert payload["firstName"] == expected_first
    assert payload["lastName"] == "."


# ---------------------------------------------------------------------------
# Feature: 360_espocrm-contact-sync, Property 6
# Consent timestamp equals registered-at
# **Validates: Requirements 2.7**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@given(
    email=st.emails(),
    waitlist_data=_waitlist_data_with_signed_up,
    profile_data=_profile_data,
)
@settings(max_examples=100, deadline=None)
def test_consent_timestamp_equals_registered_at(
    email: str,
    waitlist_data: dict,
    profile_data: "dict | None",
) -> None:
    """Property 6: Consent timestamp equals registered-at.

    For any input, build_contact_payload SHALL produce a payload where
    cJuntoaiConsentTimestamp == cJuntoaiRegisteredAt.

    Validates: Requirements 2.7
    """
    payload = build_contact_payload(email, waitlist_data, profile_data)
    assert payload["cJuntoaiConsentTimestamp"] == payload["cJuntoaiRegisteredAt"]


# ---------------------------------------------------------------------------
# Feature: 360_espocrm-contact-sync, Property 7
# sync_contact never raises
# **Validates: Requirements 1.12**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@pytest.mark.asyncio
@given(
    email=st.text(min_size=1, max_size=100),
    waitlist_data=st.dictionaries(
        keys=st.text(max_size=20),
        values=st.text(max_size=50),
        max_size=5,
    ),
    profile_data=st.one_of(
        st.none(),
        st.dictionaries(
            keys=st.text(max_size=20),
            values=st.text(max_size=50),
            max_size=5,
        ),
    ),
)
@settings(max_examples=50, deadline=None)
async def test_sync_contact_never_raises(
    email: str,
    waitlist_data: dict,
    profile_data: "dict | None",
) -> None:
    """Property 7: sync_contact never raises.

    For any email string and any dict inputs, sync_contact SHALL return a
    CrmSyncResult without raising an exception, even when the underlying
    httpx client raises arbitrary exceptions.

    Validates: Requirements 1.12
    """
    from app.models.admin import CrmSyncResult

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(side_effect=Exception("boom"))
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.espocrm_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "cloud"
        mock_settings.ESPOCRM_URL = "https://crm.example.com"
        mock_settings.ESPOCRM_API_KEY = "test-key"
        mock_settings.ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID = "acc-123"
        mock_settings.ESPOCRM_JUNTOAI_TEAM_ID = "team-456"

        with patch("app.services.espocrm_service.httpx.AsyncClient", return_value=mock_client):
            result = await sync_contact(email, waitlist_data, profile_data)

    assert isinstance(result, CrmSyncResult)
    assert result.action in ("created", "updated", "skipped", "error")
