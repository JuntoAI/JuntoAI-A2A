"""Async SQLite client for negotiation session persistence (local mode)."""

import json
import os
from datetime import datetime, timezone

import aiosqlite

from app.exceptions import DatabaseConnectionError, SessionNotFoundError
from app.models.negotiation import NegotiationStateModel

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
