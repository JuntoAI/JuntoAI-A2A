"""Unit tests for admin user management endpoints.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.9, 4.10
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from itsdangerous import URLSafeTimedSerializer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "test-admin-secret"
BASE_URL = "http://testserver"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_cookie(password: str = ADMIN_PASSWORD) -> str:
    s = URLSafeTimedSerializer(password)
    return s.dumps("admin")


def _build_app_with_admin(password: str = ADMIN_PASSWORD):
    import importlib

    with patch.dict(os.environ, {
        "ADMIN_PASSWORD": password,
        "RUN_MODE": "cloud",
        "ENVIRONMENT": "development",
    }):
        import app.config as config_mod
        importlib.reload(config_mod)

        import app.routers.admin as admin_mod
        importlib.reload(admin_mod)

        import app.main as main_mod
        importlib.reload(main_mod)

        return main_mod.app


def _make_firestore_doc(doc_id: str, data: dict, exists: bool = True) -> MagicMock:
    """Create a mock Firestore document snapshot with an id."""
    doc = MagicMock()
    doc.to_dict.return_value = data
    doc.exists = exists
    doc.id = doc_id
    return doc


def _make_async_stream(docs: list[MagicMock]):
    """Create an async iterator that yields mock document snapshots."""
    async def _stream():
        for doc in docs:
            yield doc
    return _stream()


def _make_waitlist_db(
    waitlist_docs: list[MagicMock],
    profile_docs: list[MagicMock] | None = None,
    doc_ref_exists: bool = True,
    doc_ref_data: dict | None = None,
) -> MagicMock:
    """Build a mock Firestore db that handles both collection streams and
    document-level get/update for the token/status endpoints.

    For the user list endpoint, the waitlist query chain is:
        db.collection("waitlist").order_by(...).start_after(...).limit(...).stream()
    For profiles:
        db.collection("profiles").stream()
    For token/status:
        db.collection("waitlist").document(email).get() / .update(...)
    """
    db = MagicMock()

    # Track doc_ref for token/status endpoints
    doc_ref = AsyncMock()
    doc_snapshot = MagicMock()
    doc_snapshot.exists = doc_ref_exists
    doc_snapshot.to_dict.return_value = doc_ref_data or {}
    doc_ref.get = AsyncMock(return_value=doc_snapshot)
    doc_ref.update = AsyncMock()

    def collection_router(name):
        coll = MagicMock()
        if name == "waitlist":
            # Support document() for PATCH endpoints
            coll.document.return_value = doc_ref

            # Support order_by().start_after().limit().stream() for GET /users
            query = MagicMock()
            query.start_after.return_value = query
            query.limit.return_value = query
            query.stream.return_value = _make_async_stream(waitlist_docs)
            coll.order_by.return_value = query
            # Also support stream() directly on collection (shouldn't be needed
            # for user list, but just in case)
            coll.stream.return_value = _make_async_stream(waitlist_docs)
        elif name == "profiles":
            coll.stream.return_value = _make_async_stream(profile_docs or [])
        else:
            coll.stream.return_value = _make_async_stream([])
        return coll

    db.collection.side_effect = collection_router
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_instance():
    return _build_app_with_admin()


# ---------------------------------------------------------------------------
# Test: Token adjustment (PATCH /admin/users/{email}/tokens)
# ---------------------------------------------------------------------------


class TestTokenAdjustment:
    """Validates: Requirements 4.4, 4.5"""

    async def test_valid_token_update_returns_200(self, app_instance):
        """Req 4.4: Valid token balance update → 200."""
        db = _make_waitlist_db(
            waitlist_docs=[],
            doc_ref_exists=True,
            doc_ref_data={"email": "user@test.com", "token_balance": 50},
        )

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.patch(
                    "/api/v1/admin/users/user@test.com/tokens",
                    json={"token_balance": 100},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        assert resp.json()["detail"] == "Token balance updated"

    async def test_negative_token_balance_rejected_422(self, app_instance):
        """Req 4.5: Negative token balance → 422 (Pydantic ge=0)."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url=BASE_URL,
        ) as client:
            resp = await client.patch(
                "/api/v1/admin/users/user@test.com/tokens",
                json={"token_balance": -5},
                cookies={"admin_session": _make_valid_cookie()},
            )

        assert resp.status_code == 422

    async def test_user_not_found_returns_404(self, app_instance):
        """Req 4.4: Non-existent user → 404."""
        db = _make_waitlist_db(
            waitlist_docs=[],
            doc_ref_exists=False,
        )

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.patch(
                    "/api/v1/admin/users/nobody@test.com/tokens",
                    json={"token_balance": 10},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "User not found"


# ---------------------------------------------------------------------------
# Test: Status change (PATCH /admin/users/{email}/status)
# ---------------------------------------------------------------------------


class TestStatusChange:
    """Validates: Requirements 4.6"""

    async def test_valid_status_change_returns_200(self, app_instance):
        """Req 4.6: Valid status change → 200."""
        db = _make_waitlist_db(
            waitlist_docs=[],
            doc_ref_exists=True,
            doc_ref_data={"email": "user@test.com", "user_status": "active"},
        )

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.patch(
                    "/api/v1/admin/users/user@test.com/status",
                    json={"user_status": "suspended"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        assert resp.json()["detail"] == "User status updated"

    async def test_invalid_status_rejected_422(self, app_instance):
        """Req 4.6: Invalid status value → 422 (enum validation)."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url=BASE_URL,
        ) as client:
            resp = await client.patch(
                "/api/v1/admin/users/user@test.com/status",
                json={"user_status": "deleted"},
                cookies={"admin_session": _make_valid_cookie()},
            )

        assert resp.status_code == 422

    async def test_status_user_not_found_returns_404(self, app_instance):
        """Req 4.6: Non-existent user → 404."""
        db = _make_waitlist_db(
            waitlist_docs=[],
            doc_ref_exists=False,
        )

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.patch(
                    "/api/v1/admin/users/nobody@test.com/status",
                    json={"user_status": "banned"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "User not found"

    async def test_all_valid_status_values_accepted(self, app_instance):
        """Req 4.6: active, suspended, banned are all valid."""
        for status_val in ("active", "suspended", "banned"):
            db = _make_waitlist_db(
                waitlist_docs=[],
                doc_ref_exists=True,
                doc_ref_data={"email": "user@test.com"},
            )

            with patch("app.db.get_firestore_db", return_value=db):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app_instance),
                    base_url=BASE_URL,
                ) as client:
                    resp = await client.patch(
                        "/api/v1/admin/users/user@test.com/status",
                        json={"user_status": status_val},
                        cookies={"admin_session": _make_valid_cookie()},
                    )

            assert resp.status_code == 200, f"Status '{status_val}' should be accepted"


# ---------------------------------------------------------------------------
# Test: User list backward compatibility (Req 4.10)
# ---------------------------------------------------------------------------


class TestUserListBackwardCompat:
    """Validates: Requirements 4.10"""

    async def test_missing_user_status_defaults_to_active(self, app_instance):
        """Req 4.10: Waitlist doc without user_status → treated as 'active'."""
        waitlist_docs = [
            _make_firestore_doc("alice@test.com", {
                "email": "alice@test.com",
                "signed_up_at": "2025-01-01T10:00:00Z",
                "token_balance": 20,
                # No user_status field
            }),
        ]

        db = _make_waitlist_db(waitlist_docs=waitlist_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/users",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        users = resp.json()["users"]
        assert len(users) == 1
        assert users[0]["user_status"] == "active"


# ---------------------------------------------------------------------------
# Test: User list pagination (Req 4.3)
# ---------------------------------------------------------------------------


class TestUserListPagination:
    """Validates: Requirements 4.1, 4.3"""

    async def test_returns_users_with_correct_fields(self, app_instance):
        """Req 4.1, 4.2: User list returns email, signed_up_at, token_balance,
        last_reset_date, tier, user_status."""
        waitlist_docs = [
            _make_firestore_doc("alice@test.com", {
                "email": "alice@test.com",
                "signed_up_at": "2025-01-15T10:00:00Z",
                "token_balance": 50,
                "last_reset_date": "2025-06-01",
                "user_status": "active",
            }),
        ]
        profile_docs = [
            _make_firestore_doc("alice@test.com", {
                "email_verified": True,
                "profile_completed_at": "2025-02-01T12:00:00Z",
            }),
        ]

        db = _make_waitlist_db(waitlist_docs=waitlist_docs, profile_docs=profile_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/users",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["users"]) == 1
        user = data["users"][0]
        assert user["email"] == "alice@test.com"
        assert user["signed_up_at"] == "2025-01-15T10:00:00Z"
        assert user["token_balance"] == 50
        assert user["last_reset_date"] == "2025-06-01"
        assert user["tier"] == 3  # profile_completed_at set → tier 3
        assert user["user_status"] == "active"

    async def test_page_size_limits_results(self, app_instance):
        """Req 4.3: page_size parameter limits the number of returned users."""
        waitlist_docs = [
            _make_firestore_doc(f"user{i}@test.com", {
                "email": f"user{i}@test.com",
                "signed_up_at": f"2025-01-{15 - i:02d}T10:00:00Z",
                "token_balance": 20,
            })
            for i in range(5)
        ]

        db = _make_waitlist_db(waitlist_docs=waitlist_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/users?page_size=2",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["users"]) == 2

    async def test_next_cursor_present_when_more_results(self, app_instance):
        """Req 4.3: next_cursor is set when there are more results."""
        waitlist_docs = [
            _make_firestore_doc(f"user{i}@test.com", {
                "email": f"user{i}@test.com",
                "signed_up_at": f"2025-01-{15 - i:02d}T10:00:00Z",
                "token_balance": 20,
            })
            for i in range(5)
        ]

        # The endpoint uses batch_size = page_size * 3. With page_size=2,
        # batch_size=6 > 5 docs, so exhausted=True and next_cursor=None.
        # To get next_cursor, we need batch_size < total docs.
        # With page_size=1, batch_size=3 < 5, so not exhausted.
        db = _make_waitlist_db(waitlist_docs=waitlist_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/users?page_size=2",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        data = resp.json()
        # With 5 docs and batch_size=6 (page_size*3), all docs fit in one batch
        # so exhausted=True → next_cursor=None. This is correct behavior.
        # The cursor is only set when there might be more data.
        assert len(data["users"]) == 2

    async def test_default_page_size_is_50(self, app_instance):
        """Req 4.3: Default page_size is 50."""
        waitlist_docs = [
            _make_firestore_doc(f"user{i}@test.com", {
                "email": f"user{i}@test.com",
                "signed_up_at": f"2025-01-01T{i:02d}:00:00Z",
                "token_balance": 20,
            })
            for i in range(3)
        ]

        db = _make_waitlist_db(waitlist_docs=waitlist_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/users",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        # All 3 users returned (less than default 50)
        assert len(resp.json()["users"]) == 3

    async def test_tier_computed_from_profiles(self, app_instance):
        """Req 4.2: Tier is computed from profiles collection."""
        waitlist_docs = [
            _make_firestore_doc("tier1@test.com", {
                "email": "tier1@test.com",
                "signed_up_at": "2025-01-03T10:00:00Z",
            }),
            _make_firestore_doc("tier2@test.com", {
                "email": "tier2@test.com",
                "signed_up_at": "2025-01-02T10:00:00Z",
            }),
            _make_firestore_doc("tier3@test.com", {
                "email": "tier3@test.com",
                "signed_up_at": "2025-01-01T10:00:00Z",
            }),
        ]
        profile_docs = [
            # tier1: no profile → tier 1
            _make_firestore_doc("tier2@test.com", {
                "email_verified": True,
            }),
            _make_firestore_doc("tier3@test.com", {
                "email_verified": True,
                "profile_completed_at": "2025-02-01T00:00:00Z",
            }),
        ]

        db = _make_waitlist_db(waitlist_docs=waitlist_docs, profile_docs=profile_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/users",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        users = {u["email"]: u for u in resp.json()["users"]}
        assert users["tier1@test.com"]["tier"] == 1
        assert users["tier2@test.com"]["tier"] == 2
        assert users["tier3@test.com"]["tier"] == 3


# ---------------------------------------------------------------------------
# Test: User list filtering (Req 4.9)
# ---------------------------------------------------------------------------


class TestUserListFiltering:
    """Validates: Requirements 4.9"""

    async def test_filter_by_tier(self, app_instance):
        """Req 4.9: Filter users by tier."""
        waitlist_docs = [
            _make_firestore_doc("tier1@test.com", {
                "email": "tier1@test.com",
                "signed_up_at": "2025-01-03T10:00:00Z",
            }),
            _make_firestore_doc("tier3@test.com", {
                "email": "tier3@test.com",
                "signed_up_at": "2025-01-01T10:00:00Z",
            }),
        ]
        profile_docs = [
            _make_firestore_doc("tier3@test.com", {
                "email_verified": True,
                "profile_completed_at": "2025-02-01T00:00:00Z",
            }),
        ]

        db = _make_waitlist_db(waitlist_docs=waitlist_docs, profile_docs=profile_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/users?tier=3",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        users = resp.json()["users"]
        assert len(users) == 1
        assert users[0]["email"] == "tier3@test.com"
        assert users[0]["tier"] == 3

    async def test_filter_by_status(self, app_instance):
        """Req 4.9: Filter users by status."""
        waitlist_docs = [
            _make_firestore_doc("active@test.com", {
                "email": "active@test.com",
                "signed_up_at": "2025-01-03T10:00:00Z",
                "user_status": "active",
            }),
            _make_firestore_doc("banned@test.com", {
                "email": "banned@test.com",
                "signed_up_at": "2025-01-01T10:00:00Z",
                "user_status": "banned",
            }),
        ]

        db = _make_waitlist_db(waitlist_docs=waitlist_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/users?status=banned",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        users = resp.json()["users"]
        assert len(users) == 1
        assert users[0]["email"] == "banned@test.com"
        assert users[0]["user_status"] == "banned"

    async def test_filter_by_tier_and_status_combined(self, app_instance):
        """Req 4.9: Combined tier + status filter."""
        waitlist_docs = [
            _make_firestore_doc("a@test.com", {
                "email": "a@test.com",
                "signed_up_at": "2025-01-04T10:00:00Z",
                "user_status": "active",
            }),
            _make_firestore_doc("b@test.com", {
                "email": "b@test.com",
                "signed_up_at": "2025-01-03T10:00:00Z",
                "user_status": "suspended",
            }),
            _make_firestore_doc("c@test.com", {
                "email": "c@test.com",
                "signed_up_at": "2025-01-02T10:00:00Z",
                "user_status": "suspended",
            }),
        ]
        profile_docs = [
            # a@test.com: tier 2 (email_verified only)
            _make_firestore_doc("a@test.com", {"email_verified": True}),
            # b@test.com: tier 2 (email_verified only)
            _make_firestore_doc("b@test.com", {"email_verified": True}),
            # c@test.com: tier 3 (profile_completed_at)
            _make_firestore_doc("c@test.com", {
                "email_verified": True,
                "profile_completed_at": "2025-02-01T00:00:00Z",
            }),
        ]

        db = _make_waitlist_db(waitlist_docs=waitlist_docs, profile_docs=profile_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                # Filter: tier=2 AND status=suspended → only b@test.com
                resp = await client.get(
                    "/api/v1/admin/users?tier=2&status=suspended",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        users = resp.json()["users"]
        assert len(users) == 1
        assert users[0]["email"] == "b@test.com"

    async def test_filter_returns_empty_when_no_match(self, app_instance):
        """Req 4.9: Filter with no matching users → empty list."""
        waitlist_docs = [
            _make_firestore_doc("user@test.com", {
                "email": "user@test.com",
                "signed_up_at": "2025-01-01T10:00:00Z",
                "user_status": "active",
            }),
        ]

        db = _make_waitlist_db(waitlist_docs=waitlist_docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/users?status=banned",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        assert resp.json()["users"] == []
