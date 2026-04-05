"""Async Firestore client for negotiation session persistence."""

from app.exceptions import SessionNotFoundError
from app.models.negotiation import NegotiationStateModel


class FirestoreSessionClient:
    """Wraps a shared Firestore AsyncClient for session CRUD operations."""

    COLLECTION = "negotiation_sessions"

    def __init__(self, db=None, project: str | None = None) -> None:
        if db is not None:
            self._db = db
        else:
            # Legacy path: create own client (kept for backward compat)
            from google.cloud import firestore

            self._db = firestore.AsyncClient(project=project)
        self._collection = self._db.collection(self.COLLECTION)

    async def create_session(self, state: NegotiationStateModel) -> None:
        """Write a new session document keyed by session_id."""
        doc_ref = self._collection.document(state.session_id)
        await doc_ref.set(state.model_dump())

    async def get_session(self, session_id: str) -> NegotiationStateModel:
        """Read a session document. Raises SessionNotFoundError if missing."""
        doc = await self._collection.document(session_id).get()
        if not doc.exists:
            raise SessionNotFoundError(session_id)
        return NegotiationStateModel(**doc.to_dict())

    async def get_session_doc(self, session_id: str) -> dict:
        """Read a raw session document dict. Raises SessionNotFoundError if missing."""
        doc = await self._collection.document(session_id).get()
        if not doc.exists:
            raise SessionNotFoundError(session_id)
        return doc.to_dict()

    async def update_session(self, session_id: str, updates: dict) -> None:
        """Merge fields into an existing session. Raises SessionNotFoundError if missing."""
        doc_ref = self._collection.document(session_id)
        doc = await doc_ref.get()
        if not doc.exists:
            raise SessionNotFoundError(session_id)
        await doc_ref.update(updates)
