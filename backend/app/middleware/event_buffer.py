"""In-memory SSE event buffer for reconnection replay.

Stores emitted events per session so that a reconnecting client
(sending Last-Event-ID) can receive missed events without re-running
the LangGraph orchestrator.

Events are pruned when the session reaches a terminal state.
"""

import asyncio
from dataclasses import dataclass, field


@dataclass
class _SessionBuffer:
    events: list[str] = field(default_factory=list)
    is_terminal: bool = False


class SSEEventBuffer:
    """Thread-safe per-session event buffer with auto-cleanup."""

    # Max events per session to prevent unbounded memory growth
    MAX_EVENTS_PER_SESSION = 500
    # How long to keep terminal session buffers before cleanup (seconds)
    TERMINAL_TTL = 120

    def __init__(self) -> None:
        self._buffers: dict[str, _SessionBuffer] = {}
        self._lock = asyncio.Lock()

    async def append(self, session_id: str, event_data: str, is_terminal: bool = False) -> int:
        """Append an event and return its 1-based event ID."""
        async with self._lock:
            buf = self._buffers.setdefault(session_id, _SessionBuffer())
            if len(buf.events) < self.MAX_EVENTS_PER_SESSION:
                buf.events.append(event_data)
            event_id = len(buf.events)
            if is_terminal:
                buf.is_terminal = True
                # Schedule cleanup after TTL
                asyncio.get_event_loop().call_later(
                    self.TERMINAL_TTL, lambda sid=session_id: asyncio.ensure_future(self._cleanup(sid))
                )
            return event_id

    async def replay_after(self, session_id: str, last_event_id: int) -> list[tuple[int, str]]:
        """Return events after the given ID as (event_id, event_data) tuples."""
        async with self._lock:
            buf = self._buffers.get(session_id)
            if not buf:
                return []
            # last_event_id is 1-based, so slice from that index
            return [
                (i + 1, evt)
                for i, evt in enumerate(buf.events)
                if i + 1 > last_event_id
            ]

    async def is_session_terminal(self, session_id: str) -> bool:
        """Check if the session has reached a terminal state."""
        async with self._lock:
            buf = self._buffers.get(session_id)
            return buf.is_terminal if buf else False

    async def _cleanup(self, session_id: str) -> None:
        async with self._lock:
            self._buffers.pop(session_id, None)
