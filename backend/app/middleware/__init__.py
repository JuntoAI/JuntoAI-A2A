"""SSE connection rate limiting middleware and event buffering."""

from app.middleware.event_buffer import SSEEventBuffer
from app.middleware.sse_limiter import SSEConnectionTracker

_tracker: SSEConnectionTracker | None = None
_event_buffer: SSEEventBuffer | None = None


def get_sse_tracker() -> SSEConnectionTracker:
    """Return a module-level singleton SSEConnectionTracker."""
    global _tracker
    if _tracker is None:
        _tracker = SSEConnectionTracker()
    return _tracker


def get_event_buffer() -> SSEEventBuffer:
    """Return a module-level singleton SSEEventBuffer."""
    global _event_buffer
    if _event_buffer is None:
        _event_buffer = SSEEventBuffer()
    return _event_buffer
