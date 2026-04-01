"""SSE event formatting utility."""

from pydantic import BaseModel


def format_sse_event(event: BaseModel) -> str:
    """Convert a Pydantic event model to SSE wire format.

    Returns a string conforming to the W3C Server-Sent Events spec:
    ``data: <JSON>\n\n``
    """
    return f"data: {event.model_dump_json()}\n\n"
