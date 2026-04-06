"""Custom scenario persistence — Firestore and SQLite implementations.

Stores user-created scenarios as sub-documents under the user's profile:
  Firestore: ``profiles/{email}/custom_scenarios/{scenario_id}``
  SQLite:    ``custom_scenarios`` table with email + scenario_id columns
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from app.scenarios.models import ArenaScenario

MAX_PER_USER = 20


class CustomScenarioStore:
    """Firestore-backed custom scenario persistence.

    Documents live at ``profiles/{email}/custom_scenarios/{scenario_id}``
    with fields: ``scenario_json``, ``created_at``, ``updated_at``.
    The owner email is implicit from the parent document path.
    """

    SUB_COLLECTION = "custom_scenarios"

    def __init__(self, profile_client) -> None:
        from app.db import get_firestore_db

        self._profile_client = profile_client
        self._db = get_firestore_db()

    def _scenarios_ref(self, email: str):
        """Return the sub-collection reference for a user's custom scenarios."""
        return self._db.collection("profiles").document(email).collection(self.SUB_COLLECTION)

    async def save(self, email: str, scenario: ArenaScenario) -> str:
        """Persist a scenario. Returns the generated scenario_id.

        Raises:
            HTTPException 403 — profile does not exist
            HTTPException 409 — user already has MAX_PER_USER scenarios
        """
        profile = await self._profile_client.get_profile(email)
        if profile is None:
            raise HTTPException(
                status_code=403,
                detail="Profile required. Please create a profile first.",
            )

        count = await self.count_by_email(email)
        if count >= MAX_PER_USER:
            raise HTTPException(
                status_code=409,
                detail=f"Maximum {MAX_PER_USER} custom scenarios. Delete an existing scenario to save a new one.",
            )

        scenario_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc_data = {
            "scenario_json": scenario.model_dump(),
            "created_at": now,
            "updated_at": now,
        }
        await self._scenarios_ref(email).document(scenario_id).set(doc_data)
        return scenario_id

    async def list_by_email(self, email: str) -> list[dict]:
        """Return all custom scenarios for a user."""
        docs = self._scenarios_ref(email).stream()
        results: list[dict] = []
        async for doc in docs:
            data = doc.to_dict()
            data["scenario_id"] = doc.id
            results.append(data)
        return results

    async def get(self, email: str, scenario_id: str) -> dict | None:
        """Return a single scenario document or ``None``."""
        doc = await self._scenarios_ref(email).document(scenario_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["scenario_id"] = doc.id
        return data

    async def delete(self, email: str, scenario_id: str) -> bool:
        """Delete a scenario. Returns True if it existed."""
        doc_ref = self._scenarios_ref(email).document(scenario_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        await doc_ref.delete()
        return True

    async def count_by_email(self, email: str) -> int:
        """Return the number of custom scenarios for a user."""
        count = 0
        async for _ in self._scenarios_ref(email).stream():
            count += 1
        return count


# ---------------------------------------------------------------------------
# SQLite implementation (local mode)
# ---------------------------------------------------------------------------

import aiosqlite

_CREATE_CUSTOM_SCENARIOS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS custom_scenarios (
    scenario_id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    scenario_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


class SQLiteCustomScenarioStore:
    """SQLite-backed custom scenario persistence for local mode."""

    def __init__(self, db_path: str = "data/juntoai.db") -> None:
        self._db_path = db_path
        self._table_ready = False

    async def _get_connection(self) -> aiosqlite.Connection:
        parent = os.path.dirname(self._db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = await aiosqlite.connect(self._db_path)
        if not self._table_ready:
            await conn.execute(_CREATE_CUSTOM_SCENARIOS_TABLE_SQL)
            await conn.commit()
            self._table_ready = True
        return conn

    async def save(self, email: str, scenario: ArenaScenario) -> str:
        """Persist a scenario. Returns the generated scenario_id."""
        count = await self.count_by_email(email)
        if count >= MAX_PER_USER:
            raise HTTPException(
                status_code=409,
                detail=f"Maximum {MAX_PER_USER} custom scenarios. Delete an existing scenario to save a new one.",
            )

        scenario_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._get_connection()
        try:
            await conn.execute(
                "INSERT INTO custom_scenarios (scenario_id, email, scenario_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (scenario_id, email, json.dumps(scenario.model_dump()), now, now),
            )
            await conn.commit()
        finally:
            await conn.close()
        return scenario_id

    async def list_by_email(self, email: str) -> list[dict]:
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT scenario_id, scenario_json, created_at, updated_at "
                "FROM custom_scenarios WHERE email = ? ORDER BY created_at DESC",
                (email,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "scenario_id": r[0],
                    "scenario_json": json.loads(r[1]),
                    "created_at": r[2],
                    "updated_at": r[3],
                }
                for r in rows
            ]
        finally:
            await conn.close()

    async def get(self, email: str, scenario_id: str) -> dict | None:
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT scenario_id, scenario_json, created_at, updated_at "
                "FROM custom_scenarios WHERE scenario_id = ? AND email = ?",
                (scenario_id, email),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return {
                "scenario_id": row[0],
                "scenario_json": json.loads(row[1]),
                "created_at": row[2],
                "updated_at": row[3],
            }
        finally:
            await conn.close()

    async def delete(self, email: str, scenario_id: str) -> bool:
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "DELETE FROM custom_scenarios WHERE scenario_id = ? AND email = ?",
                (scenario_id, email),
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    async def count_by_email(self, email: str) -> int:
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM custom_scenarios WHERE email = ?",
                (email,),
            )
            row = await cursor.fetchone()
            return row[0]
        finally:
            await conn.close()
