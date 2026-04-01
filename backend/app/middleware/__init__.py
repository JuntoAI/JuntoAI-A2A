"""SSE connection rate limiting middleware."""

from app.middleware.sse_limiter import SSEConnectionTracker

_tracker: SSEConnectionTracker | None = None


def get_sse_tracker() -> SSEConnectionTracker:
    """Return a module-level singleton SSEConnectionTracker."""
    global _tracker
    if _tracker is None:
        _tracker = SSEConnectionTracker()
    return _tracker
