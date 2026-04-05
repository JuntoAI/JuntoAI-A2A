"""Database client factories — returns the appropriate backend based on RUN_MODE."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.db.base import SessionStore

_client: SessionStore | None = None
_firestore_db = None
_profile_client = None


def get_firestore_db():
    """Return a module-level singleton ``firestore.AsyncClient``.

    Only called in cloud mode. Lazily imports and creates the client
    so local mode never touches GCP libraries.
    """
    global _firestore_db
    if _firestore_db is None:
        from google.cloud import firestore

        _firestore_db = firestore.AsyncClient(
            project=settings.GOOGLE_CLOUD_PROJECT or None
        )
    return _firestore_db


def get_session_store() -> SessionStore:
    """Return a module-level singleton SessionStore implementation.

    - ``RUN_MODE=local``  → ``SQLiteSessionClient`` (no GCP imports)
    - ``RUN_MODE=cloud``  → ``FirestoreSessionClient``
    """
    global _client
    if _client is None:
        if settings.RUN_MODE == "local":
            from app.db.sqlite_client import SQLiteSessionClient

            _client = SQLiteSessionClient(db_path=settings.SQLITE_DB_PATH)
        else:
            from app.db.firestore_client import FirestoreSessionClient

            _client = FirestoreSessionClient(db=get_firestore_db())
    return _client


def get_profile_client():
    """Return a module-level singleton profile client.

    - ``RUN_MODE=local``  → ``SQLiteProfileClient``
    - ``RUN_MODE=cloud``  → ``ProfileClient`` (Firestore)
    """
    global _profile_client
    if _profile_client is None:
        if settings.RUN_MODE == "local":
            from app.db.profile_client import SQLiteProfileClient

            _profile_client = SQLiteProfileClient(db_path=settings.SQLITE_DB_PATH)
        else:
            from app.db.profile_client import ProfileClient

            _profile_client = ProfileClient(db=get_firestore_db())
    return _profile_client


# Backward-compat alias (deprecated) — keeps existing call sites working
# during the transition period.
def get_firestore_client() -> SessionStore:
    """Deprecated: use ``get_session_store()`` instead."""
    return get_session_store()
