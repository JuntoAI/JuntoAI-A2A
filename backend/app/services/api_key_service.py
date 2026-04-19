"""API Key Service — org token generation, hashing, validation, and rate-limit checking.

Manages per-org integration tokens with domain allowlisting. No scopes — all
authenticated orgs get full access to the integration API. Rate limiting is
per-org (daily + per-minute).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db.base import ApiKeyStore

DEFAULT_RATE_LIMIT_PER_MINUTE = 10


class ApiKeyService:
    """Manages org token lifecycle: generation, validation, rate limiting, deactivation."""

    def __init__(self, store: ApiKeyStore) -> None:
        self._store = store

    @staticmethod
    def generate_raw_key() -> str:
        """Generate a raw org token: a2a_live_<base64url 32 random bytes>."""
        random_bytes = secrets.token_bytes(32)
        encoded = base64.urlsafe_b64encode(random_bytes).decode("ascii")
        return f"a2a_live_{encoded}"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Compute SHA-256 hex digest of a raw org token."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def generate_key(
        self,
        org_name: str,
        domain: str,
        created_by_email: str,
        rate_limit_daily: int | None = None,
        rate_limit_per_minute: int | None = None,
    ) -> tuple[str, dict]:
        """Generate a new org token and persist the record.

        Returns (raw_key, key_record). The raw key is shown once only.
        """
        raw_key = self.generate_raw_key()
        key_hash = self.hash_key(raw_key)

        # Extract prefix: first 4 chars after "a2a_live_"
        key_prefix = raw_key[len("a2a_live_"):len("a2a_live_") + 4]

        if rate_limit_daily is None:
            rate_limit_daily = (
                settings.DEFAULT_RATE_LIMIT_DAILY_CLOUD
                if settings.RUN_MODE == "cloud"
                else settings.DEFAULT_RATE_LIMIT_DAILY_LOCAL
            )

        if rate_limit_per_minute is None:
            rate_limit_per_minute = settings.DEFAULT_RATE_LIMIT_PER_MINUTE

        now = datetime.now(timezone.utc).isoformat()

        key_record = {
            "key_id": str(uuid.uuid4()),
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "org_name": org_name,
            "domain": domain.lower().strip(),
            "created_by_email": created_by_email,
            "rate_limit_daily": rate_limit_daily,
            "rate_limit_per_minute": rate_limit_per_minute,
            "active": True,
            "created_at": now,
            "last_used_at": None,
            "usage_today": 0,
            "usage_today_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "minute_window_start": None,
            "minute_window_count": 0,
        }

        await self._store.create_key(key_record)
        return raw_key, key_record

    async def validate_key(self, raw_key: str) -> dict | None:
        """Validate an org token by hash lookup.

        Returns the key record if found, or None if no match.
        Updates last_used_at on successful lookup.
        """
        key_hash = self.hash_key(raw_key)
        record = await self._store.get_key_by_hash(key_hash)

        if record is None:
            return None

        # Update last_used_at
        now = datetime.now(timezone.utc).isoformat()
        await self._store.update_key(record["key_id"], {"last_used_at": now})
        record["last_used_at"] = now

        return record

    async def check_rate_limit(self, key_record: dict) -> tuple[bool, dict]:
        """Check daily and per-minute rate limits for an org.

        Returns (allowed, rate_info) where rate_info contains:
        - daily_limit, used_today, remaining, resets_at
        - retry_after_seconds (only if rejected)
        """
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        key_id = key_record["key_id"]

        # Reset daily counter if date has changed
        usage_today_date = key_record.get("usage_today_date")
        if usage_today_date != today_str:
            await self._store.reset_daily_usage(key_id)
            key_record["usage_today"] = 0
            key_record["usage_today_date"] = today_str

        daily_limit = key_record["rate_limit_daily"]
        used_today = key_record["usage_today"]

        # Calculate midnight UTC reset time
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        resets_at = tomorrow.isoformat()

        # Check daily limit
        if used_today >= daily_limit:
            seconds_until_reset = (tomorrow - now).total_seconds()
            rate_info = {
                "daily_limit": daily_limit,
                "used_today": used_today,
                "remaining": 0,
                "resets_at": resets_at,
                "retry_after_seconds": int(seconds_until_reset) + 1,
            }
            return False, rate_info

        # Check per-minute limit
        per_minute_limit = key_record["rate_limit_per_minute"]
        minute_window_start = key_record.get("minute_window_start")
        minute_window_count = key_record.get("minute_window_count", 0)

        if minute_window_start is not None:
            try:
                window_start = datetime.fromisoformat(minute_window_start)
                if window_start.tzinfo is None:
                    window_start = window_start.replace(tzinfo=timezone.utc)
                elapsed = (now - window_start).total_seconds()

                if elapsed < 60 and minute_window_count >= per_minute_limit:
                    retry_after = int(60 - elapsed) + 1
                    rate_info = {
                        "daily_limit": daily_limit,
                        "used_today": used_today,
                        "remaining": daily_limit - used_today,
                        "resets_at": resets_at,
                        "retry_after_seconds": retry_after,
                    }
                    return False, rate_info

                if elapsed >= 60:
                    minute_window_start = None
                    minute_window_count = 0
            except (ValueError, TypeError):
                minute_window_start = None
                minute_window_count = 0

        # Allowed — increment counters
        new_usage = await self._store.increment_usage(key_id)
        key_record["usage_today"] = new_usage

        # Update per-minute window
        if minute_window_start is None or minute_window_count == 0:
            new_window_start = now.isoformat()
            new_window_count = 1
        else:
            new_window_start = minute_window_start
            new_window_count = minute_window_count + 1

        await self._store.update_key(
            key_id,
            {
                "minute_window_start": new_window_start,
                "minute_window_count": new_window_count,
            },
        )

        rate_info = {
            "daily_limit": daily_limit,
            "used_today": new_usage,
            "remaining": daily_limit - new_usage,
            "resets_at": resets_at,
        }
        return True, rate_info

    async def deactivate_key(self, key_id: str) -> None:
        """Soft-delete: set active=false on the org token record."""
        await self._store.deactivate_key(key_id)
