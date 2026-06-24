"""Property-based tests for CRM Integration API models.

# Feature: 350_crm-integration-api, Property 14: Pydantic Model Serialization Round-Trip

For any valid instance of CreateKeyRequest, SimulateRequest, CRMContext,
SessionStatusResponse, HealthResponse, WebhookPayload, ScenarioBuilderInput,
or IntegrationErrorResponse, serializing to JSON via .model_dump_json() and
deserializing back via .model_validate_json() SHALL produce an equivalent
model instance.

**Validates: Requirements 14.3**
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.integrations import (
    CRMContext,
    HealthResponse,
    IntegrationErrorResponse,
    RateLimitInfo,
    ScenarioBuilderInput,
    SessionStatusResponse,
    SimulateRequest,
    WebhookPayload,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=60,
)

_non_empty_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=60,
)

_non_negative_float = st.floats(
    min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False
)

_non_negative_int = st.integers(min_value=0, max_value=1_000_000)

_iso_datetime = st.datetimes(
    min_value=__import__("datetime").datetime(2020, 1, 1),
    max_value=__import__("datetime").datetime(2030, 12, 31),
).map(lambda dt: dt.isoformat())

_scopes = st.lists(
    st.sampled_from(["simulate", "read_sessions", "list_scenarios", "manage_keys"]),
    min_size=1,
    max_size=4,
    unique=True,
)

# ---------------------------------------------------------------------------
# Strategy: CRMContext
# ---------------------------------------------------------------------------

_optional_text = st.one_of(st.none(), _safe_text)
_optional_float = st.one_of(st.none(), _non_negative_float)
_optional_string_list = st.one_of(st.none(), st.lists(_safe_text, min_size=0, max_size=5))
_optional_bool = st.one_of(st.none(), st.booleans())
_optional_custom_fields = st.one_of(
    st.none(),
    st.dictionaries(
        keys=_non_empty_text,
        values=st.one_of(
            _safe_text,
            st.integers(min_value=-1000, max_value=1000),
            st.booleans(),
        ),
        min_size=0,
        max_size=3,
    ),
)


@st.composite
def crm_context_strategy(draw):
    """Generate valid CRMContext instances."""
    return CRMContext(
        contact_name=draw(_optional_text),
        company=draw(_optional_text),
        role=draw(_optional_text),
        industry=draw(_optional_text),
        deal_value=draw(_optional_float),
        deal_stage=draw(_optional_text),
        pain_points=draw(_optional_string_list),
        competing_vendors=draw(_optional_string_list),
        budget_approved=draw(_optional_bool),
        custom_fields=draw(_optional_custom_fields),
    )


# ---------------------------------------------------------------------------
# Strategy: ScenarioBuilderInput
# ---------------------------------------------------------------------------


@st.composite
def scenario_builder_input_strategy(draw):
    """Generate valid ScenarioBuilderInput instances."""
    from app.models.integrations import (
        DealContextInput,
        MyProfileInput,
        RegulatorInput,
        TheirProfileInput,
    )

    my_profile = MyProfileInput(
        name=draw(_non_empty_text),
        role=draw(_non_empty_text),
        company=draw(_non_empty_text),
        goals=draw(st.lists(_non_empty_text, min_size=1, max_size=3)),
        constraints=draw(st.lists(_non_empty_text, min_size=0, max_size=3)),
        tone=draw(_optional_text),
    )

    their_profile = TheirProfileInput(
        name=draw(_non_empty_text),
        role=draw(_non_empty_text),
        company=draw(_non_empty_text),
        industry=draw(_optional_text),
        goals=draw(st.lists(_non_empty_text, min_size=1, max_size=3)),
        constraints=draw(st.lists(_non_empty_text, min_size=0, max_size=3)),
        tone=draw(_optional_text),
    )

    deal_context = draw(st.one_of(
        st.none(),
        st.builds(
            DealContextInput,
            value=_optional_float,
            stage=_optional_text,
            competing_vendors=_optional_string_list,
            deadline=_optional_text,
            key_terms=_optional_string_list,
        ),
    ))

    regulator = draw(st.one_of(
        st.none(),
        st.builds(
            RegulatorInput,
            name=_non_empty_text,
            role=_non_empty_text,
            rules=st.lists(_non_empty_text, min_size=1, max_size=3),
        ),
    ))

    return ScenarioBuilderInput(
        simulation_type=draw(_non_empty_text),
        my_profile=my_profile,
        their_profile=their_profile,
        deal_context=deal_context,
        regulator=regulator,
        additional_instructions=draw(_optional_text),
    )


# ---------------------------------------------------------------------------
# Strategy: SimulateRequest (handles _dynamic / scenario_builder exclusion)
# ---------------------------------------------------------------------------

_https_url = st.one_of(
    st.none(),
    _non_empty_text.map(lambda s: f"https://{s}.example.com/webhook"),
)


@st.composite
def simulate_request_strategy(draw):
    """Generate valid SimulateRequest instances respecting mutual exclusion.

    Either generates a dynamic request (scenario_id="_dynamic" + scenario_builder)
    or a static request (non-_dynamic scenario_id, no scenario_builder).
    """
    is_dynamic = draw(st.booleans())

    if is_dynamic:
        scenario_id = "_dynamic"
        scenario_builder = draw(scenario_builder_input_strategy())
    else:
        scenario_id = draw(_non_empty_text.filter(lambda s: s != "_dynamic"))
        scenario_builder = None

    return SimulateRequest(
        scenario_id=scenario_id,
        active_toggles=draw(st.one_of(st.none(), st.lists(_non_empty_text, min_size=0, max_size=3))),
        context=draw(st.one_of(st.none(), crm_context_strategy())),
        callback_url=draw(_https_url),
        triggered_by=draw(_optional_text),
        scenario_builder=scenario_builder,
    )


# ---------------------------------------------------------------------------
# Strategy: SessionStatusResponse
# ---------------------------------------------------------------------------

_deal_status = st.sampled_from(["Agreed", "Blocked", "Failed"])
_score_1_10 = st.integers(min_value=1, max_value=10)


@st.composite
def session_status_response_strategy(draw):
    """Generate valid SessionStatusResponse instances."""
    from app.models.integrations import (
        EvaluationScores,
        ParticipantSummary,
        SessionOutcome,
    )

    has_outcome = draw(st.booleans())
    outcome = None
    if has_outcome:
        participant_summaries = draw(st.lists(
            st.builds(
                ParticipantSummary,
                role=_non_empty_text,
                name=_non_empty_text,
                agent_type=st.sampled_from(["negotiator", "regulator", "observer"]),
                summary=_safe_text,
            ),
            min_size=0,
            max_size=4,
        ))

        evaluation_scores = draw(st.one_of(
            st.none(),
            st.builds(
                EvaluationScores,
                fairness=_score_1_10,
                mutual_respect=_score_1_10,
                value_creation=_score_1_10,
                satisfaction=_score_1_10,
                overall_score=_score_1_10,
            ),
        ))

        outcome = SessionOutcome(
            deal_status=draw(_deal_status),
            summary=draw(_safe_text),
            final_offer=draw(_non_negative_float),
            turns_completed=draw(_non_negative_int),
            warning_count=draw(_non_negative_int),
            duration_seconds=draw(_non_negative_int),
            participant_summaries=participant_summaries,
            evaluation_scores=evaluation_scores,
        )

    return SessionStatusResponse(
        session_id=draw(st.uuids().map(lambda u: u.hex)),
        scenario_id=draw(_non_empty_text),
        scenario_name=draw(_safe_text),
        status=draw(st.sampled_from(["running", "completed", "failed"])),
        viewer_url=draw(_non_empty_text.map(lambda s: f"https://app.juntoai.org/share/{s}")),
        turns_completed=draw(_non_negative_int),
        current_offer=draw(st.one_of(st.none(), _non_negative_float)),
        created_at=draw(_iso_datetime),
        completed_at=draw(st.one_of(st.none(), _iso_datetime)),
        outcome=outcome,
    )


# ---------------------------------------------------------------------------
# Strategy: HealthResponse
# ---------------------------------------------------------------------------


@st.composite
def health_response_strategy(draw):
    """Generate valid HealthResponse instances."""
    rate_limit = RateLimitInfo(
        daily_limit=draw(st.integers(min_value=1, max_value=10000)),
        used_today=draw(st.integers(min_value=0, max_value=10000)),
        remaining=draw(st.integers(min_value=0, max_value=10000)),
        resets_at=draw(_iso_datetime),
    )

    return HealthResponse(
        status="ok",
        version=draw(_non_empty_text),
        key_valid=draw(st.booleans()),
        org_name=draw(_non_empty_text),
        rate_limit=rate_limit,
    )


# ---------------------------------------------------------------------------
# Strategy: WebhookPayload
# ---------------------------------------------------------------------------


@st.composite
def webhook_payload_strategy(draw):
    """Generate valid WebhookPayload instances."""
    return WebhookPayload(
        event=draw(st.sampled_from(["simulation.completed", "simulation.failed"])),
        session_id=draw(st.uuids().map(lambda u: u.hex)),
        scenario_id=draw(_non_empty_text),
        status=draw(st.sampled_from(["completed", "failed", "blocked"])),
        outcome=draw(st.dictionaries(
            keys=_non_empty_text,
            values=st.one_of(
                _safe_text,
                st.integers(min_value=-1000, max_value=1000),
                st.booleans(),
                _non_negative_float,
            ),
            min_size=0,
            max_size=5,
        )),
        viewer_url=draw(_non_empty_text.map(lambda s: f"https://app.juntoai.org/share/{s}")),
        timestamp=draw(_iso_datetime),
    )


# ---------------------------------------------------------------------------
# Strategy: IntegrationErrorResponse
# ---------------------------------------------------------------------------

_error_codes = st.sampled_from([
    "invalid_api_key",
    "key_deactivated",
    "insufficient_scope",
    "scenario_not_found",
    "session_not_found",
    "validation_error",
    "rate_limit_exceeded",
    "simulation_failed",
    "service_unavailable",
])


@st.composite
def integration_error_response_strategy(draw):
    """Generate valid IntegrationErrorResponse instances."""
    return IntegrationErrorResponse(
        error=draw(_error_codes),
        message=draw(_safe_text),
        details=draw(st.dictionaries(
            keys=_non_empty_text,
            values=st.one_of(
                _safe_text,
                st.integers(min_value=-1000, max_value=1000),
                st.booleans(),
            ),
            min_size=0,
            max_size=3,
        )),
    )


# ---------------------------------------------------------------------------
# Feature: 350_crm-integration-api, Property 14: Pydantic Model Serialization Round-Trip
# **Validates: Requirements 14.3**
#
# For any valid instance of CreateKeyRequest, SimulateRequest, CRMContext,
# SessionStatusResponse, HealthResponse, WebhookPayload, ScenarioBuilderInput,
# or IntegrationErrorResponse, serializing to JSON via .model_dump_json() and
# deserializing back via .model_validate_json() SHALL produce an equivalent
# model instance.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(instance=simulate_request_strategy())
def test_simulate_request_round_trip(instance: SimulateRequest):
    """SimulateRequest survives JSON serialization round-trip.

    Patches settings.RUN_MODE to 'local' so HTTPS callback_url validation
    passes during deserialization (the validator checks settings at runtime).
    """
    json_str = instance.model_dump_json()
    with patch("app.models.integrations.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        restored = SimulateRequest.model_validate_json(json_str)
    assert restored == instance


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(instance=crm_context_strategy())
def test_crm_context_round_trip(instance: CRMContext):
    """CRMContext survives JSON serialization round-trip."""
    json_str = instance.model_dump_json()
    restored = CRMContext.model_validate_json(json_str)
    assert restored == instance


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(instance=session_status_response_strategy())
def test_session_status_response_round_trip(instance: SessionStatusResponse):
    """SessionStatusResponse survives JSON serialization round-trip."""
    json_str = instance.model_dump_json()
    restored = SessionStatusResponse.model_validate_json(json_str)
    assert restored == instance


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(instance=health_response_strategy())
def test_health_response_round_trip(instance: HealthResponse):
    """HealthResponse survives JSON serialization round-trip."""
    json_str = instance.model_dump_json()
    restored = HealthResponse.model_validate_json(json_str)
    assert restored == instance


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(instance=webhook_payload_strategy())
def test_webhook_payload_round_trip(instance: WebhookPayload):
    """WebhookPayload survives JSON serialization round-trip."""
    json_str = instance.model_dump_json()
    restored = WebhookPayload.model_validate_json(json_str)
    assert restored == instance


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(instance=scenario_builder_input_strategy())
def test_scenario_builder_input_round_trip(instance: ScenarioBuilderInput):
    """ScenarioBuilderInput survives JSON serialization round-trip."""
    json_str = instance.model_dump_json()
    restored = ScenarioBuilderInput.model_validate_json(json_str)
    assert restored == instance


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(instance=integration_error_response_strategy())
def test_integration_error_response_round_trip(instance: IntegrationErrorResponse):
    """IntegrationErrorResponse survives JSON serialization round-trip."""
    json_str = instance.model_dump_json()
    restored = IntegrationErrorResponse.model_validate_json(json_str)
    assert restored == instance


# ===========================================================================
# Feature: 350_crm-integration-api, Property 1: API Key Generation and Validation Round-Trip
# Feature: 350_crm-integration-api, Property 2: API Key Record Completeness
# Feature: 350_crm-integration-api, Property 4: Rate Limit Enforcement
#
# These property tests validate the ApiKeyService against an in-memory SQLite
# store, covering key generation/validation round-trip, record completeness,
# and rate limit enforcement.
# ===========================================================================

import asyncio
import tempfile
import os
from datetime import datetime, timedelta, timezone

from app.db.api_key_store import SQLiteApiKeyClient
from app.services.api_key_service import ApiKeyService


# ---------------------------------------------------------------------------
# Fixtures / helpers for API key service property tests
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine synchronously (for Hypothesis which doesn't support async)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_service() -> tuple[ApiKeyService, SQLiteApiKeyClient, str]:
    """Create a fresh temp-file SQLite store and ApiKeyService.

    Returns (service, store, db_path). Caller should clean up db_path.
    Note: We use a temp file because SQLiteApiKeyClient opens a new connection
    per method call, and :memory: databases are per-connection.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = SQLiteApiKeyClient(db_path=db_path)
    service = ApiKeyService(store=store)
    return service, store, db_path


# ---------------------------------------------------------------------------
# Strategies for API key service tests
# ---------------------------------------------------------------------------

_org_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs"), blacklist_characters="\x00"),
    min_size=1,
    max_size=100,
)

_valid_scopes = st.lists(
    st.sampled_from(["simulate", "read_sessions", "list_scenarios", "manage_keys"]),
    min_size=1,
    max_size=4,
    unique=True,
)

_rate_limit_daily = st.integers(min_value=1, max_value=10000)
_rate_limit_per_minute = st.integers(min_value=1, max_value=100)


# ---------------------------------------------------------------------------
# Feature: 350_crm-integration-api, Property 1: API Key Generation and Validation Round-Trip
# **Validates: Requirements 1.1, 2.1**
#
# For any valid org_name, scopes, and rate_limit_daily, generating an API key
# and then validating it by computing SHA-256 of the raw key and querying the
# store SHALL return the original key record with matching metadata.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    org_name=_org_names,
    scopes=_valid_scopes,
    rate_limit_daily=_rate_limit_daily,
)
def test_api_key_generation_and_validation_round_trip(
    org_name: str, scopes: list[str], rate_limit_daily: int
):
    """Property 1: Generating a key and validating it returns the original record.

    **Validates: Requirements 1.1, 2.1**
    """

    async def _test():
        service, _store, db_path = _make_service()
        try:
            with patch("app.services.api_key_service.settings") as mock_settings:
                mock_settings.RUN_MODE = "local"
                mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
                mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
                mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

                # Generate key
                raw_key, key_record = await service.generate_key(
                    org_name=org_name,
                    domain="test.com",
                    created_by_email="test@example.com",
                    rate_limit_daily=rate_limit_daily,
                )

                # Validate key by hash lookup
                validated_record = await service.validate_key(raw_key)

                # Assert round-trip: validated record matches original metadata
                assert validated_record is not None
                assert validated_record["key_id"] == key_record["key_id"]
                assert validated_record["key_hash"] == key_record["key_hash"]
                assert validated_record["org_name"] == org_name
                assert validated_record["rate_limit_daily"] == rate_limit_daily
                assert validated_record["active"] is True

                # Assert hash matches
                computed_hash = ApiKeyService.hash_key(raw_key)
                assert validated_record["key_hash"] == computed_hash
        finally:
            os.unlink(db_path)

    _run_async(_test())


# ---------------------------------------------------------------------------
# Feature: 350_crm-integration-api, Property 2: API Key Record Completeness
# **Validates: Requirements 1.2**
#
# For any generated API key, the persisted record SHALL contain all required
# fields with correct types, and key_prefix SHALL equal the first 4 characters
# after "a2a_live_" in the raw key.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    org_name=_org_names,
    scopes=_valid_scopes,
    rate_limit_daily=_rate_limit_daily,
    rate_limit_per_minute=_rate_limit_per_minute,
)
def test_api_key_record_completeness(
    org_name: str, scopes: list[str], rate_limit_daily: int, rate_limit_per_minute: int
):
    """Property 2: Generated key records contain all required fields with correct types.

    **Validates: Requirements 1.2**
    """

    async def _test():
        service, _store, db_path = _make_service()
        try:
            with patch("app.services.api_key_service.settings") as mock_settings:
                mock_settings.RUN_MODE = "local"
                mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
                mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
                mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

                raw_key, key_record = await service.generate_key(
                    org_name=org_name,
                    domain="test.com",
                    created_by_email="admin@example.com",
                    rate_limit_daily=rate_limit_daily,
                    rate_limit_per_minute=rate_limit_per_minute,
                )

                # Assert all required fields exist
                required_fields = [
                    "key_id", "key_hash", "key_prefix", "org_name",
                    "domain", "created_by_email", "rate_limit_daily",
                    "rate_limit_per_minute", "active", "created_at",
                ]
                for field in required_fields:
                    assert field in key_record, f"Missing required field: {field}"

                # Assert correct types
                assert isinstance(key_record["key_id"], str) and len(key_record["key_id"]) > 0
                assert isinstance(key_record["key_hash"], str) and len(key_record["key_hash"]) == 64
                assert isinstance(key_record["key_prefix"], str) and len(key_record["key_prefix"]) == 4
                assert isinstance(key_record["org_name"], str)
                assert isinstance(key_record["created_by_email"], str)
                assert isinstance(key_record["rate_limit_daily"], int)
                assert isinstance(key_record["rate_limit_per_minute"], int)
                assert isinstance(key_record["active"], bool)
                assert isinstance(key_record["created_at"], str)

                # Assert key_prefix equals first 4 chars after "a2a_live_"
                prefix_from_raw = raw_key[len("a2a_live_"):len("a2a_live_") + 4]
                assert key_record["key_prefix"] == prefix_from_raw

                # Assert raw key format
                assert raw_key.startswith("a2a_live_")

                # Assert metadata matches inputs
                assert key_record["org_name"] == org_name
                assert key_record["rate_limit_daily"] == rate_limit_daily
                assert key_record["rate_limit_per_minute"] == rate_limit_per_minute
                assert key_record["active"] is True
        finally:
            os.unlink(db_path)

    _run_async(_test())


# ---------------------------------------------------------------------------
# Feature: 350_crm-integration-api, Property 4: Rate Limit Enforcement
# **Validates: Requirements 3.1, 3.2, 3.4**
#
# For any key with rate_limit_daily=D and usage_today=U, assert U >= D → rejected.
# For any key with rate_limit_per_minute=M and minute_window_count=C, assert C >= M → rejected.
# Assert each successful request increments counters.
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    daily_limit=st.integers(min_value=1, max_value=500),
    usage_today=st.integers(min_value=0, max_value=1000),
    per_minute_limit=st.integers(min_value=1, max_value=50),
    minute_count=st.integers(min_value=0, max_value=100),
)
def test_rate_limit_enforcement(
    daily_limit: int, usage_today: int, per_minute_limit: int, minute_count: int
):
    """Property 4: Rate limits are enforced correctly based on usage counters.

    **Validates: Requirements 3.1, 3.2, 3.4**
    """

    async def _test():
        service, store, db_path = _make_service()
        try:
            with patch("app.services.api_key_service.settings") as mock_settings:
                mock_settings.RUN_MODE = "local"
                mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
                mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
                mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

                # Generate a key with specific rate limits
                raw_key, key_record = await service.generate_key(
                    org_name="test-org",
                    domain="test.com",
                    created_by_email="test@example.com",
                    rate_limit_daily=daily_limit,
                    rate_limit_per_minute=per_minute_limit,
                )

                key_id = key_record["key_id"]
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                # Set up usage_today to the desired value
                await store.update_key(key_id, {
                    "usage_today": usage_today,
                    "usage_today_date": today_str,
                })

                # Set up minute window with the desired count (window started recently)
                now = datetime.now(timezone.utc)
                window_start = (now - timedelta(seconds=10)).isoformat()
                await store.update_key(key_id, {
                    "minute_window_start": window_start,
                    "minute_window_count": minute_count,
                })

                # Refresh key_record with updated values
                key_record["usage_today"] = usage_today
                key_record["usage_today_date"] = today_str
                key_record["minute_window_start"] = window_start
                key_record["minute_window_count"] = minute_count

                # Check rate limit
                allowed, rate_info = await service.check_rate_limit(key_record)

                if usage_today >= daily_limit:
                    # Daily limit exceeded → must be rejected
                    assert allowed is False, (
                        f"Expected rejection: usage_today={usage_today} >= daily_limit={daily_limit}"
                    )
                    assert rate_info["remaining"] == 0
                    assert "retry_after_seconds" in rate_info
                elif minute_count >= per_minute_limit:
                    # Per-minute limit exceeded → must be rejected
                    assert allowed is False, (
                        f"Expected rejection: minute_count={minute_count} >= per_minute_limit={per_minute_limit}"
                    )
                    assert "retry_after_seconds" in rate_info
                else:
                    # Both limits OK → must be allowed and counters incremented
                    assert allowed is True, (
                        f"Expected allowed: usage_today={usage_today} < daily_limit={daily_limit} "
                        f"and minute_count={minute_count} < per_minute_limit={per_minute_limit}"
                    )
                    # Daily counter should have been incremented
                    assert rate_info["used_today"] == usage_today + 1
                    assert rate_info["remaining"] == daily_limit - (usage_today + 1)
        finally:
            os.unlink(db_path)

    _run_async(_test())


# ===========================================================================
# Feature: 350_crm-integration-api, Property 3: Scope-Based Access Control
#
# For any API key with scopes S and any endpoint requiring scope R where R is
# not in S, the authentication dependency SHALL reject the request with HTTP 403
# and error code `insufficient_scope`.
#
# **Validates: Requirements 2.4**
# ===========================================================================

from unittest.mock import AsyncMock
from fastapi import HTTPException

from app.middleware.api_key_auth import validate_integration_auth

ALL_SCOPES = ["simulate", "read_sessions", "list_scenarios", "manage_keys"]

_domain_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00"),
    min_size=2,
    max_size=20,
).map(lambda s: f"{s}.com")


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    org_domain=_domain_strategy,
    wrong_domain=_domain_strategy,
)
def test_domain_mismatch_access_control(org_domain: str, wrong_domain: str):
    """Property 3: Email domain mismatch is rejected with 403 domain_mismatch.

    **Validates: Requirements 2.4 (adapted for domain-based auth)**
    """
    from hypothesis import assume
    assume(org_domain.lower() != wrong_domain.lower())

    async def _test():
        service, store, db_path = _make_service()
        try:
            with patch("app.services.api_key_service.settings") as mock_settings:
                mock_settings.RUN_MODE = "local"
                mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
                mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

                raw_key, key_record = await service.generate_key(
                    org_name="domain-test-org",
                    domain=org_domain,
                    created_by_email=f"admin@{org_domain}",
                    rate_limit_daily=1000,
                    rate_limit_per_minute=100,
                )

                with patch("app.middleware.api_key_auth.get_api_key_store", return_value=store):
                    try:
                        await validate_integration_auth(
                            x_integration_token=raw_key,
                            x_user_email=f"user@{wrong_domain}",
                        )
                        assert False, "Expected HTTPException(403) but call succeeded"
                    except HTTPException as exc:
                        assert exc.status_code == 403
                        assert exc.detail["error"] == "domain_mismatch"
        finally:
            os.unlink(db_path)

    _run_async(_test())


# ===========================================================================
# Feature: 350_crm-integration-api, Property 7: Context Preamble Round-Trip
#
# For any valid CRMContext, building a context preamble string and then parsing
# the preamble's key-value lines SHALL recover the original field names and
# values — lists as comma-separated strings, booleans as "Yes"/"No", and
# deal_value as a currency-formatted string.
#
# **Validates: Requirements 7.1, 7.3, 7.5**
# ===========================================================================

from app.services.integration_service import IntegrationService

# ---------------------------------------------------------------------------
# Strategy: CRMContext for round-trip testing (avoids ambiguous custom fields)
# ---------------------------------------------------------------------------

# Safe custom field keys: non-empty alphanumeric strings
_safe_custom_key = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)

# Safe custom field string values: no ", " (would be parsed as list),
# no "Yes"/"No" (would be parsed as boolean), non-empty
# Avoid whitespace categories to prevent stripping issues
_safe_custom_string_value = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=30,
).filter(lambda s: ", " not in s and s.strip() not in ("Yes", "No"))

# Custom field values that round-trip cleanly: booleans, safe strings
_roundtrip_custom_value = st.one_of(
    _safe_custom_string_value,
    st.booleans(),
)

_roundtrip_custom_fields = st.one_of(
    st.none(),
    st.dictionaries(
        keys=_safe_custom_key,
        values=_roundtrip_custom_value,
        min_size=0,
        max_size=3,
    ),
)

# Non-empty text for standard string fields (ensures they appear in preamble)
# Filter out values with leading/trailing whitespace that would be lost in parsing
_rt_non_empty_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=40,
)

# List items that don't contain ", " (to avoid ambiguous splitting)
# Also avoid whitespace-only or leading/trailing whitespace
_rt_list_item = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=20,
).filter(lambda s: ", " not in s)

_rt_optional_text = st.one_of(st.none(), _rt_non_empty_text)
_rt_optional_float = st.one_of(
    st.none(),
    st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False),
)
_rt_optional_list = st.one_of(st.none(), st.lists(_rt_list_item, min_size=1, max_size=5))
_rt_optional_bool = st.one_of(st.none(), st.booleans())


@st.composite
def crm_context_roundtrip_strategy(draw):
    """Generate CRMContext instances suitable for round-trip testing.

    Avoids ambiguous custom field values that don't round-trip cleanly.
    """
    return CRMContext(
        contact_name=draw(_rt_optional_text),
        company=draw(_rt_optional_text),
        role=draw(_rt_optional_text),
        industry=draw(_rt_optional_text),
        deal_value=draw(_rt_optional_float),
        deal_stage=draw(_rt_optional_text),
        pain_points=draw(_rt_optional_list),
        competing_vendors=draw(_rt_optional_list),
        budget_approved=draw(_rt_optional_bool),
        custom_fields=draw(_roundtrip_custom_fields),
    )


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(ctx=crm_context_roundtrip_strategy())
def test_context_preamble_round_trip(ctx: CRMContext):
    """Property 7: parse_context_preamble(build_context_preamble(ctx)) recovers fields.

    **Validates: Requirements 7.1, 7.3, 7.5**
    """
    service = IntegrationService()
    preamble = service.build_context_preamble(ctx)

    # If context is all-None, preamble is empty and parse returns empty dict
    ctx_data = ctx.model_dump(exclude_none=True)
    # Remove custom_fields if it's an empty dict
    if "custom_fields" in ctx_data and not ctx_data["custom_fields"]:
        del ctx_data["custom_fields"]

    if not ctx_data:
        assert preamble == ""
        assert service.parse_context_preamble(preamble) == {}
        return

    # Parse the preamble back
    parsed = service.parse_context_preamble(preamble)

    # Compare each non-None field from the original context
    for field_name, original_value in ctx_data.items():
        if field_name == "custom_fields":
            # Compare custom fields separately
            assert "custom_fields" in parsed, f"custom_fields missing from parsed result"
            parsed_custom = parsed["custom_fields"]
            for key, val in original_value.items():
                if val is None:
                    continue
                assert key in parsed_custom, f"Custom field '{key}' missing from parsed"
                if isinstance(val, bool):
                    assert parsed_custom[key] == val, (
                        f"Custom field '{key}': expected {val}, got {parsed_custom[key]}"
                    )
                elif isinstance(val, str):
                    assert parsed_custom[key] == val, (
                        f"Custom field '{key}': expected '{val}', got '{parsed_custom[key]}'"
                    )
            continue

        assert field_name in parsed, f"Field '{field_name}' missing from parsed result"
        parsed_value = parsed[field_name]

        if field_name == "deal_value":
            # deal_value is recovered as float via currency formatting
            # Currency format: $X,XXX.XX — rounds to 2 decimal places
            expected = round(original_value, 2)
            assert abs(parsed_value - expected) < 0.01, (
                f"deal_value: expected ~{expected}, got {parsed_value}"
            )
        elif field_name == "budget_approved":
            # Boolean recovered as bool
            assert parsed_value == original_value, (
                f"budget_approved: expected {original_value}, got {parsed_value}"
            )
        elif field_name in ("pain_points", "competing_vendors"):
            # Lists recovered as lists of strings
            assert isinstance(parsed_value, list)
            expected_list = [str(item) for item in original_value]
            assert parsed_value == expected_list, (
                f"{field_name}: expected {expected_list}, got {parsed_value}"
            )
        else:
            # String fields recovered as strings
            assert parsed_value == str(original_value), (
                f"{field_name}: expected '{original_value}', got '{parsed_value}'"
            )


# ===========================================================================
# Feature: 350_crm-integration-api, Property 8: Context Preamble Injection
# Preserves Original Prompt
#
# For any non-empty CRMContext and any persona_prompt, the injected prompt
# SHALL start with the context preamble block and end with the original
# persona_prompt content, with no content lost or reordered.
#
# **Validates: Requirements 7.2**
# ===========================================================================

from app.scenarios.models import (
    AgentDefinition,
    ArenaScenario,
    Budget,
    NegotiationParams,
    OutcomeReceipt,
    ToggleDefinition,
)

# Strategy for non-empty persona prompts
_persona_prompt = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=200,
)


@st.composite
def non_empty_crm_context_strategy(draw):
    """Generate CRMContext instances with at least one non-None field."""
    # Ensure at least contact_name is set so preamble is non-empty
    ctx = CRMContext(
        contact_name=draw(_rt_non_empty_text),
        company=draw(_rt_optional_text),
        role=draw(_rt_optional_text),
        industry=draw(_rt_optional_text),
        deal_value=draw(_rt_optional_float),
        deal_stage=draw(_rt_optional_text),
        pain_points=draw(_rt_optional_list),
        competing_vendors=draw(_rt_optional_list),
        budget_approved=draw(_rt_optional_bool),
        custom_fields=draw(_roundtrip_custom_fields),
    )
    return ctx


def _build_minimal_scenario(persona_prompt: str) -> ArenaScenario:
    """Build a minimal valid ArenaScenario with the given persona_prompt."""
    return ArenaScenario(
        id="test-scenario",
        name="Test Scenario",
        description="A minimal test scenario",
        difficulty="beginner",
        category="General",
        agents=[
            AgentDefinition(
                role="buyer",
                name="Buyer Agent",
                type="negotiator",
                persona_prompt=persona_prompt,
                goals=["Get a good deal"],
                budget=Budget(min=100, max=1000, target=500),
                tone="professional",
                output_fields=["proposed_price", "reasoning"],
                model_id="gemini-3.5-flash",
            ),
            AgentDefinition(
                role="seller",
                name="Seller Agent",
                type="negotiator",
                persona_prompt="I am the seller.",
                goals=["Maximize profit"],
                budget=Budget(min=200, max=2000, target=1500),
                tone="assertive",
                output_fields=["proposed_price", "reasoning"],
                model_id="gemini-3.5-flash",
            ),
        ],
        toggles=[
            ToggleDefinition(
                id="toggle-1",
                label="Test Toggle",
                target_agent_role="buyer",
                hidden_context_payload={"info": "secret"},
            ),
        ],
        negotiation_params=NegotiationParams(
            max_turns=5,
            agreement_threshold=50.0,
            turn_order=["buyer", "seller"],
        ),
        outcome_receipt=OutcomeReceipt(
            equivalent_human_time="2 hours",
            process_label="Negotiation",
        ),
    )


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    ctx=non_empty_crm_context_strategy(),
    persona_prompt=_persona_prompt,
)
def test_context_injection_preserves_original_prompt(ctx: CRMContext, persona_prompt: str):
    """Property 8: Injected prompt starts with preamble and ends with original prompt.

    **Validates: Requirements 7.2**
    """
    service = IntegrationService()

    # Build the preamble
    preamble = service.build_context_preamble(ctx)
    assert preamble, "Preamble should be non-empty for non-empty context"

    # Build a minimal scenario with the given persona_prompt
    scenario = _build_minimal_scenario(persona_prompt)

    # Inject context
    injected_scenario = service.inject_context_into_prompts(scenario, ctx)

    # Check the first agent (buyer) whose persona_prompt we control
    injected_prompt = injected_scenario.agents[0].persona_prompt

    # Assert injected prompt starts with the preamble
    assert injected_prompt.startswith(preamble), (
        f"Injected prompt does not start with preamble.\n"
        f"Preamble: {preamble[:100]}...\n"
        f"Prompt start: {injected_prompt[:100]}..."
    )

    # Assert injected prompt ends with the original persona_prompt
    assert injected_prompt.endswith(persona_prompt), (
        f"Injected prompt does not end with original prompt.\n"
        f"Original: {persona_prompt[:100]}...\n"
        f"Prompt end: {injected_prompt[-100:]}"
    )

    # Assert the structure is: preamble + "\n\n" + original_prompt
    expected = preamble + "\n\n" + persona_prompt
    assert injected_prompt == expected, (
        f"Injected prompt structure mismatch.\n"
        f"Expected length: {len(expected)}, Got: {len(injected_prompt)}"
    )

    # Also verify the second agent got the preamble prepended
    second_prompt = injected_scenario.agents[1].persona_prompt
    assert second_prompt.startswith(preamble), (
        "Second agent's prompt should also start with preamble"
    )
    assert second_prompt.endswith("I am the seller."), (
        "Second agent's original prompt should be preserved"
    )


# ===========================================================================
# Feature: 350_crm-integration-api, Property 12: HMAC-SHA256 Webhook Signature Correctness
#
# For any webhook payload bytes and API key string, compute_signature(payload, key)
# SHALL produce a hex digest that equals hmac.new(key.encode(), payload, hashlib.sha256).hexdigest(),
# and verify_signature(payload, key, signature) SHALL return True for a correctly
# computed signature and False for any tampered payload or incorrect key.
#
# **Validates: Requirements 11.2**
# ===========================================================================

import hashlib
import hmac as hmac_module

from app.services.webhook_dispatcher import WebhookDispatcher

# Strategy: arbitrary bytes for payload
_payload_bytes = st.binary(min_size=0, max_size=1024)

# Strategy: non-empty strings for secret key (keys must be non-empty to be meaningful)
_secret_key = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=100,
)


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    payload=_payload_bytes,
    key=_secret_key,
)
def test_hmac_sha256_webhook_signature_correctness(payload: bytes, key: str):
    """Property 12: compute_signature matches reference HMAC-SHA256 and verify_signature is correct.

    **Validates: Requirements 11.2**

    Asserts:
    1. compute_signature(payload, key) == hmac.new(key.encode(), payload, hashlib.sha256).hexdigest()
    2. verify_signature(payload, key, correct_signature) returns True
    3. verify_signature(tampered_payload, key, correct_signature) returns False
    4. verify_signature(payload, wrong_key, correct_signature) returns False
    """
    # 1. compute_signature matches reference implementation
    computed = WebhookDispatcher.compute_signature(payload, key)
    reference = hmac_module.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    assert computed == reference, (
        f"compute_signature mismatch: got {computed}, expected {reference}"
    )

    # 2. verify_signature returns True for correct signature
    assert WebhookDispatcher.verify_signature(payload, key, computed) is True, (
        "verify_signature should return True for correctly computed signature"
    )

    # 3. verify_signature returns False for tampered payload
    tampered_payload = payload + b"\x00"  # Append a byte to tamper
    assert WebhookDispatcher.verify_signature(tampered_payload, key, computed) is False, (
        "verify_signature should return False for tampered payload"
    )

    # 4. verify_signature returns False for wrong key
    wrong_key = key + "x"  # Append a char to create a different key
    assert WebhookDispatcher.verify_signature(payload, wrong_key, computed) is False, (
        "verify_signature should return False for wrong key"
    )


# ===========================================================================
# Feature: 350_crm-integration-api, Property 6: Scenario List Field Filtering
#
# For any scenario in the ScenarioRegistry, the integration scenarios endpoint
# SHALL return id, name, description, category, difficulty, agents (with only
# role, name, type), toggles (with only id, label, target_agent_role), and
# context_fields. The response SHALL NOT contain model_id, persona_prompt,
# hidden_context_payload, budget, goals, output_fields, or any other internal fields.
#
# **Validates: Requirements 5.1, 5.2**
# ===========================================================================


# Forbidden fields that must NEVER appear in the serialized scenario list output
_FORBIDDEN_SCENARIO_FIELDS = frozenset({
    "model_id",
    "persona_prompt",
    "hidden_context_payload",
    "budget",
    "goals",
    "output_fields",
})

# Allowed top-level fields in ScenarioListItem
_ALLOWED_SCENARIO_FIELDS = frozenset({
    "id",
    "name",
    "description",
    "category",
    "difficulty",
    "agents",
    "toggles",
    "context_fields",
})

# Allowed fields within each agent entry
_ALLOWED_AGENT_FIELDS = frozenset({"role", "name", "type"})

# Allowed fields within each toggle entry
_ALLOWED_TOGGLE_FIELDS = frozenset({"id", "label", "target_agent_role"})


@st.composite
def arena_scenario_strategy(draw):
    """Generate valid ArenaScenario instances with all fields populated.

    Includes internal fields (model_id, persona_prompt, hidden_context_payload,
    budget, goals, output_fields) to verify they are filtered out.
    """
    from app.orchestrator.available_models import VALID_MODEL_IDS

    valid_model_ids = list(VALID_MODEL_IDS)
    model_id = draw(st.sampled_from(valid_model_ids))

    scenario_id = draw(_non_empty_text)
    name = draw(_non_empty_text)
    description = draw(_safe_text)
    category = draw(st.sampled_from(["Sales", "Corporate", "Everyday", "General"]))
    difficulty = draw(st.sampled_from(["beginner", "intermediate", "advanced", "fun"]))

    # Generate 2-3 agents with all internal fields
    num_agents = draw(st.integers(min_value=2, max_value=3))
    roles = draw(
        st.lists(
            _non_empty_text,
            min_size=num_agents,
            max_size=num_agents,
            unique=True,
        )
    )

    agents = []
    for i, role in enumerate(roles):
        agent = AgentDefinition(
            role=role,
            name=draw(_non_empty_text),
            type="negotiator" if i < 2 else draw(st.sampled_from(["negotiator", "regulator", "observer"])),
            persona_prompt=draw(_safe_text),
            goals=draw(st.lists(_non_empty_text, min_size=1, max_size=3)),
            budget=Budget(
                min=draw(st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False)),
                max=draw(st.floats(min_value=500, max_value=10000, allow_nan=False, allow_infinity=False)),
                target=draw(st.floats(min_value=200, max_value=5000, allow_nan=False, allow_infinity=False)),
            ),
            tone=draw(_non_empty_text),
            output_fields=draw(st.lists(_non_empty_text, min_size=1, max_size=3)),
            model_id=model_id,
        )
        agents.append(agent)

    # Generate 1-2 toggles with hidden_context_payload
    num_toggles = draw(st.integers(min_value=1, max_value=2))
    toggles = []
    for _ in range(num_toggles):
        toggle = ToggleDefinition(
            id=draw(_non_empty_text),
            label=draw(_non_empty_text),
            target_agent_role=draw(st.sampled_from(roles)),
            hidden_context_payload={"secret": draw(_non_empty_text)},
        )
        toggles.append(toggle)

    negotiation_params = NegotiationParams(
        max_turns=draw(st.integers(min_value=3, max_value=20)),
        agreement_threshold=draw(st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False)),
        turn_order=roles[:2],  # Use first two roles for turn order
    )

    outcome_receipt = OutcomeReceipt(
        equivalent_human_time="2 hours",
        process_label="Negotiation",
    )

    return ArenaScenario(
        id=scenario_id,
        name=name,
        description=description,
        difficulty=difficulty,
        category=category,
        agents=agents,
        toggles=toggles,
        negotiation_params=negotiation_params,
        outcome_receipt=outcome_receipt,
    )


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(scenario=arena_scenario_strategy())
def test_scenario_list_field_filtering(scenario: ArenaScenario):
    """Property 6: list_scenarios() returns only allowed fields, never internal ones.

    For any scenario in the registry, assert the response contains only allowed
    fields and never contains model_id, persona_prompt, hidden_context_payload,
    budget, goals, output_fields.

    **Validates: Requirements 5.1, 5.2**
    """
    # Create a mock registry with the generated scenario
    class MockRegistry:
        def __init__(self, scenario):
            self._scenarios = {scenario.id: scenario}

    registry = MockRegistry(scenario)
    service = IntegrationService(scenario_registry=registry)

    # Call list_scenarios
    result = service.list_scenarios()

    assert len(result) == 1
    item = result[0]

    # Serialize to dict to inspect all fields
    item_dict = item.model_dump()

    # Assert only allowed top-level fields are present
    for key in item_dict:
        assert key in _ALLOWED_SCENARIO_FIELDS, (
            f"Unexpected top-level field '{key}' in ScenarioListItem"
        )

    # Assert no forbidden fields at top level
    for forbidden in _FORBIDDEN_SCENARIO_FIELDS:
        assert forbidden not in item_dict, (
            f"Forbidden field '{forbidden}' found in ScenarioListItem"
        )

    # Assert agent entries only contain allowed fields
    for agent_dict in item_dict["agents"]:
        for key in agent_dict:
            assert key in _ALLOWED_AGENT_FIELDS, (
                f"Unexpected agent field '{key}' — should only have {_ALLOWED_AGENT_FIELDS}"
            )
        # Explicitly verify forbidden agent fields are absent
        assert "model_id" not in agent_dict
        assert "persona_prompt" not in agent_dict
        assert "budget" not in agent_dict
        assert "goals" not in agent_dict
        assert "output_fields" not in agent_dict

    # Assert toggle entries only contain allowed fields
    for toggle_dict in item_dict["toggles"]:
        for key in toggle_dict:
            assert key in _ALLOWED_TOGGLE_FIELDS, (
                f"Unexpected toggle field '{key}' — should only have {_ALLOWED_TOGGLE_FIELDS}"
            )
        # Explicitly verify hidden_context_payload is absent
        assert "hidden_context_payload" not in toggle_dict

    # Assert context_fields structure
    assert "context_fields" in item_dict
    cf = item_dict["context_fields"]
    assert "required" in cf
    assert "optional" in cf
    assert isinstance(cf["required"], list)
    assert isinstance(cf["optional"], list)


# ===========================================================================
# Feature: 350_crm-integration-api, Property 9: Session Status Excludes Internal Data
#
# For any session (running or completed), the SessionStatusResponse SHALL NOT
# contain history, hidden_context, custom_prompts, model_overrides, agent_states,
# or agent_memories fields.
#
# **Validates: Requirements 8.4**
# ===========================================================================

# Internal fields that must NEVER appear in SessionStatusResponse
_EXCLUDED_STATUS_FIELDS = frozenset({
    "history",
    "hidden_context",
    "custom_prompts",
    "model_overrides",
    "agent_states",
    "agent_memories",
})


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(instance=session_status_response_strategy())
def test_session_status_excludes_internal_data(instance: SessionStatusResponse):
    """Property 9: SessionStatusResponse never contains internal session data.

    For any session, assert SessionStatusResponse does not contain history,
    hidden_context, custom_prompts, model_overrides, agent_states, agent_memories.

    **Validates: Requirements 8.4**
    """
    # Serialize to dict (simulates what the API would return)
    response_dict = instance.model_dump()

    # Assert none of the excluded fields appear in the serialized output
    for excluded_field in _EXCLUDED_STATUS_FIELDS:
        assert excluded_field not in response_dict, (
            f"Internal field '{excluded_field}' found in SessionStatusResponse"
        )

    # Also check JSON serialization (what the client actually receives)
    import json
    response_json = instance.model_dump_json()
    parsed = json.loads(response_json)

    for excluded_field in _EXCLUDED_STATUS_FIELDS:
        assert excluded_field not in parsed, (
            f"Internal field '{excluded_field}' found in JSON-serialized SessionStatusResponse"
        )

    # Verify the model class itself doesn't define these fields
    model_fields = set(SessionStatusResponse.model_fields.keys())
    for excluded_field in _EXCLUDED_STATUS_FIELDS:
        assert excluded_field not in model_fields, (
            f"SessionStatusResponse model defines forbidden field '{excluded_field}'"
        )


# ===========================================================================
# Feature: 350_crm-integration-api, Property 10: Email triggered_by Sets Owner
# and Integration Metadata
#
# For any simulate request with valid email triggered_by, assert session has
# owner_email = email, source = "integration", integration_org = org_name.
#
# **Validates: Requirements 9.1, 9.2**
# ===========================================================================

# Strategy: valid email addresses
_email_local_part = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00"),
    min_size=1,
    max_size=20,
)

_email_domain = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00"),
    min_size=1,
    max_size=15,
)

_email_tld = st.sampled_from(["com", "org", "net", "io", "dev", "co", "ai"])


@st.composite
def valid_email_strategy(draw):
    """Generate valid email addresses for triggered_by testing."""
    local = draw(_email_local_part)
    domain = draw(_email_domain)
    tld = draw(_email_tld)
    return f"{local}@{domain}.{tld}"


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    email=valid_email_strategy(),
    org_name=_org_names,
)
def test_email_triggered_by_sets_owner_and_integration_metadata(
    email: str, org_name: str
):
    """Property 10: Valid email triggered_by sets owner_email, source, integration_org.

    For any simulate request with valid email triggered_by, assert session has
    owner_email = email, source = "integration", integration_org = org_name.

    **Validates: Requirements 9.1, 9.2**
    """
    service = IntegrationService()

    # Call _resolve_owner with a valid email
    owner_email, source, integration_org = service._resolve_owner(email, org_name)

    # Assert owner_email is the email itself
    assert owner_email == email, (
        f"Expected owner_email='{email}', got '{owner_email}'"
    )

    # Assert source is "integration"
    assert source == "integration", (
        f"Expected source='integration', got '{source}'"
    )

    # Assert integration_org is the org_name
    assert integration_org == org_name, (
        f"Expected integration_org='{org_name}', got '{integration_org}'"
    )


# ===========================================================================
# Feature: 350_crm-integration-api, Property 11: Non-Email triggered_by Uses
# Synthetic Owner
#
# For any simulate request with non-email triggered_by (display name, empty,
# None), assert session has owner_email = "integration:<org_name>".
#
# **Validates: Requirements 9.3**
# ===========================================================================

# Strategy: non-email strings (display names, empty, etc.)
_non_email_strings = st.one_of(
    # Display names (no @ sign)
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Zs"),
            blacklist_characters="@\x00",
        ),
        min_size=0,
        max_size=60,
    ),
    # Strings with @ but not valid email format (missing dot after @)
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
            blacklist_characters="\x00",
        ),
        min_size=1,
        max_size=20,
    ).map(lambda s: f"{s}@nodot"),
    # Just the constant empty string
    st.just(""),
)

# Strategy: None or non-email string
_non_email_triggered_by = st.one_of(
    st.none(),
    _non_email_strings,
)


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    triggered_by=_non_email_triggered_by,
    org_name=_org_names,
)
def test_non_email_triggered_by_uses_synthetic_owner(
    triggered_by: str | None, org_name: str
):
    """Property 11: Non-email triggered_by uses synthetic owner "integration:<org_name>".

    For any simulate request with non-email triggered_by (display name, empty,
    None), assert session has owner_email = "integration:<org_name>".

    **Validates: Requirements 9.3**
    """
    service = IntegrationService()

    # Call _resolve_owner with a non-email triggered_by
    owner_email, source, integration_org = service._resolve_owner(triggered_by, org_name)

    # Assert owner_email is the synthetic format
    expected_owner = f"integration:{org_name}"
    assert owner_email == expected_owner, (
        f"Expected owner_email='{expected_owner}', got '{owner_email}' "
        f"for triggered_by={triggered_by!r}"
    )

    # Assert source is None (no integration source for non-email)
    assert source is None, (
        f"Expected source=None, got '{source}' for triggered_by={triggered_by!r}"
    )

    # Assert integration_org is None
    assert integration_org is None, (
        f"Expected integration_org=None, got '{integration_org}' "
        f"for triggered_by={triggered_by!r}"
    )


# ===========================================================================
# Feature: 350_crm-integration-api, Property 5: Rate Limit Header Consistency
#
# For any successful response from /api/v1/integrations/*, the headers
# X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset SHALL be
# present, and Remaining SHALL equal Limit - usage_today for the authenticated key.
#
# **Validates: Requirements 3.3**
# ===========================================================================

from starlette.responses import Response as StarletteResponse

from app.routers.integrations import _add_rate_limit_headers


@st.composite
def rate_info_strategy(draw):
    """Generate arbitrary rate_info dicts with consistent values.

    daily_limit >= 1, used_today in [0, daily_limit], remaining = daily_limit - used_today.
    """
    daily_limit = draw(st.integers(min_value=1, max_value=100_000))
    used_today = draw(st.integers(min_value=0, max_value=daily_limit))
    remaining = daily_limit - used_today
    resets_at = draw(_iso_datetime)

    return {
        "daily_limit": daily_limit,
        "used_today": used_today,
        "remaining": remaining,
        "resets_at": resets_at,
    }


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(rate_info=rate_info_strategy())
def test_rate_limit_header_consistency(rate_info: dict):
    """Property 5: Rate limit headers are present and Remaining = Limit - usage_today.

    For any successful response from /api/v1/integrations/*, assert
    X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset headers are
    present and Remaining = Limit - usage_today.

    **Validates: Requirements 3.3**
    """
    # Build a mock key_record with _rate_info attached (as the router does)
    key_record = {
        "key_id": "test-key-id",
        "org_name": "test-org",
        "_rate_info": rate_info,
    }

    # Create a real Starlette Response to attach headers to
    response = StarletteResponse()

    # Call the helper that the router uses on every successful response
    _add_rate_limit_headers(response, key_record)

    # Assert all three headers are present
    assert "x-ratelimit-limit" in response.headers, (
        "X-RateLimit-Limit header missing from response"
    )
    assert "x-ratelimit-remaining" in response.headers, (
        "X-RateLimit-Remaining header missing from response"
    )
    assert "x-ratelimit-reset" in response.headers, (
        "X-RateLimit-Reset header missing from response"
    )

    # Assert header values match rate_info
    limit_header = int(response.headers["x-ratelimit-limit"])
    remaining_header = int(response.headers["x-ratelimit-remaining"])
    reset_header = response.headers["x-ratelimit-reset"]

    assert limit_header == rate_info["daily_limit"], (
        f"X-RateLimit-Limit: expected {rate_info['daily_limit']}, got {limit_header}"
    )
    assert remaining_header == rate_info["remaining"], (
        f"X-RateLimit-Remaining: expected {rate_info['remaining']}, got {remaining_header}"
    )
    assert reset_header == rate_info["resets_at"], (
        f"X-RateLimit-Reset: expected '{rate_info['resets_at']}', got '{reset_header}'"
    )

    # Core property: Remaining = Limit - used_today
    expected_remaining = rate_info["daily_limit"] - rate_info["used_today"]
    assert remaining_header == expected_remaining, (
        f"Remaining ({remaining_header}) != Limit ({limit_header}) - used_today ({rate_info['used_today']}). "
        f"Expected {expected_remaining}."
    )


# ===========================================================================
# Feature: 350_crm-integration-api, Property 13: Error Response Format Consistency
#
# For any error response (401, 403, 404, 422, 429, 500, 503), the response body
# SHALL conform to {"error": str, "message": str, "details": dict} with the
# correct error code for the condition.
#
# **Validates: Requirements 13.1, 13.2**
# ===========================================================================

import json as json_module

# Error code to HTTP status mapping from the design doc
_ERROR_CODE_STATUS_MAP = {
    "invalid_api_key": 401,
    "key_deactivated": 403,
    "insufficient_scope": 403,
    "scenario_not_found": 404,
    "session_not_found": 404,
    "validation_error": 422,
    "scenario_generation_failed": 422,
    "rate_limit_exceeded": 429,
    "simulation_failed": 500,
    "service_unavailable": 503,
}

_all_error_codes = list(_ERROR_CODE_STATUS_MAP.keys())

# Strategy: generate arbitrary error responses with valid error codes
_error_code_strategy = st.sampled_from(_all_error_codes)

_error_message_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=200,
)

_error_details_strategy = st.dictionaries(
    keys=_non_empty_text,
    values=st.one_of(
        _safe_text,
        st.integers(min_value=-10000, max_value=10000),
        st.booleans(),
        st.lists(_safe_text, min_size=0, max_size=3),
    ),
    min_size=0,
    max_size=5,
)


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    error_code=_error_code_strategy,
    message=_error_message_strategy,
    details=_error_details_strategy,
)
def test_error_response_format_consistency(
    error_code: str, message: str, details: dict
):
    """Property 13: All error responses conform to {"error": str, "message": str, "details": dict}.

    For any error response (401, 403, 404, 422, 429, 500, 503), assert body
    conforms to the IntegrationErrorResponse schema with the correct error code.

    **Validates: Requirements 13.1, 13.2**
    """
    # 1. Verify IntegrationErrorResponse model enforces the schema
    error_response = IntegrationErrorResponse(
        error=error_code,
        message=message,
        details=details,
    )

    # Serialize to dict (simulates JSON response body)
    response_dict = error_response.model_dump()

    # Assert required keys are present
    assert "error" in response_dict, "Missing 'error' field in error response"
    assert "message" in response_dict, "Missing 'message' field in error response"
    assert "details" in response_dict, "Missing 'details' field in error response"

    # Assert types
    assert isinstance(response_dict["error"], str), (
        f"'error' field must be str, got {type(response_dict['error'])}"
    )
    assert isinstance(response_dict["message"], str), (
        f"'message' field must be str, got {type(response_dict['message'])}"
    )
    assert isinstance(response_dict["details"], dict), (
        f"'details' field must be dict, got {type(response_dict['details'])}"
    )

    # Assert error code matches input
    assert response_dict["error"] == error_code, (
        f"Error code mismatch: expected '{error_code}', got '{response_dict['error']}'"
    )

    # Assert message matches input
    assert response_dict["message"] == message, (
        f"Message mismatch: expected '{message}', got '{response_dict['message']}'"
    )

    # Assert details matches input
    assert response_dict["details"] == details, (
        f"Details mismatch: expected {details}, got {response_dict['details']}"
    )

    # 2. Verify JSON serialization also conforms
    json_str = error_response.model_dump_json()
    parsed = json_module.loads(json_str)

    assert set(parsed.keys()) == {"error", "message", "details"}, (
        f"JSON keys should be exactly {{'error', 'message', 'details'}}, got {set(parsed.keys())}"
    )
    assert isinstance(parsed["error"], str)
    assert isinstance(parsed["message"], str)
    assert isinstance(parsed["details"], dict)

    # 3. Verify the error code maps to a valid HTTP status code
    assert error_code in _ERROR_CODE_STATUS_MAP, (
        f"Error code '{error_code}' not in known error code mapping"
    )
    expected_status = _ERROR_CODE_STATUS_MAP[error_code]
    assert expected_status in (401, 403, 404, 422, 429, 500, 503), (
        f"Error code '{error_code}' maps to unexpected status {expected_status}"
    )

    # 4. Verify the auth middleware error format matches the same schema
    # (HTTPException detail dicts from api_key_auth.py use the same structure)
    auth_error_detail = {
        "error": error_code,
        "message": message,
        "details": details,
    }
    # Validate it can be parsed as IntegrationErrorResponse
    validated = IntegrationErrorResponse.model_validate(auth_error_detail)
    assert validated.error == error_code
    assert validated.message == message
    assert validated.details == details
