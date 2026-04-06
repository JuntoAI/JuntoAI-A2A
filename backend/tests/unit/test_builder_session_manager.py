"""Unit tests for BuilderSessionManager.

Tests: create, get, add_message, update_scenario, delete, cleanup_stale,
and message limit enforcement at boundary (49, 50, 51).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.builder.session_manager import BuilderSession, BuilderSessionManager


@pytest.mark.unit
class TestBuilderSessionCreate:
    """Tests for create_session."""

    def test_create_session_returns_session(self):
        mgr = BuilderSessionManager()
        session = mgr.create_session("user@example.com")

        assert isinstance(session, BuilderSession)
        assert session.email == "user@example.com"
        assert session.session_id  # non-empty UUID string
        assert session.conversation_history == []
        assert session.partial_scenario == {}
        assert session.message_count == 0

    def test_create_session_unique_ids(self):
        mgr = BuilderSessionManager()
        s1 = mgr.create_session("a@b.com")
        s2 = mgr.create_session("a@b.com")
        assert s1.session_id != s2.session_id

    def test_create_session_timestamps_are_utc(self):
        mgr = BuilderSessionManager()
        session = mgr.create_session("t@t.com")
        assert session.created_at.tzinfo is not None
        assert session.last_activity.tzinfo is not None


@pytest.mark.unit
class TestBuilderSessionGet:
    """Tests for get_session."""

    def test_get_existing_session(self):
        mgr = BuilderSessionManager()
        session = mgr.create_session("x@y.com")
        fetched = mgr.get_session(session.session_id)
        assert fetched is session

    def test_get_nonexistent_session_returns_none(self):
        mgr = BuilderSessionManager()
        assert mgr.get_session("no-such-id") is None


@pytest.mark.unit
class TestBuilderSessionAddMessage:
    """Tests for add_message."""

    def test_add_user_message(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        mgr.add_message(s.session_id, "user", "hello")

        assert len(s.conversation_history) == 1
        assert s.conversation_history[0] == {"role": "user", "content": "hello"}
        assert s.message_count == 1

    def test_add_assistant_message_does_not_increment_count(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        mgr.add_message(s.session_id, "assistant", "hi there")

        assert len(s.conversation_history) == 1
        assert s.message_count == 0

    def test_add_message_updates_last_activity(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        before = s.last_activity
        mgr.add_message(s.session_id, "user", "ping")
        assert s.last_activity >= before

    def test_add_message_unknown_session_raises(self):
        mgr = BuilderSessionManager()
        with pytest.raises(KeyError):
            mgr.add_message("ghost", "user", "nope")

    def test_message_order_preserved(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        mgr.add_message(s.session_id, "user", "first")
        mgr.add_message(s.session_id, "assistant", "second")
        mgr.add_message(s.session_id, "user", "third")

        assert [m["content"] for m in s.conversation_history] == [
            "first",
            "second",
            "third",
        ]
        assert s.message_count == 2  # only user messages


@pytest.mark.unit
class TestBuilderSessionMessageLimit:
    """Boundary tests for the 50 user-message limit."""

    def _fill_to(self, mgr: BuilderSessionManager, session: BuilderSession, n: int):
        for i in range(n):
            mgr.add_message(session.session_id, "user", f"msg-{i}")

    def test_49_messages_allowed(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        self._fill_to(mgr, s, 49)
        assert s.message_count == 49
        # 50th should still work
        mgr.add_message(s.session_id, "user", "msg-49")
        assert s.message_count == 50

    def test_50_messages_reached(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        self._fill_to(mgr, s, 50)
        assert s.message_count == 50

    def test_51st_message_rejected(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        self._fill_to(mgr, s, 50)

        with pytest.raises(ValueError, match="message limit"):
            mgr.add_message(s.session_id, "user", "overflow")

        assert s.message_count == 50
        assert len(s.conversation_history) == 50

    def test_assistant_messages_bypass_limit(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        self._fill_to(mgr, s, 50)

        # Assistant messages should still work
        mgr.add_message(s.session_id, "assistant", "I can still reply")
        assert len(s.conversation_history) == 51
        assert s.message_count == 50


@pytest.mark.unit
class TestBuilderSessionUpdateScenario:
    """Tests for update_scenario."""

    def test_update_adds_section(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        mgr.update_scenario(s.session_id, "agents", [{"role": "Buyer"}])
        assert s.partial_scenario["agents"] == [{"role": "Buyer"}]

    def test_update_overwrites_section(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        mgr.update_scenario(s.session_id, "name", {"value": "old"})
        mgr.update_scenario(s.session_id, "name", {"value": "new"})
        assert s.partial_scenario["name"] == {"value": "new"}

    def test_update_multiple_sections(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        mgr.update_scenario(s.session_id, "name", {"value": "Test"})
        mgr.update_scenario(s.session_id, "agents", [{"role": "Seller"}])
        assert "name" in s.partial_scenario
        assert "agents" in s.partial_scenario

    def test_update_unknown_session_raises(self):
        mgr = BuilderSessionManager()
        with pytest.raises(KeyError):
            mgr.update_scenario("ghost", "name", {"value": "x"})

    def test_update_refreshes_last_activity(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        before = s.last_activity
        mgr.update_scenario(s.session_id, "id", {"value": "s1"})
        assert s.last_activity >= before


@pytest.mark.unit
class TestBuilderSessionDelete:
    """Tests for delete_session."""

    def test_delete_existing(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        mgr.delete_session(s.session_id)
        assert mgr.get_session(s.session_id) is None

    def test_delete_nonexistent_is_noop(self):
        mgr = BuilderSessionManager()
        mgr.delete_session("no-such-id")  # should not raise


@pytest.mark.unit
class TestBuilderSessionCleanupStale:
    """Tests for cleanup_stale with mocked timestamps."""

    def test_cleanup_removes_stale_sessions(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("old@e.com")

        # Manually backdate last_activity by 2 hours
        s.last_activity = datetime.now(timezone.utc) - timedelta(hours=2)

        removed = mgr.cleanup_stale(max_age_minutes=60)
        assert removed == 1
        assert mgr.get_session(s.session_id) is None

    def test_cleanup_keeps_fresh_sessions(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("fresh@e.com")
        # last_activity is "now" by default

        removed = mgr.cleanup_stale(max_age_minutes=60)
        assert removed == 0
        assert mgr.get_session(s.session_id) is not None

    def test_cleanup_mixed(self):
        mgr = BuilderSessionManager()
        stale = mgr.create_session("stale@e.com")
        fresh = mgr.create_session("fresh@e.com")

        stale.last_activity = datetime.now(timezone.utc) - timedelta(minutes=90)

        removed = mgr.cleanup_stale(max_age_minutes=60)
        assert removed == 1
        assert mgr.get_session(stale.session_id) is None
        assert mgr.get_session(fresh.session_id) is not None

    def test_cleanup_returns_count(self):
        mgr = BuilderSessionManager()
        for i in range(5):
            s = mgr.create_session(f"s{i}@e.com")
            s.last_activity = datetime.now(timezone.utc) - timedelta(hours=3)

        removed = mgr.cleanup_stale(max_age_minutes=60)
        assert removed == 5

    def test_cleanup_custom_max_age(self):
        mgr = BuilderSessionManager()
        s = mgr.create_session("u@e.com")
        s.last_activity = datetime.now(timezone.utc) - timedelta(minutes=10)

        # 5-minute TTL should catch it
        assert mgr.cleanup_stale(max_age_minutes=5) == 1
        # 15-minute TTL should not
        s2 = mgr.create_session("u2@e.com")
        s2.last_activity = datetime.now(timezone.utc) - timedelta(minutes=10)
        assert mgr.cleanup_stale(max_age_minutes=15) == 0
