"""Firestore database client dependency."""

from app.config import settings
from app.db.firestore_client import FirestoreSessionClient

_client: FirestoreSessionClient | None = None


def get_firestore_client() -> FirestoreSessionClient:
    """Return a module-level singleton FirestoreSessionClient."""
    global _client
    if _client is None:
        _client = FirestoreSessionClient(
            project=settings.GOOGLE_CLOUD_PROJECT or None
        )
    return _client
