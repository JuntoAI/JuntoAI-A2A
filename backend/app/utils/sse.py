"""SSE event formatting utility."""

from pydantic import BaseModel


def format_sse_event(event: BaseModel, event_id: int | None = None) -> str:
    """Convert a Pydantic event model to SSE wire format.

    Returns a string conforming to the W3C Server-Sent Events spec:
    ``id: <id>\ndata: <JSON>\n\n``

    When event_id is provided, the ``id:`` field is included so the
    browser sends ``Last-Event-ID`` on reconnect.
    """
    parts = []
    if event_id is not None:
        parts.append(f"id: {event_id}")
    parts.append(f"data: {event.model_dump_json()}")
    return "\n".join(parts) + "\n\n"
