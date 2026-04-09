"""Async Firestore clients for negotiation session and share persistence."""

from app.exceptions import SessionNotFoundError
from app.models.negotiation import NegotiationStateModel
from app.models.share import SharePayload


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

    async def list_sessions_by_owner(
        self, owner_email: str, since: str
    ) -> list[dict]:
        """Return session dicts for *owner_email* created at or after *since* (ISO timestamp)."""
        query = (
            self._collection
            .where("owner_email", "==", owner_email)
            .where("created_at", ">=", since)
            .order_by("created_at", direction="DESCENDING")
        )
        docs: list[dict] = []
        async for doc in query.stream():
            docs.append(doc.to_dict())
        return docs

    async def list_sessions_by_scenario(
        self, scenario_id: str, owner_email: str
    ) -> list[dict]:
        """Return session dicts where scenario_id and owner_email both match."""
        query = (
            self._collection
            .where("scenario_id", "==", scenario_id)
            .where("owner_email", "==", owner_email)
        )
        docs: list[dict] = []
        async for doc in query.stream():
            docs.append(doc.to_dict())
        return docs

    async def delete_session(self, session_id: str) -> None:
        """Delete a single session document by session_id."""
        await self._collection.document(session_id).delete()


class FirestoreShareClient:
    """Wraps a shared Firestore AsyncClient for share CRUD operations."""

    COLLECTION = "shared_negotiations"

    def __init__(self, db=None, project: str | None = None) -> None:
        if db is not None:
            self._db = db
        else:
            from google.cloud import firestore

            self._db = firestore.AsyncClient(project=project)
        self._collection = self._db.collection(self.COLLECTION)

    async def create_share(self, payload: SharePayload) -> None:
        """Write a new share document keyed by share_slug."""
        doc_ref = self._collection.document(payload.share_slug)
        await doc_ref.set(payload.model_dump())

    async def get_share(self, share_slug: str) -> SharePayload | None:
        """Read a share document by slug. Returns None if missing."""
        doc = await self._collection.document(share_slug).get()
        if not doc.exists:
            return None
        return SharePayload(**doc.to_dict())

    async def get_share_by_session(self, session_id: str) -> SharePayload | None:
        """Find a share document by session_id. Returns None if missing."""
        query = self._collection.where("session_id", "==", session_id).limit(1)
        async for doc in query.stream():
            return SharePayload(**doc.to_dict())
        return None
