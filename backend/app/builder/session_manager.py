"""In-memory builder session management with TTL-based cleanup."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BuilderSession:
    """Ephemeral builder chat session stored in memory."""

    session_id: str
    email: str
    conversation_history: list[dict] = field(default_factory=list)
    partial_scenario: dict = field(default_factory=dict)
    message_count: int = 0  # Tracks user messages only
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BuilderSessionManager:
    """In-memory session store with TTL cleanup for builder chat sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, BuilderSession] = {}

    def create_session(self, email: str) -> BuilderSession:
        """Create a new builder session with a UUID session_id."""
        session = BuilderSession(
            session_id=str(uuid.uuid4()),
            email=email,
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> BuilderSession | None:
        """Return the session or None if not found."""
        return self._sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session's conversation history.

        Raises ValueError if the session has reached the 50 user-message limit
        and the role is "user". Assistant messages are never limited.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")

        if role == "user" and session.message_count >= 50:
            raise ValueError(
                "Session message limit reached (50). "
                "Please save or start a new session."
            )

        session.conversation_history.append({"role": role, "content": content})

        if role == "user":
            session.message_count += 1

        session.last_activity = datetime.now(timezone.utc)

    def update_scenario(self, session_id: str, section: str, data: dict) -> None:
        """Merge *section* data into the session's partial_scenario."""
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")

        session.partial_scenario[section] = data
        session.last_activity = datetime.now(timezone.utc)

    def delete_session(self, session_id: str) -> None:
        """Remove a session. No-op if the session doesn't exist."""
        self._sessions.pop(session_id, None)

    def cleanup_stale(self, max_age_minutes: int = 60) -> int:
        """Remove sessions whose last_activity exceeds *max_age_minutes*.

        Returns the number of sessions removed.
        """
        now = datetime.now(timezone.utc)
        stale_ids = [
            sid
            for sid, s in self._sessions.items()
            if (now - s.last_activity).total_seconds() > max_age_minutes * 60
        ]
        for sid in stale_ids:
            del self._sessions[sid]
        return len(stale_ids)
