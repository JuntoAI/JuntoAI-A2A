"""Session store factory — returns the appropriate backend based on RUN_MODE."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.db.base import SessionStore

_client: SessionStore | None = None


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

            _client = FirestoreSessionClient(
                project=settings.GOOGLE_CLOUD_PROJECT or None
            )
    return _client


# Backward-compat alias (deprecated) — keeps existing call sites working
# during the transition period.
def get_firestore_client() -> SessionStore:
    """Deprecated: use ``get_session_store()`` instead."""
    return get_session_store()
