"""Abstract store protocols for database-agnostic persistence."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.models.negotiation import NegotiationStateModel
from app.models.share import SharePayload


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

    async def list_sessions_by_owner(
        self, owner_email: str, since: str
    ) -> list[dict]: ...

    async def list_sessions_by_scenario(
        self, scenario_id: str, owner_email: str
    ) -> list[dict]:
        """Return session dicts where scenario_id matches and owner_email matches."""
        ...

    async def delete_session(self, session_id: str) -> None:
        """Delete a single session by session_id."""
        ...

    async def list_sessions(self, since: datetime | None = None) -> list[dict]:
        """Return all session dicts, optionally filtered by created_at >= since."""
        ...


@runtime_checkable
class ShareStore(Protocol):
    """Protocol defining the share persistence interface.

    Both ``FirestoreShareClient`` (cloud) and ``SQLiteShareClient`` (local)
    implement this protocol, allowing runtime selection via ``RUN_MODE``.
    """

    async def create_share(self, payload: SharePayload) -> None: ...

    async def get_share(self, share_slug: str) -> SharePayload | None: ...

    async def get_share_by_session(self, session_id: str) -> SharePayload | None: ...
