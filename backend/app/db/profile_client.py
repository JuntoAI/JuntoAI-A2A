"""Profile and verification token persistence clients.

Provides ``ProfileClient`` (Firestore) and ``SQLiteProfileClient`` (SQLite)
implementations for profile CRUD and verification token management.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from app.exceptions import DatabaseConnectionError


class ProfileClient:
    """Firestore-backed profile and verification token persistence."""

    PROFILES_COLLECTION = "profiles"
    TOKENS_COLLECTION = "verification_tokens"

    def __init__(self, db) -> None:
        """Accept a shared ``firestore.AsyncClient`` instance."""
        self._db = db
        self._profiles = self._db.collection(self.PROFILES_COLLECTION)
        self._tokens = self._db.collection(self.TOKENS_COLLECTION)

    # ── Profile CRUD ──────────────────────────────────────────────

    async def get_or_create_profile(self, email: str) -> dict:
        """Return existing profile or create one with defaults."""
        doc_ref = self._profiles.document(email)
        doc = await doc_ref.get()
        if doc.exists:
            return doc.to_dict()

        defaults = {
            "display_name": "",
            "email_verified": False,
            "github_url": None,
            "linkedin_url": None,
            "profile_completed_at": None,
            "created_at": datetime.now(timezone.utc),
            "password_hash": None,
            "country": None,
            "google_oauth_id": None,
        }
        await doc_ref.set(defaults)
        return defaults

    async def get_profile(self, email: str) -> dict | None:
        """Read profile by email. Returns ``None`` if not found."""
        doc = await self._profiles.document(email).get()
        if not doc.exists:
            return None
        return doc.to_dict()

    async def update_profile(self, email: str, fields: dict) -> None:
        """Update specific fields on an existing profile."""
        doc_ref = self._profiles.document(email)
        await doc_ref.update(fields)

    async def update_password_hash(self, email: str, password_hash: str) -> None:
        """Set the ``password_hash`` field on a profile."""
        await self.update_profile(email, {"password_hash": password_hash})

    async def set_google_oauth_id(self, email: str, google_oauth_id: str) -> None:
        """Link a Google account to a profile."""
        await self.update_profile(email, {"google_oauth_id": google_oauth_id})

    async def clear_google_oauth_id(self, email: str) -> None:
        """Unlink a Google account from a profile."""
        await self.update_profile(email, {"google_oauth_id": None})

    async def get_profile_by_google_oauth_id(self, google_oauth_id: str) -> dict | None:
        """Look up a profile by its linked Google OAuth ID."""
        query = self._profiles.where("google_oauth_id", "==", google_oauth_id).limit(1)
        docs = query.stream()
        async for doc in docs:
            data = doc.to_dict()
            data["_email"] = doc.id
            return data
        return None

    # ── Verification Token CRUD ───────────────────────────────────

    async def create_verification_token(
        self, token: str, email: str, created_at, expires_at
    ) -> None:
        """Store a verification token document."""
        doc_ref = self._tokens.document(token)
        await doc_ref.set(
            {"email": email, "created_at": created_at, "expires_at": expires_at}
        )

    async def get_verification_token(self, token: str) -> dict | None:
        """Read a verification token. Returns ``None`` if not found."""
        doc = await self._tokens.document(token).get()
        if not doc.exists:
            return None
        return doc.to_dict()

    async def delete_verification_token(self, token: str) -> None:
        """Delete a verification token document."""
        await self._tokens.document(token).delete()


# ── SQLite implementation ─────────────────────────────────────────

import aiosqlite

_CREATE_PROFILES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS profiles (
    email TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    email_verified INTEGER NOT NULL DEFAULT 0,
    github_url TEXT,
    linkedin_url TEXT,
    profile_completed_at TEXT,
    created_at TEXT,
    password_hash TEXT,
    country TEXT,
    google_oauth_id TEXT
)
"""

_CREATE_VERIFICATION_TOKENS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS verification_tokens (
    token TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
)
"""


class SQLiteProfileClient:
    """SQLite-backed profile and verification token persistence (local mode)."""

    def __init__(self, db_path: str = "data/juntoai.db") -> None:
        self._db_path = db_path
        self._tables_ready = False

    async def _get_connection(self) -> aiosqlite.Connection:
        """Open a connection and ensure tables exist."""
        try:
            parent = os.path.dirname(self._db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            conn = await aiosqlite.connect(self._db_path)
        except Exception as e:
            raise DatabaseConnectionError(
                f"Failed to open SQLite database at {self._db_path}: {e}"
            ) from e

        if not self._tables_ready:
            await conn.execute(_CREATE_PROFILES_TABLE_SQL)
            await conn.execute(_CREATE_VERIFICATION_TOKENS_TABLE_SQL)
            await conn.commit()
            self._tables_ready = True

        return conn

    # ── helpers ────────────────────────────────────────────────────

    @staticmethod
    def _row_to_profile(row: tuple) -> dict:
        """Convert a SQLite row to a profile dict matching Firestore shape."""
        return {
            "display_name": row[1],
            "email_verified": bool(row[2]),
            "github_url": row[3],
            "linkedin_url": row[4],
            "profile_completed_at": row[5],
            "created_at": row[6],
            "password_hash": row[7],
            "country": row[8],
            "google_oauth_id": row[9],
        }

    # ── Profile CRUD ──────────────────────────────────────────────

    async def get_or_create_profile(self, email: str) -> dict:
        """Return existing profile or create one with defaults."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT * FROM profiles WHERE email = ?", (email,)
            )
            row = await cursor.fetchone()
            if row is not None:
                return self._row_to_profile(row)

            now = datetime.now(timezone.utc).isoformat()
            defaults = {
                "display_name": "",
                "email_verified": False,
                "github_url": None,
                "linkedin_url": None,
                "profile_completed_at": None,
                "created_at": now,
                "password_hash": None,
                "country": None,
                "google_oauth_id": None,
            }
            await conn.execute(
                "INSERT INTO profiles "
                "(email, display_name, email_verified, github_url, linkedin_url, "
                "profile_completed_at, created_at, password_hash, country, google_oauth_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    email,
                    defaults["display_name"],
                    int(defaults["email_verified"]),
                    defaults["github_url"],
                    defaults["linkedin_url"],
                    defaults["profile_completed_at"],
                    defaults["created_at"],
                    defaults["password_hash"],
                    defaults["country"],
                    defaults["google_oauth_id"],
                ),
            )
            await conn.commit()
            return defaults
        finally:
            await conn.close()

    async def get_profile(self, email: str) -> dict | None:
        """Read profile by email. Returns ``None`` if not found."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT * FROM profiles WHERE email = ?", (email,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_profile(row)
        finally:
            await conn.close()

    async def update_profile(self, email: str, fields: dict) -> None:
        """Update specific fields on an existing profile."""
        if not fields:
            return
        conn = await self._get_connection()
        try:
            # Map bool values to int for SQLite
            mapped = {}
            for k, v in fields.items():
                if isinstance(v, bool):
                    mapped[k] = int(v)
                elif isinstance(v, datetime):
                    mapped[k] = v.isoformat()
                else:
                    mapped[k] = v

            set_clause = ", ".join(f"{k} = ?" for k in mapped)
            values = list(mapped.values()) + [email]
            await conn.execute(
                f"UPDATE profiles SET {set_clause} WHERE email = ?", values
            )
            await conn.commit()
        finally:
            await conn.close()

    async def update_password_hash(self, email: str, password_hash: str) -> None:
        """Set the ``password_hash`` field on a profile."""
        await self.update_profile(email, {"password_hash": password_hash})

    async def set_google_oauth_id(self, email: str, google_oauth_id: str) -> None:
        """Link a Google account to a profile."""
        await self.update_profile(email, {"google_oauth_id": google_oauth_id})

    async def clear_google_oauth_id(self, email: str) -> None:
        """Unlink a Google account from a profile."""
        await self.update_profile(email, {"google_oauth_id": None})

    async def get_profile_by_google_oauth_id(self, google_oauth_id: str) -> dict | None:
        """Look up a profile by its linked Google OAuth ID."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT * FROM profiles WHERE google_oauth_id = ? LIMIT 1",
                (google_oauth_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            data = self._row_to_profile(row)
            data["_email"] = row[0]
            return data
        finally:
            await conn.close()

    # ── Verification Token CRUD ───────────────────────────────────

    async def create_verification_token(
        self, token: str, email: str, created_at, expires_at
    ) -> None:
        """Store a verification token."""
        conn = await self._get_connection()
        try:
            created_str = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
            expires_str = expires_at.isoformat() if isinstance(expires_at, datetime) else str(expires_at)
            await conn.execute(
                "INSERT INTO verification_tokens (token, email, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (token, email, created_str, expires_str),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def get_verification_token(self, token: str) -> dict | None:
        """Read a verification token. Returns ``None`` if not found."""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT token, email, created_at, expires_at FROM verification_tokens WHERE token = ?",
                (token,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return {"email": row[1], "created_at": row[2], "expires_at": row[3]}
        finally:
            await conn.close()

    async def delete_verification_token(self, token: str) -> None:
        """Delete a verification token."""
        conn = await self._get_connection()
        try:
            await conn.execute(
                "DELETE FROM verification_tokens WHERE token = ?", (token,)
            )
            await conn.commit()
        finally:
            await conn.close()
