"""Integration tests for share router endpoints.

Feature: 192_social-sharing
Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.exceptions import SessionNotFoundError
from app.main import app
from app.models.share import SharePayload, SocialPostText
from app.scenarios.router import get_scenario_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_EMAIL = "owner@example.com"
_TEST_SESSION_ID = "sess-abc-123"
_TEST_SLUG = "aB3dEf9x"
_TEST_IMAGE_URL = "/api/v1/share/images/placeholder.png"


def _make_session_doc(
    deal_status: str = "Agreed",
    owner_email: str = _TEST_EMAIL,
) -> dict:
    """Return a minimal session document dict."""
    return {
        "session_id": _TEST_SESSION_ID,
        "scenario_id": "test-scenario",
        "deal_status": deal_status,
        "current_offer": 500_000.0,
        "turn_count": 5,
        "warning_count": 1,
        "max_turns": 10,
        "owner_email": owner_email,
        "duration_seconds": 42,
        "participant_summaries": [
            {
                "role": "Buyer",
                "name": "Alice",
                "agent_type": "negotiator",
                "summary": "Negotiated aggressively.",
            },
        ],
    }


def _mock_registry() -> MagicMock:
    """Build a mock ScenarioRegistry that returns a valid scenario."""
    from app.scenarios.models import ArenaScenario

    registry = MagicMock()
    scenario = MagicMock(spec=ArenaScenario)
    scenario.name = "Test Scenario"
    scenario.description = "A test scenario"
    registry.get_scenario.return_value = scenario
    return registry


# ---------------------------------------------------------------------------
# Happy-path POST /api/v1/share — one test per deal status
# ---------------------------------------------------------------------------


class TestCreateShareHappyPath:
    """POST /api/v1/share returns 200 with correct payload for each terminal status."""

    @pytest.mark.parametrize("deal_status", ["Agreed", "Blocked", "Failed"])
    async def test_create_share_returns_200(self, deal_status: str):
        mock_share_store = MagicMock()
        mock_share_store.get_share_by_session = AsyncMock(return_value=None)
        mock_share_store.get_share = AsyncMock(return_value=None)
        mock_share_store.create_share = AsyncMock()

        mock_session_store = MagicMock()
        mock_session_store.get_session_doc = AsyncMock(
            return_value=_make_session_doc(deal_status=deal_status)
        )

        registry = _mock_registry()
        app.dependency_overrides[get_scenario_registry] = lambda: registry

        try:
            with (
                patch(
                    "app.services.share_service.get_share_store",
                    return_value=mock_share_store,
                ),
                patch(
                    "app.services.share_service.get_session_store",
                    return_value=mock_session_store,
                ),
                patch(
                    "app.services.share_service.generate_share_image",
                    new=AsyncMock(return_value=_TEST_IMAGE_URL),
                ),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    resp = await client.post(
                        "/api/v1/share",
                        json={
                            "session_id": _TEST_SESSION_ID,
                            "email": _TEST_EMAIL,
                        },
                    )

            assert resp.status_code == 200
            body = resp.json()
            assert "share_slug" in body
            assert "share_url" in body
            assert "social_post_text" in body
            assert "share_image_url" in body

            # Social post text has all three platform variants
            spt = body["social_post_text"]
            assert "twitter" in spt
            assert "linkedin" in spt
            assert "facebook" in spt

            # Share store was called to persist
            mock_share_store.create_share.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Error cases: 404 missing session, 403 wrong email
# ---------------------------------------------------------------------------


class TestCreateShareErrors:
    """POST /api/v1/share error responses."""

    async def test_missing_session_returns_404(self):
        mock_share_store = MagicMock()
        mock_share_store.get_share_by_session = AsyncMock(return_value=None)

        mock_session_store = MagicMock()
        mock_session_store.get_session_doc = AsyncMock(
            side_effect=SessionNotFoundError(_TEST_SESSION_ID)
        )

        registry = _mock_registry()
        app.dependency_overrides[get_scenario_registry] = lambda: registry

        try:
            with (
                patch(
                    "app.services.share_service.get_share_store",
                    return_value=mock_share_store,
                ),
                patch(
                    "app.services.share_service.get_session_store",
                    return_value=mock_session_store,
                ),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    resp = await client.post(
                        "/api/v1/share",
                        json={
                            "session_id": _TEST_SESSION_ID,
                            "email": _TEST_EMAIL,
                        },
                    )

            assert resp.status_code == 404
            assert _TEST_SESSION_ID in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    async def test_wrong_email_returns_403(self):
        mock_share_store = MagicMock()
        mock_share_store.get_share_by_session = AsyncMock(return_value=None)

        mock_session_store = MagicMock()
        mock_session_store.get_session_doc = AsyncMock(
            return_value=_make_session_doc(owner_email="real-owner@example.com")
        )

        registry = _mock_registry()
        app.dependency_overrides[get_scenario_registry] = lambda: registry

        try:
            with (
                patch(
                    "app.services.share_service.get_share_store",
                    return_value=mock_share_store,
                ),
                patch(
                    "app.services.share_service.get_session_store",
                    return_value=mock_session_store,
                ),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    resp = await client.post(
                        "/api/v1/share",
                        json={
                            "session_id": _TEST_SESSION_ID,
                            "email": "intruder@example.com",
                        },
                    )

            assert resp.status_code == 403
            assert "Email does not match" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/v1/share/{slug} — happy path and 404
# ---------------------------------------------------------------------------


class TestGetShare:
    """GET /api/v1/share/{share_slug} endpoint tests."""

    async def test_get_share_returns_payload(self):
        from datetime import datetime, timezone

        payload = SharePayload(
            share_slug=_TEST_SLUG,
            session_id=_TEST_SESSION_ID,
            scenario_id="test-scenario",
            scenario_name="Test Scenario",
            scenario_description="A test scenario",
            deal_status="Agreed",
            outcome_text="Deal agreed at $500,000.00",
            final_offer=500_000.0,
            turns_completed=5,
            warning_count=1,
            participant_summaries=[],
            evaluation_scores=None,
            public_conversation=[],
            elapsed_time_ms=42_000,
            share_image_url=_TEST_IMAGE_URL,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        mock_share_store = MagicMock()
        mock_share_store.get_share = AsyncMock(return_value=payload)

        try:
            with patch(
                "app.services.share_service.get_share_store",
                return_value=mock_share_store,
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    resp = await client.get(f"/api/v1/share/{_TEST_SLUG}")

            assert resp.status_code == 200
            body = resp.json()
            assert body["share_slug"] == _TEST_SLUG
            assert body["deal_status"] == "Agreed"
            assert body["scenario_name"] == "Test Scenario"
            assert body["final_offer"] == 500_000.0
        finally:
            app.dependency_overrides.clear()

    async def test_get_share_missing_slug_returns_404(self):
        mock_share_store = MagicMock()
        mock_share_store.get_share = AsyncMock(return_value=None)

        try:
            with patch(
                "app.services.share_service.get_share_store",
                return_value=mock_share_store,
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    resp = await client.get("/api/v1/share/nonExist1")

            assert resp.status_code == 404
            assert "nonExist1" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Idempotency: POST twice → same slug
# ---------------------------------------------------------------------------


class TestIdempotency:
    """POST /api/v1/share twice with same session_id returns same slug."""

    async def test_second_post_returns_existing_share(self):
        from datetime import datetime, timezone

        existing_payload = SharePayload(
            share_slug=_TEST_SLUG,
            session_id=_TEST_SESSION_ID,
            scenario_id="test-scenario",
            scenario_name="Test Scenario",
            scenario_description="A test scenario",
            deal_status="Agreed",
            outcome_text="Deal agreed at $500,000.00",
            final_offer=500_000.0,
            turns_completed=5,
            warning_count=1,
            participant_summaries=[],
            evaluation_scores=None,
            public_conversation=[],
            elapsed_time_ms=42_000,
            share_image_url=_TEST_IMAGE_URL,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        # First call: no existing share → creates one
        # Second call: existing share found → returns it
        mock_share_store = MagicMock()
        mock_share_store.get_share_by_session = AsyncMock(
            side_effect=[None, existing_payload]
        )
        mock_share_store.get_share = AsyncMock(return_value=None)
        mock_share_store.create_share = AsyncMock()

        mock_session_store = MagicMock()
        mock_session_store.get_session_doc = AsyncMock(
            return_value=_make_session_doc()
        )

        registry = _mock_registry()
        app.dependency_overrides[get_scenario_registry] = lambda: registry

        try:
            with (
                patch(
                    "app.services.share_service.get_share_store",
                    return_value=mock_share_store,
                ),
                patch(
                    "app.services.share_service.get_session_store",
                    return_value=mock_session_store,
                ),
                patch(
                    "app.services.share_service.generate_share_image",
                    new=AsyncMock(return_value=_TEST_IMAGE_URL),
                ),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    # First POST — creates share
                    resp1 = await client.post(
                        "/api/v1/share",
                        json={
                            "session_id": _TEST_SESSION_ID,
                            "email": _TEST_EMAIL,
                        },
                    )
                    assert resp1.status_code == 200
                    slug1 = resp1.json()["share_slug"]

                    # Second POST — returns existing
                    resp2 = await client.post(
                        "/api/v1/share",
                        json={
                            "session_id": _TEST_SESSION_ID,
                            "email": _TEST_EMAIL,
                        },
                    )
                    assert resp2.status_code == 200
                    slug2 = resp2.json()["share_slug"]

            # Both calls return the same slug
            assert slug2 == _TEST_SLUG
            # create_share was only called once (first request)
            mock_share_store.create_share.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()
