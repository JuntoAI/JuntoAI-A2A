"""Tests for SSEConnectionTracker: acquire, release, limits, independence."""

import pytest

from app.middleware.sse_limiter import SSEConnectionTracker


@pytest.fixture()
def tracker():
    return SSEConnectionTracker()


class TestAcquire:
    async def test_acquire_up_to_max(self, tracker):
        for _ in range(3):
            assert await tracker.acquire("user@test.com") is True

    async def test_fourth_acquire_returns_false(self, tracker):
        for _ in range(3):
            await tracker.acquire("user@test.com")
        assert await tracker.acquire("user@test.com") is False


class TestRelease:
    async def test_release_decrements(self, tracker):
        await tracker.acquire("user@test.com")
        await tracker.acquire("user@test.com")
        await tracker.release("user@test.com")
        # Should be able to acquire again (now at 1, limit 3)
        assert await tracker.acquire("user@test.com") is True
        assert await tracker.acquire("user@test.com") is True
        # Now at 3 again
        assert await tracker.acquire("user@test.com") is False

    async def test_release_floors_at_zero(self, tracker):
        # Release without any acquire should not go negative
        await tracker.release("nobody@test.com")
        # Should still be able to acquire normally
        assert await tracker.acquire("nobody@test.com") is True


class TestIndependence:
    async def test_different_emails_independent(self, tracker):
        for _ in range(3):
            await tracker.acquire("a@test.com")
        # a is maxed out
        assert await tracker.acquire("a@test.com") is False
        # b should be unaffected
        assert await tracker.acquire("b@test.com") is True
