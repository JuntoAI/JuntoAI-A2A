"""Property-based tests for social sharing models.

Feature: 192_social-sharing
Property 7: SharePayload round-trip serialization — generate valid SharePayload
instances via a composite Hypothesis strategy and verify that JSON
serialization followed by deserialization produces an equal object.

Property 1: Slug format and uniqueness — for any set of existing slugs,
the generated slug is exactly 8 alphanumeric characters and not in the
existing set.

Property 2: Idempotent share creation — for any valid session_id, calling
create_or_get_share twice with the same session_id returns the same
share_slug both times, and exactly 1 document is stored.

Property 3: Sensitive data exclusion — for any valid NegotiationState
containing non-empty history, hidden_context, custom_prompts, and
model_overrides fields, the resulting SharePayload and image prompt
shall not contain any substring from those sensitive fields.

**Validates: Requirements 7.7, 8.6, 1.2, 1.4, 1.5, 3.4**
"""

from __future__ import annotations

import re
import string
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.share import EvaluationScores, ParticipantSummary, PublicMessage, SharePayload

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=60,
)

_share_slug = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=8,
    max_size=8,
).filter(lambda s: s.isalnum())

_deal_status = st.sampled_from(["Agreed", "Blocked", "Failed"])

_participant_summary = st.builds(
    ParticipantSummary,
    role=_safe_text,
    name=_safe_text,
    agent_type=st.sampled_from(["negotiator", "regulator", "observer"]),
    summary=_safe_text,
)

_non_negative_float = st.floats(
    min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False
)

_non_negative_int = st.integers(min_value=0, max_value=1_000_000)

_score_1_10 = st.integers(min_value=1, max_value=10)

_evaluation_scores = st.builds(
    EvaluationScores,
    fairness=_score_1_10,
    mutual_respect=_score_1_10,
    value_creation=_score_1_10,
    satisfaction=_score_1_10,
    overall_score=_score_1_10,
)

_optional_evaluation_scores = st.one_of(st.none(), _evaluation_scores)

_public_message = st.builds(
    PublicMessage,
    agent_name=_safe_text,
    role=_safe_text,
    agent_type=st.sampled_from(["negotiator", "regulator", "observer"]),
    message=_safe_text,
    turn_number=st.integers(min_value=0, max_value=100),
)

_datetime = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)


@st.composite
def share_payload_strategy(draw):
    """Composite strategy generating valid SharePayload instances."""
    return SharePayload(
        share_slug=draw(_share_slug),
        session_id=draw(st.uuids().map(lambda u: u.hex)),
        scenario_id=draw(_safe_text),
        scenario_name=draw(_safe_text),
        scenario_description=draw(_safe_text),
        deal_status=draw(_deal_status),
        outcome_text=draw(_safe_text),
        final_offer=draw(_non_negative_float),
        turns_completed=draw(_non_negative_int),
        warning_count=draw(_non_negative_int),
        participant_summaries=draw(
            st.lists(_participant_summary, min_size=0, max_size=5)
        ),
        evaluation_scores=draw(_optional_evaluation_scores),
        public_conversation=draw(
            st.lists(_public_message, min_size=0, max_size=10)
        ),
        elapsed_time_ms=draw(_non_negative_int),
        share_image_url=draw(_safe_text),
        created_at=draw(_datetime),
    )


# ---------------------------------------------------------------------------
# Feature: 192_social-sharing
# Property 7: SharePayload round-trip serialization
# **Validates: Requirements 7.7, 8.6**
#
# For any valid SharePayload instance, serializing via .model_dump_json()
# and deserializing via SharePayload.model_validate_json() SHALL produce
# an object equal to the original.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(payload=share_payload_strategy())
def test_share_payload_round_trip_serialization(payload: SharePayload):
    """Serialize then deserialize a SharePayload — must equal the original."""
    json_bytes = payload.model_dump_json()
    restored = SharePayload.model_validate_json(json_bytes)
    assert restored == payload


# ---------------------------------------------------------------------------
# Strategy: random sets of existing slugs (8-char alphanumeric strings)
# ---------------------------------------------------------------------------

_SLUG_ALPHABET = string.ascii_letters + string.digits

_existing_slug = st.text(
    alphabet=st.sampled_from(list(_SLUG_ALPHABET)),
    min_size=8,
    max_size=8,
)

_existing_slugs_set = st.frozensets(_existing_slug, min_size=0, max_size=50)


# ---------------------------------------------------------------------------
# Feature: 192_social-sharing
# Property 1: Slug format and uniqueness
# **Validates: Requirements 1.2**
#
# For any set of existing share slugs and any call to the slug generator,
# the returned slug SHALL be exactly 8 characters long, contain only
# alphanumeric characters [a-zA-Z0-9], and not be present in the existing set.
# ---------------------------------------------------------------------------

_SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9]{8}$")


@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(existing_slugs=_existing_slugs_set)
async def test_slug_format_and_uniqueness(existing_slugs: frozenset[str]):
    """Generated slug is 8 alphanumeric chars and not in the existing set.

    Mocks the share store so get_share() returns None (no collision),
    then verifies the slug produced by _generate_slug() satisfies the
    format and uniqueness invariants.
    """
    mock_store = AsyncMock()
    mock_store.get_share = AsyncMock(return_value=None)

    with patch("app.services.share_service.get_share_store", return_value=mock_store):
        from app.services.share_service import _generate_slug

        slug = await _generate_slug()

    # Exactly 8 characters
    assert len(slug) == 8, f"Slug length {len(slug)} != 8: {slug!r}"

    # Only alphanumeric characters [a-zA-Z0-9]
    assert _SLUG_PATTERN.fullmatch(slug), f"Slug does not match [a-zA-Z0-9]{{8}}: {slug!r}"

    # Not in the existing set
    assert slug not in existing_slugs, f"Slug {slug!r} collides with existing set"


# ---------------------------------------------------------------------------
# Strategy: random session IDs (hex UUIDs)
# ---------------------------------------------------------------------------

_session_id = st.uuids().map(lambda u: u.hex)

_email = st.just("test@example.com")


# ---------------------------------------------------------------------------
# Feature: 192_social-sharing
# Property 2: Idempotent share creation
# **Validates: Requirements 1.4**
#
# For any valid session_id, calling create_or_get_share twice with the same
# session_id SHALL return the same share_slug both times, and the total
# number of SharePayload documents for that session_id SHALL remain exactly 1.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(session_id=_session_id)
async def test_idempotent_share_creation(session_id: str):
    """Calling create_or_get_share twice returns the same slug; create_share called once.

    Mocks the share store so get_share_by_session returns None on the first
    call (triggering creation) and returns the stored payload on the second
    call (returning existing). Asserts the same share_slug is returned both
    times and create_share is invoked exactly once.
    """
    # Track what gets stored
    stored_payloads: list[SharePayload] = []

    # --- Share store mock ---
    mock_share_store = AsyncMock()
    # get_share returns None (no slug collision)
    mock_share_store.get_share = AsyncMock(return_value=None)

    # get_share_by_session: None on first call, stored payload on second
    async def _get_share_by_session(sid: str):
        for p in stored_payloads:
            if p.session_id == sid:
                return p
        return None

    mock_share_store.get_share_by_session = AsyncMock(side_effect=_get_share_by_session)

    # create_share: record the payload
    async def _create_share(payload: SharePayload):
        stored_payloads.append(payload)

    mock_share_store.create_share = AsyncMock(side_effect=_create_share)

    # --- Session store mock ---
    mock_session_store = AsyncMock()
    mock_session_store.get_session_doc = AsyncMock(return_value={
        "session_id": session_id,
        "owner_email": "test@example.com",
        "deal_status": "Agreed",
        "scenario_id": "test-scenario",
        "current_offer": 1000.0,
        "turn_count": 5,
        "warning_count": 0,
        "duration_seconds": 120,
        "participant_summaries": [],
        "max_turns": 10,
    })

    # --- Scenario registry mock ---
    mock_scenario = MagicMock()
    mock_scenario.name = "Test Scenario"
    mock_scenario.description = "A test scenario"
    mock_registry = MagicMock()
    mock_registry.get_scenario = MagicMock(return_value=mock_scenario)

    with (
        patch("app.services.share_service.get_share_store", return_value=mock_share_store),
        patch("app.services.share_service.get_session_store", return_value=mock_session_store),
        patch("app.services.share_service.generate_share_image", new_callable=AsyncMock, return_value="https://example.com/placeholder.png"),
        patch("app.services.share_service.settings") as mock_settings,
    ):
        mock_settings.FRONTEND_URL = "https://test.juntoai.org"

        from app.services.share_service import create_or_get_share

        # First call — creates the share
        response1 = await create_or_get_share(session_id, "test@example.com", mock_registry)

        # Second call — returns existing share
        response2 = await create_or_get_share(session_id, "test@example.com", mock_registry)

    # Same slug returned both times
    assert response1.share_slug == response2.share_slug, (
        f"Slugs differ: {response1.share_slug!r} vs {response2.share_slug!r}"
    )

    # Exactly 1 document stored
    assert len(stored_payloads) == 1, (
        f"Expected 1 stored payload, got {len(stored_payloads)}"
    )

    # create_share called exactly once
    assert mock_share_store.create_share.call_count == 1, (
        f"create_share called {mock_share_store.create_share.call_count} times, expected 1"
    )


# ---------------------------------------------------------------------------
# Strategies for sensitive data (Property 3)
# ---------------------------------------------------------------------------

# Use min_size=5 to avoid false positives from very short strings matching
# common words in the output (e.g. "a", "AI", "the").
# Use a prefix to avoid matching JSON field names like "warning_count".
_sensitive_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters="\x00",
    ),
    min_size=5,
    max_size=80,
).map(lambda s: f"SENS_{s}")

_history_entry = st.fixed_dictionaries({"content": _sensitive_text})

_sensitive_dict = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L",)),
        min_size=1,
        max_size=10,
    ),
    values=_sensitive_text,
    min_size=1,
    max_size=5,
)


@st.composite
def session_doc_with_sensitive_fields(draw):
    """Generate a session_doc dict that includes both required fields and sensitive fields."""
    history = draw(st.lists(_history_entry, min_size=1, max_size=5))
    hidden_context = draw(_sensitive_text)
    custom_prompts = draw(_sensitive_dict)
    model_overrides = draw(_sensitive_dict)

    session_doc = {
        # Required fields for _build_share_payload
        "session_id": draw(st.uuids().map(lambda u: u.hex)),
        "owner_email": "test@example.com",
        "deal_status": draw(st.sampled_from(["Agreed", "Blocked", "Failed"])),
        "scenario_id": "test-scenario",
        "current_offer": draw(
            st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)
        ),
        "turn_count": draw(st.integers(min_value=0, max_value=100)),
        "warning_count": draw(st.integers(min_value=0, max_value=10)),
        "duration_seconds": draw(st.integers(min_value=0, max_value=3600)),
        "participant_summaries": [],
        "max_turns": draw(st.integers(min_value=1, max_value=50)),
        # Sensitive fields — MUST NOT leak into output
        "history": history,
        "hidden_context": hidden_context,
        "custom_prompts": custom_prompts,
        "model_overrides": model_overrides,
    }

    # Collect all sensitive values for assertion
    sensitive_values: list[str] = []
    for entry in history:
        sensitive_values.append(entry["content"])
    sensitive_values.append(hidden_context)
    for v in custom_prompts.values():
        sensitive_values.append(v)
    for v in model_overrides.values():
        sensitive_values.append(v)

    return session_doc, sensitive_values


# ---------------------------------------------------------------------------
# Feature: 192_social-sharing
# Property 3: Sensitive data exclusion
# **Validates: Requirements 1.5, 3.4**
#
# For any valid NegotiationState containing non-empty history,
# hidden_context, custom_prompts, and model_overrides fields, the
# resulting SharePayload (from _build_share_payload) and image prompt
# (from _build_image_prompt) SHALL NOT contain any substring from the
# raw history messages, hidden context values, custom prompt values,
# or model override values.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(data=session_doc_with_sensitive_fields())
def test_sensitive_data_exclusion(data: tuple[dict, list[str]]):
    """SharePayload and image prompt must not contain any sensitive field values."""
    session_doc, sensitive_values = data

    from app.services.share_service import _build_image_prompt, _build_share_payload

    # Use scenario=None so _build_share_payload falls back to scenario_config/scenario_id
    payload = _build_share_payload(session_doc, scenario=None, slug="Ab1Cd2Ef")

    # Serialize the payload to JSON for comprehensive substring search
    payload_json = payload.model_dump_json()

    # Build the image prompt
    image_prompt = _build_image_prompt(payload)

    for sensitive_val in sensitive_values:
        assert sensitive_val not in payload_json, (
            f"Sensitive value {sensitive_val!r} found in serialized SharePayload"
        )
        assert sensitive_val not in image_prompt, (
            f"Sensitive value {sensitive_val!r} found in image prompt"
        )


# ---------------------------------------------------------------------------
# Feature: 192_social-sharing
# Property 4: Social post text contains required elements
# **Validates: Requirements 4.1**
#
# For any valid SharePayload and share URL, the composed SocialPostText
# (all three platform variants) SHALL contain: the share URL, the branding
# line "JuntoAI A2A", and at least one hashtag from
# {#JuntoAI, #A2A, #AIAgents, #Negotiation}.
# ---------------------------------------------------------------------------

_REQUIRED_HASHTAGS = {"#JuntoAI", "#A2A", "#AIAgents", "#Negotiation"}


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(payload=share_payload_strategy())
def test_social_post_required_elements(payload: SharePayload):
    """All three social post variants contain share URL, branding, and hashtags."""
    from app.services.share_service import _compose_social_text

    share_url = f"https://test.juntoai.org/share/{payload.share_slug}"
    social_text = _compose_social_text(payload, share_url)

    for platform, text in [
        ("twitter", social_text.twitter),
        ("linkedin", social_text.linkedin),
        ("facebook", social_text.facebook),
    ]:
        # 1. Contains the share URL
        assert share_url in text, (
            f"{platform} post missing share URL: {text!r}"
        )

        # 2. Contains "JuntoAI A2A" branding
        assert "JuntoAI A2A" in text, (
            f"{platform} post missing 'JuntoAI A2A' branding: {text!r}"
        )

        # 3. Contains at least one required hashtag
        assert any(tag in text for tag in _REQUIRED_HASHTAGS), (
            f"{platform} post missing required hashtag (expected one of {_REQUIRED_HASHTAGS}): {text!r}"
        )


# ---------------------------------------------------------------------------
# Strategy: SharePayload with long text fields (for length constraint tests)
# ---------------------------------------------------------------------------

_long_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=100,
    max_size=600,
)


@st.composite
def share_payload_long_text_strategy(draw):
    """Composite strategy generating SharePayload with long scenario_name and outcome_text.

    Stress tests the truncation logic in _compose_social_text by producing
    inputs that would exceed platform character limits if not truncated.
    """
    return SharePayload(
        share_slug=draw(_share_slug),
        session_id=draw(st.uuids().map(lambda u: u.hex)),
        scenario_id=draw(_safe_text),
        scenario_name=draw(_long_text),
        scenario_description=draw(_long_text),
        deal_status=draw(_deal_status),
        outcome_text=draw(_long_text),
        final_offer=draw(_non_negative_float),
        turns_completed=draw(_non_negative_int),
        warning_count=draw(_non_negative_int),
        participant_summaries=draw(
            st.lists(_participant_summary, min_size=0, max_size=5)
        ),
        evaluation_scores=draw(_optional_evaluation_scores),
        public_conversation=draw(
            st.lists(_public_message, min_size=0, max_size=10)
        ),
        elapsed_time_ms=draw(_non_negative_int),
        share_image_url=draw(_safe_text),
        created_at=draw(_datetime),
    )


# ---------------------------------------------------------------------------
# Feature: 192_social-sharing
# Property 5: Social post text length constraints
# **Validates: Requirements 4.2, 4.3, 8.7**
#
# For any valid SharePayload, the composed SocialPostText SHALL have:
# twitter field length ≤ 280 characters, linkedin field length ≤ 3000
# characters, and facebook field length ≤ 3000 characters.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(payload=share_payload_long_text_strategy())
def test_social_post_length_constraints(payload: SharePayload):
    """Social post text respects platform character limits even with long inputs."""
    from app.services.share_service import _compose_social_text

    share_url = f"https://test.juntoai.org/share/{payload.share_slug}"
    social_text = _compose_social_text(payload, share_url)

    assert len(social_text.twitter) <= 280, (
        f"Twitter post exceeds 280 chars ({len(social_text.twitter)}): "
        f"{social_text.twitter!r}"
    )
    assert len(social_text.linkedin) <= 3000, (
        f"LinkedIn post exceeds 3000 chars ({len(social_text.linkedin)}): "
        f"{social_text.linkedin!r}"
    )
    assert len(social_text.facebook) <= 3000, (
        f"Facebook post exceeds 3000 chars ({len(social_text.facebook)}): "
        f"{social_text.facebook!r}"
    )


# ---------------------------------------------------------------------------
# Feature: 192_social-sharing
# Property 6: Mailto link composition
# **Validates: Requirements 5.2**
#
# For any valid SharePayload with non-empty scenario_name and deal_status,
# the generated mailto link SHALL contain the scenario_name in the subject,
# the deal_status in the subject, the share URL in the body, and the
# branding line "JuntoAI A2A" in the body.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(payload=share_payload_strategy())
def test_mailto_link_composition(payload: SharePayload):
    """Mailto link contains scenario_name, deal_status, share URL, and branding."""
    import urllib.parse

    from app.services.share_service import _compose_mailto

    share_url = f"https://test.juntoai.org/share/{payload.share_slug}"
    mailto = _compose_mailto(payload, share_url)

    # 1. Starts with "mailto:?"
    assert mailto.startswith("mailto:?"), (
        f"Mailto link does not start with 'mailto:?': {mailto!r}"
    )

    # Decode the URL-encoded mailto link for substring checks
    decoded = urllib.parse.unquote(mailto)

    # 2. Contains scenario_name (in the subject)
    assert payload.scenario_name in decoded, (
        f"Mailto link missing scenario_name {payload.scenario_name!r} in decoded link"
    )

    # 3. Contains deal_status (in the subject)
    assert payload.deal_status in decoded, (
        f"Mailto link missing deal_status {payload.deal_status!r} in decoded link"
    )

    # 4. Contains the share URL (in the body)
    assert share_url in decoded, (
        f"Mailto link missing share URL {share_url!r} in decoded link"
    )

    # 5. Contains "JuntoAI A2A" branding (in the body)
    assert "JuntoAI A2A" in decoded, (
        f"Mailto link missing 'JuntoAI A2A' branding in decoded link"
    )


# ---------------------------------------------------------------------------
# Feature: 192_social-sharing
# Property 8: Meta tag generation
# **Validates: Requirements 2.4, 2.5**
#
# For any valid SharePayload, the generated meta tags SHALL include:
# - og:title containing the scenario name
# - og:description with length ≤ 200 characters
# - og:image matching the share_image_url
# - og:url containing the share_slug
# - twitter:card = "summary_large_image"
# - twitter:title, twitter:description, twitter:image matching OG values
# ---------------------------------------------------------------------------

_site_url = st.sampled_from([
    "https://app.juntoai.org",
    "https://test.juntoai.org",
    "http://localhost:3000",
    "https://app.juntoai.org/",
])


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(payload=share_payload_strategy(), site_url=_site_url)
def test_meta_tag_generation(payload: SharePayload, site_url: str):
    """Generated meta tags satisfy OG and Twitter Card requirements."""
    from app.services.share_service import generate_meta_tags

    tags = generate_meta_tags(payload, site_url)

    # og:title contains the scenario name
    assert payload.scenario_name in tags["og:title"], (
        f"og:title {tags['og:title']!r} does not contain scenario_name {payload.scenario_name!r}"
    )

    # og:title contains the deal status
    assert payload.deal_status in tags["og:title"], (
        f"og:title {tags['og:title']!r} does not contain deal_status {payload.deal_status!r}"
    )

    # og:description ≤ 200 characters
    assert len(tags["og:description"]) <= 200, (
        f"og:description exceeds 200 chars ({len(tags['og:description'])})"
    )

    # og:image matches share_image_url
    assert tags["og:image"] == payload.share_image_url, (
        f"og:image {tags['og:image']!r} != share_image_url {payload.share_image_url!r}"
    )

    # og:url contains the share_slug
    assert payload.share_slug in tags["og:url"], (
        f"og:url {tags['og:url']!r} does not contain share_slug {payload.share_slug!r}"
    )

    # og:url has correct format: {site_url}/share/{slug}
    normalized_base = site_url.rstrip("/")
    expected_url = f"{normalized_base}/share/{payload.share_slug}"
    assert tags["og:url"] == expected_url, (
        f"og:url {tags['og:url']!r} != expected {expected_url!r}"
    )

    # twitter:card = "summary_large_image"
    assert tags["twitter:card"] == "summary_large_image", (
        f"twitter:card {tags['twitter:card']!r} != 'summary_large_image'"
    )

    # twitter:title matches og:title
    assert tags["twitter:title"] == tags["og:title"], (
        f"twitter:title {tags['twitter:title']!r} != og:title {tags['og:title']!r}"
    )

    # twitter:description matches og:description
    assert tags["twitter:description"] == tags["og:description"], (
        f"twitter:description != og:description"
    )

    # twitter:image matches og:image
    assert tags["twitter:image"] == tags["og:image"], (
        f"twitter:image {tags['twitter:image']!r} != og:image {tags['og:image']!r}"
    )
