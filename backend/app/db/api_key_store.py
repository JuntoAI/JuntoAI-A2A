"""Async API key store implementations for dual-mode persistence (Firestore + SQLite)."""

import json
import os
from datetime import datetime, timezone

import aiosqlite

from app.exceptions import DatabaseConnectionError

_CREATE_API_KEYS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS integration_api_keys (
    key_id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    org_name TEXT NOT NULL,
    created_by_email TEXT NOT NULL,
    scopes TEXT NOT NULL,
    rate_limit_daily INTEGER NOT NULL DEFAULT 1000,
    rate_limit_per_minute INTEGER NOT NULL DEFAULT 10,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    usage_today INTEGER NOT NULL DEFAULT 0,
    usage_today_date TEXT,
    minute_window_start TEXT,
    minute_window_count INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_API_KEYS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON integration_api_keys(key_hash)
"""


class SQLiteApiKeyClient:
    """Implements the ``ApiKeyStore`` protocol using aiosqlite.

    The constructor is synchronous. Table creation happens lazily on the
    first database operation via ``_get_connection()``.
    """

    def __init__(self, db_path: str = "data/juntoai.db") -> None:
        self._db_path = db_path
        self._table_ready = False

    async def _get_connection(self) -> aiosqlite.Connection:
        """Open a connection and ensure the table exists."""
        try:
            parent = os.path.dirname(self._db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            conn = await aiosqlite.connect(self._db_path)
        except Exception as e:
            raise DatabaseConnectionError(
                f"Failed to open SQLite database at {self._db_path}: {e}"
            ) from e

        if not self._table_ready:
            await conn.execute(_CREATE_API_KEYS_TABLE_SQL)
            await conn.execute(_CREATE_API_KEYS_INDEX_SQL)
            await conn.commit()
            self._table_ready = True

        return conn

    def _row_to_dict(self, row: tuple, cursor_description: list) -> dict:
        """Convert a SQLite row tuple to a dict, deserializing JSON fields."""
        columns = [desc[0] for desc in cursor_description]
        record = dict(zip(columns, row))
        # Deserialize scopes from JSON string to list
        if "scopes" in record and isinstance(record["scopes"], str):
            record["scopes"] = json.loads(record["scopes"])
        # Convert active from int to bool
        if "active" in record:
            record["active"] = bool(record["active"])
        return record

    async def create_key(self, key_record: dict) -> None:
        """Insert a new API key record."""
        conn = await self._get_connection()
        try:
            # Serialize scopes list to JSON string
            scopes_json = json.dumps(key_record.get("scopes", []))
            await conn.execute(
                """INSERT INTO integration_api_keys
                (key_id, key_hash, key_prefix, org_name, created_by_email,
                 scopes, rate_limit_daily, rate_limit_per_minute, active,
                 created_at, last_used_at, usage_today, usage_today_date,
                 minute_window_start, minute_window_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    key_record["key_id"],
                    key_record["key_hash"],
                    key_record["key_prefix"],
                    key_record["org_name"],
                    key_record["created_by_email"],
                    scopes_json,
                    key_record.get("rate_limit_daily", 1000),
                    key_record.get("rate_limit_per_minute", 10),
                    1 if key_record.get("active", True) else 0,
                    key_record["created_at"],
                    key_record.get("last_used_at"),
                    key_record.get("usage_today", 0),
                    key_record.get("usage_today_date"),
                    key_record.get("minute_window_start"),
                    key_record.get("minute_window_count", 0),
                ),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def get_key_by_hash(self, key_hash: str) -> dict | None:
        """Look up an API key record by its SHA-256 hash. Returns None if not found."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT * FROM integration_api_keys WHERE key_hash = ?",
                (key_hash,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_dict(row, cursor.description)
        finally:
            await conn.close()

    async def get_key_by_id(self, key_id: str) -> dict | None:
        """Look up an API key record by key_id. Returns None if not found."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT * FROM integration_api_keys WHERE key_id = ?",
                (key_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_dict(row, cursor.description)
        finally:
            await conn.close()

    async def update_key(self, key_id: str, updates: dict) -> None:
        """Update fields on an existing API key record."""
        conn = await self._get_connection()
        try:
            # Build SET clause dynamically from updates
            set_parts = []
            values = []
            for key, value in updates.items():
                if key == "scopes":
                    set_parts.append(f"{key} = ?")
                    values.append(json.dumps(value))
                elif key == "active":
                    set_parts.append(f"{key} = ?")
                    values.append(1 if value else 0)
                else:
                    set_parts.append(f"{key} = ?")
                    values.append(value)

            if not set_parts:
                return

            values.append(key_id)
            await conn.execute(
                f"UPDATE integration_api_keys SET {', '.join(set_parts)} WHERE key_id = ?",
                tuple(values),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def deactivate_key(self, key_id: str) -> None:
        """Set active to 0 (soft-delete)."""
        conn = await self._get_connection()
        try:
            await conn.execute(
                "UPDATE integration_api_keys SET active = 0 WHERE key_id = ?",
                (key_id,),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def increment_usage(self, key_id: str) -> int:
        """Atomically increment usage_today and return the new value."""
        conn = await self._get_connection()
        try:
            await conn.execute(
                "UPDATE integration_api_keys SET usage_today = usage_today + 1 WHERE key_id = ?",
                (key_id,),
            )
            await conn.commit()
            cursor = await conn.execute(
                "SELECT usage_today FROM integration_api_keys WHERE key_id = ?",
                (key_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
        finally:
            await conn.close()

    async def reset_daily_usage(self, key_id: str) -> None:
        """Reset usage_today to 0 and update usage_today_date."""
        conn = await self._get_connection()
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            await conn.execute(
                "UPDATE integration_api_keys SET usage_today = 0, usage_today_date = ? WHERE key_id = ?",
                (today, key_id),
            )
            await conn.commit()
        finally:
            await conn.close()


class FirestoreApiKeyClient:
    """Implements the ``ApiKeyStore`` protocol using Firestore.

    Uses the ``integration_api_keys`` collection with document ID = ``key_id``.
    Scopes are stored as a native Firestore array.
    """

    COLLECTION = "integration_api_keys"

    def __init__(self, db=None, project: str | None = None) -> None:
        if db is not None:
            self._db = db
        else:
            from google.cloud import firestore

            self._db = firestore.AsyncClient(project=project)
        self._collection = self._db.collection(self.COLLECTION)

    async def create_key(self, key_record: dict) -> None:
        """Write a new API key document keyed by key_id."""
        doc_ref = self._collection.document(key_record["key_id"])
        await doc_ref.set(key_record)

    async def get_key_by_hash(self, key_hash: str) -> dict | None:
        """Query for an API key by its SHA-256 hash. Returns None if not found."""
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._collection.where(
            filter=FieldFilter("key_hash", "==", key_hash)
        ).limit(1)
        async for doc in query.stream():
            return doc.to_dict()
        return None

    async def get_key_by_id(self, key_id: str) -> dict | None:
        """Read an API key document by key_id. Returns None if not found."""
        doc = await self._collection.document(key_id).get()
        if not doc.exists:
            return None
        return doc.to_dict()

    async def update_key(self, key_id: str, updates: dict) -> None:
        """Merge fields into an existing API key document."""
        doc_ref = self._collection.document(key_id)
        await doc_ref.update(updates)

    async def deactivate_key(self, key_id: str) -> None:
        """Set active to False (soft-delete)."""
        doc_ref = self._collection.document(key_id)
        await doc_ref.update({"active": False})

    async def increment_usage(self, key_id: str) -> int:
        """Atomically increment usage_today and return the new value."""
        from google.cloud.firestore_v1 import transforms

        doc_ref = self._collection.document(key_id)
        await doc_ref.update({"usage_today": transforms.Increment(1)})
        # Read back the updated value
        doc = await doc_ref.get()
        data = doc.to_dict()
        return data.get("usage_today", 0)

    async def reset_daily_usage(self, key_id: str) -> None:
        """Reset usage_today to 0 and update usage_today_date."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        doc_ref = self._collection.document(key_id)
        await doc_ref.update({"usage_today": 0, "usage_today_date": today})
