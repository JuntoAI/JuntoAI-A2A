"""Async SQLite clients for negotiation session and share persistence (local mode)."""

import json
import os
from datetime import datetime, timezone

import aiosqlite

from app.exceptions import DatabaseConnectionError, SessionNotFoundError
from app.models.negotiation import NegotiationStateModel
from app.models.share import SharePayload

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS negotiation_sessions (
    session_id TEXT PRIMARY KEY,
    data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


class SQLiteSessionClient:
    """Implements the ``SessionStore`` protocol using aiosqlite.

    The constructor is synchronous. Table creation happens lazily on the
    first database operation via ``_ensure_table()``.
    """

    def __init__(self, db_path: str = "data/juntoai.db") -> None:
        self._db_path = db_path
        self._table_ready = False

    async def _get_connection(self) -> aiosqlite.Connection:
        """Open a connection and ensure the table exists."""
        try:
            # Ensure parent directory exists
            parent = os.path.dirname(self._db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            conn = await aiosqlite.connect(self._db_path)
        except Exception as e:
            raise DatabaseConnectionError(
                f"Failed to open SQLite database at {self._db_path}: {e}"
            ) from e

        if not self._table_ready:
            await conn.execute(_CREATE_TABLE_SQL)
            await conn.commit()
            self._table_ready = True

        return conn

    async def create_session(self, state: NegotiationStateModel) -> None:
        """Serialize and insert a new session row."""
        conn = await self._get_connection()
        try:
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                "INSERT INTO negotiation_sessions (session_id, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (state.session_id, state.model_dump_json(), now, now),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def get_session(self, session_id: str) -> NegotiationStateModel:
        """Read and deserialize a session. Raises SessionNotFoundError if missing."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT data FROM negotiation_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise SessionNotFoundError(session_id)
            return NegotiationStateModel.model_validate_json(row[0])
        finally:
            await conn.close()

    async def get_session_doc(self, session_id: str) -> dict:
        """Read a raw session document dict. Raises SessionNotFoundError if missing."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT data FROM negotiation_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise SessionNotFoundError(session_id)
            return json.loads(row[0])
        finally:
            await conn.close()

    async def update_session(self, session_id: str, updates: dict) -> None:
        """Merge updates into existing session JSON. Raises SessionNotFoundError if missing."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT data FROM negotiation_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise SessionNotFoundError(session_id)

            existing = json.loads(row[0])
            existing.update(updates)
            now = datetime.now(timezone.utc).isoformat()

            await conn.execute(
                "UPDATE negotiation_sessions SET data = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(existing), now, session_id),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def list_sessions_by_owner(
        self, owner_email: str, since: str
    ) -> list[dict]:
        """Return session dicts for *owner_email* created at or after *since*.

        Uses the indexed ``created_at`` column for date filtering, then checks
        ``owner_email`` inside the JSON ``data`` column in Python (local-mode
        volumes make a full-table scan acceptable).
        """
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT data FROM negotiation_sessions "
                "WHERE created_at >= ? ORDER BY created_at DESC",
                (since,),
            )
            rows = await cursor.fetchall()
            results: list[dict] = []
            for (raw,) in rows:
                doc = json.loads(raw)
                if doc.get("owner_email") == owner_email:
                    results.append(doc)
            return results
        finally:
            await conn.close()

    async def list_sessions_by_scenario(
        self, scenario_id: str, owner_email: str
    ) -> list[dict]:
        """Return session dicts where ``scenario_id`` and ``owner_email`` match.

        Consistent with ``list_sessions_by_owner``: fetches all rows then
        filters the JSON ``data`` column in Python.
        """
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT data FROM negotiation_sessions "
                "WHERE created_at >= '1970-01-01'",
            )
            rows = await cursor.fetchall()
            results: list[dict] = []
            for (raw,) in rows:
                doc = json.loads(raw)
                if (
                    doc.get("scenario_id") == scenario_id
                    and doc.get("owner_email") == owner_email
                ):
                    results.append(doc)
            return results
        finally:
            await conn.close()

    async def delete_session(self, session_id: str) -> None:
        """Delete a single session by ``session_id``."""
        conn = await self._get_connection()
        try:
            await conn.execute(
                "DELETE FROM negotiation_sessions WHERE session_id = ?",
                (session_id,),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def list_sessions(self, since: datetime | None = None) -> list[dict]:
        """Return all session dicts, optionally filtered by created_at >= since."""
        conn = await self._get_connection()
        try:
            if since is not None:
                cursor = await conn.execute(
                    "SELECT data FROM negotiation_sessions WHERE created_at >= ?",
                    (since.isoformat(),),
                )
            else:
                cursor = await conn.execute(
                    "SELECT data FROM negotiation_sessions",
                )
            rows = await cursor.fetchall()
            return [json.loads(raw) for (raw,) in rows]
        finally:
            await conn.close()


_CREATE_SHARE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS shared_negotiations (
    share_slug TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_SHARE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_shared_session ON shared_negotiations(session_id)
"""


class SQLiteShareClient:
    """Implements the ``ShareStore`` protocol using aiosqlite.

    The constructor is synchronous. Table creation happens lazily on the
    first database operation via ``_ensure_share_table()``.
    """

    def __init__(self, db_path: str = "data/juntoai.db") -> None:
        self._db_path = db_path
        self._table_ready = False

    async def _get_connection(self) -> aiosqlite.Connection:
        """Open a connection and ensure the share table exists."""
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
            await conn.execute(_CREATE_SHARE_TABLE_SQL)
            await conn.execute(_CREATE_SHARE_INDEX_SQL)
            await conn.commit()
            self._table_ready = True

        return conn

    async def create_share(self, payload: SharePayload) -> None:
        """Serialize and insert a new share row."""
        conn = await self._get_connection()
        try:
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                "INSERT INTO shared_negotiations (share_slug, session_id, data, created_at) "
                "VALUES (?, ?, ?, ?)",
                (payload.share_slug, payload.session_id, payload.model_dump_json(), now),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def get_share(self, share_slug: str) -> SharePayload | None:
        """Read and deserialize a share by slug. Returns None if missing."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT data FROM shared_negotiations WHERE share_slug = ?",
                (share_slug,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return SharePayload.model_validate_json(row[0])
        finally:
            await conn.close()

    async def get_share_by_session(self, session_id: str) -> SharePayload | None:
        """Find a share by session_id. Returns None if missing."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT data FROM shared_negotiations WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return SharePayload.model_validate_json(row[0])
        finally:
            await conn.close()
