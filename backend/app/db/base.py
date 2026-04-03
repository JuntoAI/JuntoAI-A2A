"""Abstract session store protocol for database-agnostic session persistence."""

from typing import Protocol, runtime_checkable

from app.models.negotiation import NegotiationStateModel


@runtime_checkable
class SessionStore(Protocol):
    """Protocol defining the session persistence interface.

    Both ``FirestoreSessionClient`` (cloud) and ``SQLiteSessionClient`` (local)
    implement this protocol, allowing runtime selection via ``RUN_MODE``.
    """

    async def create_session(self, state: NegotiationStateModel) -> None: ...

    async def get_session(self, session_id: str) -> NegotiationStateModel: ...

    async def get_session_doc(self, session_id: str) -> dict: ...

    async def update_session(self, session_id: str, updates: dict) -> None: ...
