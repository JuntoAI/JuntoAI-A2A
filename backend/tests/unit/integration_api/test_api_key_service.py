"""Unit tests for the API Key Service.

Tests cover:
- Default rate limits for cloud mode (100) and local mode (1000)
- Key deactivation preserves record (soft-delete)
- key_prefix extraction from raw key
- last_used_at update on validation
- Daily usage counter reset at midnight UTC
- Per-minute window tracking

Requirements: 1.1, 1.2, 1.4, 1.5, 2.5, 3.1
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.db.api_key_store import SQLiteApiKeyClient
from app.services.api_key_service import ApiKeyService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path():
    """Create a temporary SQLite database file and clean up after test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture()
def store(db_path):
    """Create a SQLiteApiKeyClient backed by a temp file."""
    return SQLiteApiKeyClient(db_path=db_path)


@pytest.fixture()
def service(store):
    """Create an ApiKeyService with the temp-file store."""
    return ApiKeyService(store=store)


# ---------------------------------------------------------------------------
# Test: Default rate limits for cloud mode (100) and local mode (1000) (Requirement 1.4)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_default_rate_limit_cloud_mode(service):
    """In cloud mode, default daily rate limit is 100."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "cloud"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="CloudOrg",
            domain="cloud.com",
            created_by_email="admin@cloud.com",
            rate_limit_daily=None,
        )

    assert key_record["rate_limit_daily"] == 100


@pytest.mark.unit
@pytest.mark.asyncio
async def test_default_rate_limit_local_mode(service):
    """In local mode, default daily rate limit is 1000."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="LocalOrg",
            domain="local.com",
            created_by_email="admin@local.com",
            rate_limit_daily=None,
        )

    assert key_record["rate_limit_daily"] == 1000


@pytest.mark.unit
@pytest.mark.asyncio
async def test_explicit_rate_limit_overrides_default(service):
    """When rate_limit_daily is explicitly provided, it overrides the default."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "cloud"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="CustomOrg",
            domain="custom.com",
            created_by_email="admin@custom.com",
            rate_limit_daily=500,
        )

    assert key_record["rate_limit_daily"] == 500


# ---------------------------------------------------------------------------
# Test: Domain stored in key record
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_domain_stored_in_key_record(service):
    """The domain parameter is stored in the key record."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="DomainOrg",
            domain="example.com",
            created_by_email="admin@example.com",
        )

    assert key_record["domain"] == "example.com"


# ---------------------------------------------------------------------------
# Test: Key deactivation preserves record (soft-delete) (Requirement 1.5)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deactivation_preserves_record(service, store):
    """Deactivating a key sets active=false but preserves the full record."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="DeactivateOrg",
            domain="deactivate.com",
            created_by_email="admin@deactivate.com",
        )

    key_id = key_record["key_id"]

    # Deactivate
    await service.deactivate_key(key_id)

    # Verify record still exists but is inactive
    record = await store.get_key_by_id(key_id)
    assert record is not None
    assert record["active"] is False
    # All other fields preserved
    assert record["key_id"] == key_id
    assert record["org_name"] == "DeactivateOrg"
    assert record["created_by_email"] == "admin@deactivate.com"
    assert record["key_hash"] == key_record["key_hash"]
    assert record["domain"] == "deactivate.com"


# ---------------------------------------------------------------------------
# Test: key_prefix extraction from raw key (Requirement 1.2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_key_prefix_extraction(service):
    """key_prefix is the first 4 characters after 'a2a_live_' in the raw key."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="PrefixOrg",
            domain="prefix.com",
            created_by_email="admin@prefix.com",
        )

    # Verify prefix matches first 4 chars after "a2a_live_"
    expected_prefix = raw_key[len("a2a_live_"):len("a2a_live_") + 4]
    assert key_record["key_prefix"] == expected_prefix
    assert len(key_record["key_prefix"]) == 4


@pytest.mark.unit
def test_raw_key_format():
    """Generated raw key starts with 'a2a_live_' and has sufficient length."""
    raw_key = ApiKeyService.generate_raw_key()
    assert raw_key.startswith("a2a_live_")
    # 32 bytes base64url encoded = 44 chars (with padding) or 43 (without)
    suffix = raw_key[len("a2a_live_"):]
    assert len(suffix) >= 40  # base64url of 32 bytes is at least 43 chars


# ---------------------------------------------------------------------------
# Test: last_used_at update on validation (Requirement 2.5)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_last_used_at_updated_on_validation(service, store):
    """Validating a key updates last_used_at timestamp."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="ValidationOrg",
            domain="validation.com",
            created_by_email="admin@validation.com",
        )

    # Initially last_used_at is None
    assert key_record["last_used_at"] is None

    # Validate the key
    validated = await service.validate_key(raw_key)

    # last_used_at should now be set
    assert validated is not None
    assert validated["last_used_at"] is not None

    # Verify it's a valid ISO timestamp
    parsed = datetime.fromisoformat(validated["last_used_at"])
    assert parsed.tzinfo is not None or "+" in validated["last_used_at"]

    # Verify it's stored in the database
    record = await store.get_key_by_id(key_record["key_id"])
    assert record["last_used_at"] is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_key_returns_none_for_invalid_key(service):
    """Validating a non-existent key returns None."""
    result = await service.validate_key("a2a_live_nonexistentkey12345678901234567890ab")
    assert result is None


# ---------------------------------------------------------------------------
# Test: Daily usage counter reset at midnight UTC (Requirement 3.1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_daily_usage_counter_reset_at_midnight(service, store):
    """When the date changes, usage_today resets to 0 before checking limits."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="ResetOrg",
            domain="reset.com",
            created_by_email="admin@reset.com",
            rate_limit_daily=100,
        )

    key_id = key_record["key_id"]

    # Simulate yesterday's usage: set usage_today_date to yesterday
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    await store.update_key(key_id, {
        "usage_today": 99,
        "usage_today_date": yesterday,
    })

    # Update key_record to reflect stored state
    key_record["usage_today"] = 99
    key_record["usage_today_date"] = yesterday

    # check_rate_limit should detect the date change and reset
    allowed, rate_info = await service.check_rate_limit(key_record)

    assert allowed is True
    # After reset, usage should be 1 (the current request was counted)
    assert rate_info["used_today"] == 1
    assert rate_info["remaining"] == 99


@pytest.mark.unit
@pytest.mark.asyncio
async def test_daily_limit_enforced_when_exhausted(service, store):
    """When usage_today >= rate_limit_daily, request is rejected."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="ExhaustedOrg",
            domain="exhausted.com",
            created_by_email="admin@exhausted.com",
            rate_limit_daily=10,
        )

    key_id = key_record["key_id"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Set usage to the limit
    await store.update_key(key_id, {
        "usage_today": 10,
        "usage_today_date": today,
    })
    key_record["usage_today"] = 10
    key_record["usage_today_date"] = today

    allowed, rate_info = await service.check_rate_limit(key_record)

    assert allowed is False
    assert rate_info["remaining"] == 0
    assert "retry_after_seconds" in rate_info
    assert rate_info["retry_after_seconds"] > 0


# ---------------------------------------------------------------------------
# Test: Per-minute window tracking (Requirement 3.1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_per_minute_limit_enforced(service, store):
    """When minute_window_count >= rate_limit_per_minute within 60s, request is rejected."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="MinuteOrg",
            domain="minute.com",
            created_by_email="admin@minute.com",
            rate_limit_daily=1000,
            rate_limit_per_minute=5,
        )

    key_id = key_record["key_id"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc)

    # Set up: within daily limit but per-minute exhausted
    window_start = (now - timedelta(seconds=10)).isoformat()
    await store.update_key(key_id, {
        "usage_today": 3,
        "usage_today_date": today,
        "minute_window_start": window_start,
        "minute_window_count": 5,
    })
    key_record["usage_today"] = 3
    key_record["usage_today_date"] = today
    key_record["minute_window_start"] = window_start
    key_record["minute_window_count"] = 5

    allowed, rate_info = await service.check_rate_limit(key_record)

    assert allowed is False
    assert "retry_after_seconds" in rate_info
    assert rate_info["retry_after_seconds"] > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_per_minute_window_resets_after_60_seconds(service, store):
    """When the minute window is older than 60s, it resets and allows the request."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="WindowResetOrg",
            domain="windowreset.com",
            created_by_email="admin@windowreset.com",
            rate_limit_daily=1000,
            rate_limit_per_minute=5,
        )

    key_id = key_record["key_id"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc)

    # Set up: minute window expired (started 90 seconds ago) with high count
    window_start = (now - timedelta(seconds=90)).isoformat()
    await store.update_key(key_id, {
        "usage_today": 3,
        "usage_today_date": today,
        "minute_window_start": window_start,
        "minute_window_count": 100,
    })
    key_record["usage_today"] = 3
    key_record["usage_today_date"] = today
    key_record["minute_window_start"] = window_start
    key_record["minute_window_count"] = 100

    allowed, rate_info = await service.check_rate_limit(key_record)

    # Should be allowed because the window expired
    assert allowed is True
    assert rate_info["used_today"] == 4  # incremented from 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_successful_request_increments_counters(service, store):
    """A successful rate limit check increments usage_today."""
    with patch("app.services.api_key_service.settings") as mock_settings:
        mock_settings.RUN_MODE = "local"
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL = 1000
        mock_settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD = 100
        mock_settings.DEFAULT_RATE_LIMIT_PER_MINUTE = 10

        raw_key, key_record = await service.generate_key(
            org_name="IncrementOrg",
            domain="increment.com",
            created_by_email="admin@increment.com",
            rate_limit_daily=100,
            rate_limit_per_minute=10,
        )

    key_id = key_record["key_id"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    await store.update_key(key_id, {
        "usage_today": 5,
        "usage_today_date": today,
    })
    key_record["usage_today"] = 5
    key_record["usage_today_date"] = today

    allowed, rate_info = await service.check_rate_limit(key_record)

    assert allowed is True
    assert rate_info["used_today"] == 6
    assert rate_info["remaining"] == 94

    # Verify in database
    record = await store.get_key_by_id(key_id)
    assert record["usage_today"] == 6
