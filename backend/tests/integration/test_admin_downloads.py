"""Integration tests for simulation list, transcript download, and JSON download.

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

import json
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


def _make_firestore_doc(data: dict, doc_id: str | None = None) -> MagicMock:
    doc = MagicMock()
    doc.to_dict.return_value = data
    doc.exists = True
    doc.id = doc_id or data.get("session_id", "unknown")
    return doc


def _make_missing_doc() -> MagicMock:
    doc = MagicMock()
    doc.exists = False
    return doc


def _make_async_stream(docs: list[MagicMock]):
    async def _stream():
        for doc in docs:
            yield doc
    return _stream()



def _make_session_doc(
    session_id: str,
    scenario_id: str = "talent-war",
    deal_status: str = "Agreed",
    turn_count: int = 5,
    total_tokens_used: int = 1000,
    owner_email: str = "user@example.com",
    created_at: str = "2025-01-15T10:00:00+00:00",
    max_turns: int = 15,
    active_toggles: list[str] | None = None,
    model_overrides: dict[str, str] | None = None,
    history: list[dict] | None = None,
) -> dict:
    doc = {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "deal_status": deal_status,
        "turn_count": turn_count,
        "total_tokens_used": total_tokens_used,
        "owner_email": owner_email,
        "created_at": created_at,
        "max_turns": max_turns,
        "active_toggles": active_toggles or [],
        "model_overrides": model_overrides or {},
    }
    if history is not None:
        doc["history"] = history
    return doc


def _make_sessions_db(
    session_docs: list[MagicMock],
    single_doc: MagicMock | None = None,
) -> MagicMock:
    """Build a mock Firestore db for simulation endpoints.

    Supports:
    - collection("negotiation_sessions").stream()  (list endpoint)
    - collection("negotiation_sessions").order_by().start_after().limit().stream()
    - collection("negotiation_sessions").document(id).get()
    """
    db = MagicMock()

    def collection_router(name):
        coll = MagicMock()
        if name == "negotiation_sessions":
            # Support document().get() for transcript/json endpoints
            doc_ref = AsyncMock()
            if single_doc is not None:
                doc_ref.get = AsyncMock(return_value=single_doc)
            else:
                missing = _make_missing_doc()
                doc_ref.get = AsyncMock(return_value=missing)
            coll.document.return_value = doc_ref

            # Support direct .stream() for list endpoint (in-memory sort)
            coll.stream.return_value = _make_async_stream(session_docs)

            # Support order_by().start_after().limit().stream() (legacy compat)
            query = MagicMock()
            query.start_after.return_value = query
            query.limit.return_value = query
            query.stream.return_value = _make_async_stream(session_docs)
            coll.order_by.return_value = query
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
# Test: Simulation list — basic fields (Req 5.1, 5.2)
# ---------------------------------------------------------------------------


class TestSimulationList:
    """Verify GET /admin/simulations returns correct fields and pagination."""

    async def test_returns_simulations_with_correct_fields(self, app_instance):
        """Req 5.1, 5.2: Returns session fields including all required columns."""
        session = _make_session_doc(
            "sess-001",
            scenario_id="m-and-a",
            deal_status="Blocked",
            turn_count=3,
            total_tokens_used=500,
            owner_email="admin@test.com",
            created_at="2025-01-15T10:00:00+00:00",
            max_turns=10,
            active_toggles=["competing-offer"],
            model_overrides={"Buyer": "gemini-flash"},
        )
        docs = [_make_firestore_doc(session)]
        db = _make_sessions_db(docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["simulations"]) == 1
        sim = data["simulations"][0]
        assert sim["session_id"] == "sess-001"
        assert sim["scenario_id"] == "m-and-a"
        assert sim["deal_status"] == "Blocked"
        assert sim["turn_count"] == 3
        assert sim["total_tokens_used"] == 500
        assert sim["owner_email"] == "admin@test.com"
        assert sim["max_turns"] == 10
        assert sim["active_toggles"] == ["competing-offer"]
        assert sim["model_overrides"] == {"Buyer": "gemini-flash"}
        assert sim["created_at"] == "2025-01-15T10:00:00+00:00"

    async def test_pagination_page_size_limits_results(self, app_instance):
        """Req 5.3: page_size limits the number of returned simulations."""
        sessions = [
            _make_session_doc(f"sess-{i:03d}", created_at=f"2025-01-{15-i:02d}T10:00:00+00:00")
            for i in range(5)
        ]
        docs = [_make_firestore_doc(s) for s in sessions]
        db = _make_sessions_db(docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations",
                    params={"page_size": 2},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["simulations"]) == 2

    async def test_filter_by_scenario_id(self, app_instance):
        """Req 5.4: Filter simulations by scenario_id."""
        sessions = [
            _make_session_doc("s1", scenario_id="talent-war"),
            _make_session_doc("s2", scenario_id="m-and-a"),
            _make_session_doc("s3", scenario_id="talent-war"),
        ]
        docs = [_make_firestore_doc(s) for s in sessions]
        db = _make_sessions_db(docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations",
                    params={"scenario_id": "talent-war"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        sims = resp.json()["simulations"]
        assert len(sims) == 2
        assert all(s["scenario_id"] == "talent-war" for s in sims)

    async def test_filter_by_deal_status(self, app_instance):
        """Req 5.4: Filter simulations by deal_status."""
        sessions = [
            _make_session_doc("s1", deal_status="Agreed"),
            _make_session_doc("s2", deal_status="Blocked"),
            _make_session_doc("s3", deal_status="Agreed"),
        ]
        docs = [_make_firestore_doc(s) for s in sessions]
        db = _make_sessions_db(docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations",
                    params={"deal_status": "Blocked"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        sims = resp.json()["simulations"]
        assert len(sims) == 1
        assert sims[0]["deal_status"] == "Blocked"

    async def test_filter_by_owner_email(self, app_instance):
        """Req 5.4: Filter simulations by owner_email."""
        sessions = [
            _make_session_doc("s1", owner_email="alice@test.com"),
            _make_session_doc("s2", owner_email="bob@test.com"),
        ]
        docs = [_make_firestore_doc(s) for s in sessions]
        db = _make_sessions_db(docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations",
                    params={"owner_email": "bob@test.com"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        sims = resp.json()["simulations"]
        assert len(sims) == 1
        assert sims[0]["owner_email"] == "bob@test.com"

    async def test_order_asc(self, app_instance):
        """Req 5.5: Ascending order returns results sorted oldest-first."""
        sessions = [
            _make_session_doc("s1", created_at="2025-01-10T10:00:00+00:00"),
            _make_session_doc("s2", created_at="2025-01-11T10:00:00+00:00"),
        ]
        docs = [_make_firestore_doc(s) for s in sessions]
        db = _make_sessions_db(docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations",
                    params={"order": "asc"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        sims = resp.json()["simulations"]
        assert len(sims) == 2
        # Ascending: oldest first
        assert sims[0]["created_at"] == "2025-01-10T10:00:00+00:00"
        assert sims[1]["created_at"] == "2025-01-11T10:00:00+00:00"

    async def test_empty_list(self, app_instance):
        """Returns empty list when no simulations exist."""
        db = _make_sessions_db([])

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["simulations"] == []
        assert data["next_cursor"] is None


# ---------------------------------------------------------------------------
# Test: Transcript download (Req 6.1, 6.2, 6.3, 6.6)
# ---------------------------------------------------------------------------


class TestTranscriptDownload:
    """Verify GET /admin/simulations/{id}/transcript endpoint."""

    async def test_returns_plain_text_with_content_disposition(self, app_instance):
        """Req 6.1, 6.3: Returns plain text with correct Content-Disposition."""
        session_data = _make_session_doc(
            "sess-abc",
            scenario_id="talent-war",
            deal_status="Agreed",
            history=[
                {
                    "turn_number": 1,
                    "role": "Buyer",
                    "agent_type": "negotiator",
                    "content": {
                        "inner_thought": "I should start low",
                        "public_message": "I offer 80k",
                    },
                },
            ],
        )
        doc = _make_firestore_doc(session_data)
        db = _make_sessions_db([], single_doc=doc)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations/sess-abc/transcript",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert resp.headers["content-disposition"] == 'attachment; filename="transcript_sess-abc.txt"'

    async def test_transcript_contains_turn_and_role_headers(self, app_instance):
        """Req 6.2: Transcript contains turn headers, role headers, messages."""
        session_data = _make_session_doc(
            "sess-xyz",
            scenario_id="m-and-a",
            deal_status="Blocked",
            history=[
                {
                    "turn_number": 1,
                    "role": "Buyer",
                    "agent_type": "negotiator",
                    "content": {
                        "inner_thought": "Need to negotiate hard",
                        "public_message": "I propose 5M",
                    },
                },
                {
                    "turn_number": 1,
                    "role": "Regulator",
                    "agent_type": "regulator",
                    "content": {
                        "reasoning": "Checking compliance",
                        "public_message": "Approved",
                        "status": "green",
                    },
                },
                {
                    "turn_number": 2,
                    "role": "Seller",
                    "agent_type": "negotiator",
                    "content": {
                        "inner_thought": "Too low",
                        "public_message": "Counter at 8M",
                        "proposed_price": 8000000,
                    },
                },
            ],
        )
        doc = _make_firestore_doc(session_data)
        db = _make_sessions_db([], single_doc=doc)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations/sess-xyz/transcript",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        text = resp.text

        # Verify header
        assert "=== Negotiation Transcript ===" in text
        assert "Session: sess-xyz" in text
        assert "Scenario: m-and-a" in text

        # Verify turn headers
        assert "--- Turn 1 ---" in text
        assert "--- Turn 2 ---" in text

        # Verify role headers
        assert "[Buyer]" in text
        assert "[Regulator]" in text
        assert "[Seller]" in text

        # Verify content fields
        assert "Thought: Need to negotiate hard" in text
        assert "Message: I propose 5M" in text
        assert "Thought: Checking compliance" in text
        assert "Status: green" in text
        assert "Message: Counter at 8M" in text
        assert "Price: 8000000" in text

    async def test_transcript_404_for_missing_session(self, app_instance):
        """Req 6.6: 404 when session_id does not exist."""
        db = _make_sessions_db([])  # single_doc defaults to missing

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations/nonexistent/transcript",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Session not found"


# ---------------------------------------------------------------------------
# Test: JSON download (Req 6.4, 6.5, 6.6)
# ---------------------------------------------------------------------------


class TestJsonDownload:
    """Verify GET /admin/simulations/{id}/json endpoint."""

    async def test_returns_json_with_content_disposition(self, app_instance):
        """Req 6.4, 6.5: Returns JSON with correct Content-Disposition."""
        session_data = _make_session_doc(
            "sess-json-001",
            scenario_id="b2b-sales",
            deal_status="Agreed",
        )
        doc = _make_firestore_doc(session_data)
        db = _make_sessions_db([], single_doc=doc)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations/sess-json-001/json",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        assert resp.headers["content-disposition"] == 'attachment; filename="session_sess-json-001.json"'

    async def test_json_contains_session_data(self, app_instance):
        """Req 6.4: JSON response contains the full session document."""
        session_data = _make_session_doc(
            "sess-json-002",
            scenario_id="talent-war",
            deal_status="Failed",
            turn_count=7,
            total_tokens_used=3000,
            owner_email="dev@test.com",
        )
        doc = _make_firestore_doc(session_data)
        db = _make_sessions_db([], single_doc=doc)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations/sess-json-002/json",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "sess-json-002"
        assert body["scenario_id"] == "talent-war"
        assert body["deal_status"] == "Failed"
        assert body["turn_count"] == 7
        assert body["total_tokens_used"] == 3000
        assert body["owner_email"] == "dev@test.com"

    async def test_json_404_for_missing_session(self, app_instance):
        """Req 6.6: 404 when session_id does not exist."""
        db = _make_sessions_db([])

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/simulations/nonexistent/json",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Session not found"


# ---------------------------------------------------------------------------
# CSV Export Tests
# Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
# ---------------------------------------------------------------------------

import csv
import io
from datetime import datetime, timezone


def _make_csv_export_db(
    waitlist_docs: list[MagicMock] | None = None,
    profile_docs: list[MagicMock] | None = None,
    session_docs: list[MagicMock] | None = None,
) -> MagicMock:
    """Build a mock Firestore db for CSV export endpoints.

    Supports:
    - collection("waitlist").stream()
    - collection("profiles").stream()
    - collection("negotiation_sessions").stream()
    """
    db = MagicMock()

    def collection_router(name):
        coll = MagicMock()
        if name == "waitlist":
            coll.stream.return_value = _make_async_stream(waitlist_docs or [])
        elif name == "profiles":
            coll.stream.return_value = _make_async_stream(profile_docs or [])
        elif name == "negotiation_sessions":
            coll.stream.return_value = _make_async_stream(session_docs or [])
        else:
            coll.stream.return_value = _make_async_stream([])
        return coll

    db.collection.side_effect = collection_router
    return db


def _make_waitlist_doc(
    email: str,
    signed_up_at: str = "2025-01-15T10:00:00+00:00",
    token_balance: int = 50,
    last_reset_date: str = "2025-01-15",
    user_status: str = "active",
) -> MagicMock:
    data = {
        "email": email,
        "signed_up_at": signed_up_at,
        "token_balance": token_balance,
        "last_reset_date": last_reset_date,
        "user_status": user_status,
    }
    doc = MagicMock()
    doc.to_dict.return_value = data
    doc.id = email
    doc.exists = True
    return doc


def _make_profile_doc(
    email: str,
    email_verified: bool = True,
    display_name: str = "Test User",
    profile_completed_at: str | None = None,
) -> MagicMock:
    data = {
        "email_verified": email_verified,
        "display_name": display_name,
    }
    if profile_completed_at:
        data["profile_completed_at"] = profile_completed_at
    doc = MagicMock()
    doc.to_dict.return_value = data
    doc.id = email
    doc.exists = True
    return doc


def _parse_csv(content: str) -> list[dict]:
    """Parse CSV text into a list of dicts using csv.DictReader."""
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


# ---------------------------------------------------------------------------
# Test: User CSV export (Req 7.1, 7.2, 7.3, 7.7, 7.8)
# ---------------------------------------------------------------------------


class TestUserCsvExport:
    """Verify GET /admin/export/users returns correct CSV."""

    async def test_content_disposition_header_with_todays_date(self, app_instance):
        """Req 7.3: Content-Disposition includes today's UTC date."""
        db = _make_csv_export_db()

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/users",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        expected = f'attachment; filename="users_export_{today}.csv"'
        assert resp.headers["content-disposition"] == expected
        assert "text/csv" in resp.headers["content-type"]

    async def test_csv_column_headers(self, app_instance):
        """Req 7.2: CSV has correct column headers."""
        wl = [_make_waitlist_doc("a@test.com")]
        pr = [_make_profile_doc("a@test.com")]
        db = _make_csv_export_db(waitlist_docs=wl, profile_docs=pr)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/users",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        expected_cols = [
            "email", "signed_up_at", "token_balance", "last_reset_date",
            "tier", "email_verified", "display_name", "status",
        ]
        assert list(rows[0].keys()) == expected_cols

    async def test_csv_data_rows_correct_values(self, app_instance):
        """Req 7.1, 7.2: CSV data rows contain correct values with tier computed."""
        wl = [_make_waitlist_doc("alice@test.com", token_balance=75)]
        pr = [_make_profile_doc(
            "alice@test.com",
            email_verified=True,
            display_name="Alice",
            profile_completed_at="2025-01-01T00:00:00Z",
        )]
        db = _make_csv_export_db(waitlist_docs=wl, profile_docs=pr)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/users",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        assert len(rows) == 1
        row = rows[0]
        assert row["email"] == "alice@test.com"
        assert row["token_balance"] == "75"
        assert row["tier"] == "3"  # profile_completed_at set → tier 3
        assert row["email_verified"] == "True"
        assert row["display_name"] == "Alice"
        assert row["status"] == "active"

    async def test_filter_by_tier(self, app_instance):
        """Req 7.7: tier filter param applied to user export."""
        wl = [
            _make_waitlist_doc("tier1@test.com"),
            _make_waitlist_doc("tier3@test.com"),
        ]
        pr = [
            # No profile for tier1 → tier 1
            _make_profile_doc(
                "tier3@test.com",
                profile_completed_at="2025-01-01T00:00:00Z",
            ),
        ]
        db = _make_csv_export_db(waitlist_docs=wl, profile_docs=pr)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/users",
                    params={"tier": 3},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        assert len(rows) == 1
        assert rows[0]["email"] == "tier3@test.com"
        assert rows[0]["tier"] == "3"

    async def test_filter_by_status(self, app_instance):
        """Req 7.7: status filter param applied to user export."""
        wl = [
            _make_waitlist_doc("active@test.com", user_status="active"),
            _make_waitlist_doc("banned@test.com", user_status="banned"),
        ]
        db = _make_csv_export_db(waitlist_docs=wl)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/users",
                    params={"status": "banned"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        assert len(rows) == 1
        assert rows[0]["email"] == "banned@test.com"
        assert rows[0]["status"] == "banned"

    async def test_special_characters_escaped(self, app_instance):
        """Req 7.8: Commas, quotes, newlines in field values are properly escaped."""
        wl = [_make_waitlist_doc("special@test.com")]
        pr_data = {
            "email_verified": True,
            "display_name": 'O\'Brien, "The Dev"\nLine2',
        }
        pr_doc = MagicMock()
        pr_doc.to_dict.return_value = pr_data
        pr_doc.id = "special@test.com"
        pr_doc.exists = True
        db = _make_csv_export_db(waitlist_docs=wl, profile_docs=[pr_doc])

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/users",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        # Parse back with csv.DictReader — round-trip proves escaping works
        rows = _parse_csv(resp.text)
        assert len(rows) == 1
        assert rows[0]["display_name"] == 'O\'Brien, "The Dev"\nLine2'


# ---------------------------------------------------------------------------
# Test: Simulation CSV export (Req 7.4, 7.5, 7.6, 7.7, 7.8)
# ---------------------------------------------------------------------------


class TestSimulationCsvExport:
    """Verify GET /admin/export/simulations returns correct CSV."""

    async def test_content_disposition_header_with_todays_date(self, app_instance):
        """Req 7.6: Content-Disposition includes today's UTC date."""
        db = _make_csv_export_db()

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/simulations",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        expected = f'attachment; filename="simulations_export_{today}.csv"'
        assert resp.headers["content-disposition"] == expected
        assert "text/csv" in resp.headers["content-type"]

    async def test_csv_column_headers(self, app_instance):
        """Req 7.5: CSV has correct column headers."""
        session = _make_session_doc("s1")
        docs = [_make_firestore_doc(session)]
        db = _make_csv_export_db(session_docs=docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/simulations",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        expected_cols = [
            "session_id", "scenario_id", "owner_email", "deal_status",
            "turn_count", "max_turns", "total_tokens_used",
            "active_toggles", "model_overrides", "created_at",
        ]
        assert list(rows[0].keys()) == expected_cols

    async def test_csv_data_rows_correct_values(self, app_instance):
        """Req 7.4, 7.5: CSV data rows contain correct values."""
        session = _make_session_doc(
            "sess-csv-001",
            scenario_id="m-and-a",
            deal_status="Blocked",
            turn_count=3,
            total_tokens_used=500,
            owner_email="admin@test.com",
            max_turns=10,
            active_toggles=["competing-offer"],
            model_overrides={"Buyer": "gemini-flash"},
        )
        docs = [_make_firestore_doc(session)]
        db = _make_csv_export_db(session_docs=docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/simulations",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        assert len(rows) == 1
        row = rows[0]
        assert row["session_id"] == "sess-csv-001"
        assert row["scenario_id"] == "m-and-a"
        assert row["deal_status"] == "Blocked"
        assert row["turn_count"] == "3"
        assert row["max_turns"] == "10"
        assert row["total_tokens_used"] == "500"
        assert row["owner_email"] == "admin@test.com"

    async def test_active_toggles_serialized_as_json(self, app_instance):
        """Req 7.5: active_toggles serialized as JSON string in CSV."""
        session = _make_session_doc(
            "s1",
            active_toggles=["competing-offer", "deadline-pressure"],
            model_overrides={"Buyer": "gemini-flash", "Seller": "claude-sonnet"},
        )
        docs = [_make_firestore_doc(session)]
        db = _make_csv_export_db(session_docs=docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/simulations",
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        row = rows[0]
        # Should be valid JSON strings
        toggles = json.loads(row["active_toggles"])
        assert toggles == ["competing-offer", "deadline-pressure"]
        overrides = json.loads(row["model_overrides"])
        assert overrides == {"Buyer": "gemini-flash", "Seller": "claude-sonnet"}

    async def test_filter_by_scenario_id(self, app_instance):
        """Req 7.7: scenario_id filter applied to simulation export."""
        sessions = [
            _make_session_doc("s1", scenario_id="talent-war"),
            _make_session_doc("s2", scenario_id="m-and-a"),
        ]
        docs = [_make_firestore_doc(s) for s in sessions]
        db = _make_csv_export_db(session_docs=docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/simulations",
                    params={"scenario_id": "m-and-a"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        assert len(rows) == 1
        assert rows[0]["scenario_id"] == "m-and-a"

    async def test_filter_by_deal_status(self, app_instance):
        """Req 7.7: deal_status filter applied to simulation export."""
        sessions = [
            _make_session_doc("s1", deal_status="Agreed"),
            _make_session_doc("s2", deal_status="Blocked"),
            _make_session_doc("s3", deal_status="Agreed"),
        ]
        docs = [_make_firestore_doc(s) for s in sessions]
        db = _make_csv_export_db(session_docs=docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/simulations",
                    params={"deal_status": "Agreed"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        assert len(rows) == 2
        assert all(r["deal_status"] == "Agreed" for r in rows)

    async def test_filter_by_owner_email(self, app_instance):
        """Req 7.7: owner_email filter applied to simulation export."""
        sessions = [
            _make_session_doc("s1", owner_email="alice@test.com"),
            _make_session_doc("s2", owner_email="bob@test.com"),
        ]
        docs = [_make_firestore_doc(s) for s in sessions]
        db = _make_csv_export_db(session_docs=docs)

        with patch("app.db.get_firestore_db", return_value=db):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_instance),
                base_url=BASE_URL,
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/export/simulations",
                    params={"owner_email": "bob@test.com"},
                    cookies={"admin_session": _make_valid_cookie()},
                )

        assert resp.status_code == 200
        rows = _parse_csv(resp.text)
        assert len(rows) == 1
        assert rows[0]["owner_email"] == "bob@test.com"
