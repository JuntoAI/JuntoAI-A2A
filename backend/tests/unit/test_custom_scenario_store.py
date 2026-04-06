"""Unit tests for CustomScenarioStore (Firestore) and SQLiteCustomScenarioStore.

Tests cover: save, list, get, delete, count, limit enforcement, document
structure, profile existence check, and sub-collection path.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.builder.scenario_store import (
    MAX_PER_USER,
    CustomScenarioStore,
    SQLiteCustomScenarioStore,
)
from app.scenarios.models import ArenaScenario


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_scenario_dict() -> dict:
    return {
        "id": "unit-test",
        "name": "Unit Test Scenario",
        "description": "For unit testing",
        "agents": [
            {
                "role": "Buyer", "name": "Alice", "type": "negotiator",
                "persona_prompt": "You are a buyer.", "goals": ["Buy low"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "assertive", "output_fields": ["proposed_price"],
                "model_id": "test-model",
            },
            {
                "role": "Seller", "name": "Bob", "type": "negotiator",
                "persona_prompt": "You are a seller.", "goals": ["Sell high"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "firm", "output_fields": ["proposed_price"],
                "model_id": "test-model",
            },
        ],
        "toggles": [{
            "id": "t1", "label": "Secret", "target_agent_role": "Buyer",
            "hidden_context_payload": {"info": "secret"},
        }],
        "negotiation_params": {
            "max_turns": 10, "agreement_threshold": 1000.0,
            "turn_order": ["Buyer", "Seller"],
        },
        "outcome_receipt": {
            "equivalent_human_time": "~1 week", "process_label": "Test",
        },
    }


@pytest.fixture()
def scenario() -> ArenaScenario:
    return ArenaScenario.model_validate(_valid_scenario_dict())


# ---------------------------------------------------------------------------
# Firestore CustomScenarioStore — mocked
# ---------------------------------------------------------------------------

class TestFirestoreCustomScenarioStore:
    """Tests for the Firestore-backed CustomScenarioStore."""

    def _make_store(self, profile_exists: bool = True, existing_count: int = 0):
        """Build a CustomScenarioStore with mocked Firestore and ProfileClient."""
        profile_client = MagicMock()
        if profile_exists:
            profile_client.get_profile = AsyncMock(return_value={"email": "user@test.com"})
        else:
            profile_client.get_profile = AsyncMock(return_value=None)

        mock_db = MagicMock()

        # Build sub-collection chain
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.id = "mock-scenario-id"
        doc_mock.to_dict = MagicMock(return_value={
            "scenario_json": _valid_scenario_dict(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })

        # stream() returns an async iterator of docs
        async def _stream():
            for i in range(existing_count):
                d = MagicMock()
                d.id = f"scenario-{i}"
                d.to_dict = MagicMock(return_value={
                    "scenario_json": _valid_scenario_dict(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                yield d

        sub_collection_ref = MagicMock()
        sub_collection_ref.stream = _stream
        sub_collection_ref.document = MagicMock()

        inner_doc_ref = MagicMock()
        inner_doc_ref.set = AsyncMock()
        inner_doc_ref.get = AsyncMock(return_value=doc_mock)
        inner_doc_ref.delete = AsyncMock()
        sub_collection_ref.document.return_value = inner_doc_ref

        profile_doc_ref = MagicMock()
        profile_doc_ref.collection = MagicMock(return_value=sub_collection_ref)

        profiles_collection = MagicMock()
        profiles_collection.document = MagicMock(return_value=profile_doc_ref)

        mock_db.collection = MagicMock(return_value=profiles_collection)

        with patch("app.db.get_firestore_db", return_value=mock_db):
            store = CustomScenarioStore(profile_client=profile_client)

        # Expose mocks for assertions
        store._mock_db = mock_db
        store._mock_profile_client = profile_client
        store._mock_sub_collection = sub_collection_ref
        store._mock_inner_doc_ref = inner_doc_ref
        store._mock_profiles_collection = profiles_collection
        store._mock_profile_doc_ref = profile_doc_ref
        return store

    @pytest.mark.asyncio
    async def test_save_success(self, scenario):
        store = self._make_store(profile_exists=True, existing_count=0)
        sid = await store.save("user@test.com", scenario)
        assert isinstance(sid, str)
        assert len(sid) > 0
        store._mock_inner_doc_ref.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_document_structure(self, scenario):
        """Stored document has scenario_json, created_at, updated_at — no email."""
        store = self._make_store(profile_exists=True, existing_count=0)
        await store.save("user@test.com", scenario)

        call_args = store._mock_inner_doc_ref.set.call_args[0][0]
        assert "scenario_json" in call_args
        assert "created_at" in call_args
        assert "updated_at" in call_args
        assert "email" not in call_args

    @pytest.mark.asyncio
    async def test_save_fails_no_profile(self, scenario):
        store = self._make_store(profile_exists=False)
        with pytest.raises(HTTPException) as exc_info:
            await store.save("nobody@test.com", scenario)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_save_fails_at_limit(self, scenario):
        store = self._make_store(profile_exists=True, existing_count=20)
        with pytest.raises(HTTPException) as exc_info:
            await store.save("user@test.com", scenario)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_save_succeeds_at_19(self, scenario):
        store = self._make_store(profile_exists=True, existing_count=19)
        sid = await store.save("user@test.com", scenario)
        assert isinstance(sid, str)

    @pytest.mark.asyncio
    async def test_list_by_email(self):
        store = self._make_store(existing_count=3)
        results = await store.list_by_email("user@test.com")
        assert len(results) == 3
        for r in results:
            assert "scenario_id" in r
            assert "scenario_json" in r

    @pytest.mark.asyncio
    async def test_get_existing(self):
        store = self._make_store()
        doc = await store.get("user@test.com", "some-id")
        assert doc is not None
        assert "scenario_id" in doc

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        store = self._make_store()
        # Override doc.exists to False
        not_found = MagicMock()
        not_found.exists = False
        store._mock_inner_doc_ref.get = AsyncMock(return_value=not_found)
        doc = await store.get("user@test.com", "nonexistent")
        assert doc is None

    @pytest.mark.asyncio
    async def test_delete_existing(self):
        store = self._make_store()
        result = await store.delete("user@test.com", "some-id")
        assert result is True
        store._mock_inner_doc_ref.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        store = self._make_store()
        not_found = MagicMock()
        not_found.exists = False
        store._mock_inner_doc_ref.get = AsyncMock(return_value=not_found)
        result = await store.delete("user@test.com", "nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_count_by_email(self):
        store = self._make_store(existing_count=5)
        count = await store.count_by_email("user@test.com")
        assert count == 5

    @pytest.mark.asyncio
    async def test_sub_collection_path(self, scenario):
        """Verify the sub-collection path is profiles/{email}/custom_scenarios/{id}."""
        store = self._make_store(profile_exists=True, existing_count=0)
        await store.save("alice@example.com", scenario)

        # Verify collection("profiles") was called
        store._mock_db.collection.assert_called_with("profiles")
        # Verify document(email) was called
        store._mock_profiles_collection.document.assert_called_with("alice@example.com")
        # Verify collection("custom_scenarios") was called
        store._mock_profile_doc_ref.collection.assert_called_with("custom_scenarios")


# ---------------------------------------------------------------------------
# SQLite CustomScenarioStore — real database
# ---------------------------------------------------------------------------

class TestSQLiteCustomScenarioStore:
    """Tests for the SQLite-backed store using temp databases."""

    @pytest.mark.asyncio
    async def test_save_and_get(self, scenario):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            sid = await store.save("user@test.com", scenario)
            doc = await store.get("user@test.com", sid)
            assert doc is not None
            assert doc["scenario_id"] == sid
            assert doc["scenario_json"]["id"] == "unit-test"

    @pytest.mark.asyncio
    async def test_save_document_structure(self, scenario):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            sid = await store.save("user@test.com", scenario)
            doc = await store.get("user@test.com", sid)
            assert "scenario_json" in doc
            assert "created_at" in doc
            assert "updated_at" in doc
            # email is NOT in the document (it's a query param, not stored in doc payload)
            assert "email" not in doc

    @pytest.mark.asyncio
    async def test_list_by_email(self, scenario):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            await store.save("user@test.com", scenario)
            await store.save("user@test.com", scenario)
            await store.save("other@test.com", scenario)

            results = await store.list_by_email("user@test.com")
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_delete(self, scenario):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            sid = await store.save("user@test.com", scenario)
            assert await store.delete("user@test.com", sid) is True
            assert await store.get("user@test.com", sid) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            assert await store.delete("user@test.com", "nope") is False

    @pytest.mark.asyncio
    async def test_count_by_email(self, scenario):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            for _ in range(5):
                await store.save("user@test.com", scenario)
            assert await store.count_by_email("user@test.com") == 5
            assert await store.count_by_email("other@test.com") == 0

    @pytest.mark.asyncio
    async def test_limit_at_19(self, scenario):
        """19 scenarios: save succeeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            for _ in range(19):
                await store.save("user@test.com", scenario)
            sid = await store.save("user@test.com", scenario)
            assert isinstance(sid, str)
            assert await store.count_by_email("user@test.com") == 20

    @pytest.mark.asyncio
    async def test_limit_at_20(self, scenario):
        """20 scenarios: 21st save rejected with 409."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            for _ in range(20):
                await store.save("user@test.com", scenario)
            with pytest.raises(HTTPException) as exc_info:
                await store.save("user@test.com", scenario)
            assert exc_info.value.status_code == 409
            assert await store.count_by_email("user@test.com") == 20

    @pytest.mark.asyncio
    async def test_limit_at_21(self, scenario):
        """Multiple attempts past 20 all fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            for _ in range(20):
                await store.save("user@test.com", scenario)
            for _ in range(3):
                with pytest.raises(HTTPException) as exc_info:
                    await store.save("user@test.com", scenario)
                assert exc_info.value.status_code == 409
            assert await store.count_by_email("user@test.com") == 20

    @pytest.mark.asyncio
    async def test_isolation_between_users(self, scenario):
        """Limit is per-user, not global."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCustomScenarioStore(db_path=f"{tmpdir}/test.db")
            for _ in range(20):
                await store.save("alice@test.com", scenario)
            # Bob can still save
            sid = await store.save("bob@test.com", scenario)
            assert isinstance(sid, str)
