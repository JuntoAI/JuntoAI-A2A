"""Unit tests for SSEEventBuffer: append, replay, isolation, terminal flag."""

import pytest

from app.middleware.event_buffer import SSEEventBuffer


@pytest.fixture()
def buffer():
    return SSEEventBuffer()


@pytest.mark.unit
class TestAppendSequentialIDs:
    async def test_append_returns_sequential_ids(self, buffer):
        id1 = await buffer.append("sess-1", "event-a")
        id2 = await buffer.append("sess-1", "event-b")
        id3 = await buffer.append("sess-1", "event-c")
        assert (id1, id2, id3) == (1, 2, 3)


@pytest.mark.unit
class TestReplayAfterZero:
    async def test_replay_after_zero_returns_all(self, buffer):
        await buffer.append("sess-1", "evt-1")
        await buffer.append("sess-1", "evt-2")
        await buffer.append("sess-1", "evt-3")

        result = await buffer.replay_after("sess-1", 0)
        assert result == [(1, "evt-1"), (2, "evt-2"), (3, "evt-3")]


@pytest.mark.unit
class TestReplayAfterPartial:
    async def test_replay_after_id_returns_only_later_events(self, buffer):
        await buffer.append("sess-1", "evt-1")
        await buffer.append("sess-1", "evt-2")
        await buffer.append("sess-1", "evt-3")
        await buffer.append("sess-1", "evt-4")

        result = await buffer.replay_after("sess-1", 2)
        assert result == [(3, "evt-3"), (4, "evt-4")]


@pytest.mark.unit
class TestTerminalFlag:
    async def test_terminal_event_is_stored(self, buffer):
        await buffer.append("sess-1", "evt-1")
        await buffer.append("sess-1", "final", is_terminal=True)

        assert await buffer.is_session_terminal("sess-1") is True

    async def test_non_terminal_session(self, buffer):
        await buffer.append("sess-1", "evt-1")

        assert await buffer.is_session_terminal("sess-1") is False


@pytest.mark.unit
class TestSessionIsolation:
    async def test_different_sessions_are_isolated(self, buffer):
        await buffer.append("sess-a", "a-evt-1")
        await buffer.append("sess-a", "a-evt-2")
        await buffer.append("sess-b", "b-evt-1")

        replay_b = await buffer.replay_after("sess-b", 0)
        assert replay_b == [(1, "b-evt-1")]

        replay_a = await buffer.replay_after("sess-a", 0)
        assert replay_a == [(1, "a-evt-1"), (2, "a-evt-2")]


@pytest.mark.unit
class TestNonExistentSession:
    async def test_replay_after_nonexistent_session_returns_empty(self, buffer):
        result = await buffer.replay_after("no-such-session", 0)
        assert result == []

    async def test_is_terminal_nonexistent_session_returns_false(self, buffer):
        assert await buffer.is_session_terminal("no-such-session") is False
