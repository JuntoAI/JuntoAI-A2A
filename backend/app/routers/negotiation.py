"""SSE streaming endpoint for real-time negotiation events."""

import asyncio
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse

from app.db import get_firestore_client
from app.db.firestore_client import FirestoreSessionClient
from app.middleware import get_sse_tracker
from app.middleware.sse_limiter import SSEConnectionTracker
from app.models.events import (
    AgentMessageEvent,
    AgentThoughtEvent,
    NegotiationCompleteEvent,
    StreamErrorEvent,
)
from app.models.negotiation import NegotiationStateModel
from app.utils.sse import format_sse_event

logger = logging.getLogger(__name__)

router = APIRouter()


async def _placeholder_event_generator(state: NegotiationStateModel):
    """Temporary placeholder — replaced by orchestrator.run_negotiation() in spec 030."""
    yield AgentThoughtEvent(
        event_type="agent_thought",
        agent_name="Buyer",
        inner_thought="Analyzing the offer...",
        turn_number=0,
    )
    await asyncio.sleep(0.5)
    yield AgentMessageEvent(
        event_type="agent_message",
        agent_name="Buyer",
        public_message="I propose €35M.",
        turn_number=0,
        proposed_price=35000000.0,
    )
    yield NegotiationCompleteEvent(
        event_type="negotiation_complete",
        session_id=state.session_id,
        deal_status="Agreed",
        final_summary={"final_price": 35000000.0},
    )


@router.get("/negotiation/stream/{session_id}")
async def stream_negotiation(
    session_id: str,
    email: str = Query(...),
    db: FirestoreSessionClient = Depends(get_firestore_client),
    tracker: SSEConnectionTracker = Depends(get_sse_tracker),
):
    """Open an SSE stream for a negotiation session.

    Validates session existence, email ownership, and connection limits
    before returning a StreamingResponse of SSE-formatted events.
    """
    # 1. Session lookup — raises SessionNotFoundError → 404 via exception handler
    raw_doc = await db.get_session_doc(session_id)

    # 2. Email ownership check
    owner_email = raw_doc.get("owner_email")
    if owner_email is not None and owner_email != email:
        return JSONResponse(
            status_code=403,
            content={"detail": "Email does not match session owner"},
        )

    # 3. Build state model (extra="ignore" drops owner_email, created_at, etc.)
    state = NegotiationStateModel(**raw_doc)

    # 4. Acquire connection slot
    acquired = await tracker.acquire(email)
    if not acquired:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Concurrent SSE connection limit reached (max 3)"
            },
        )

    # 5. Build the async event stream generator
    async def event_stream():
        timeout = state.max_turns * 30
        try:
            async with asyncio.timeout(timeout):
                async for event in _placeholder_event_generator(state):
                    yield format_sse_event(event)
                    if isinstance(event, NegotiationCompleteEvent):
                        return
        except TimeoutError:
            yield format_sse_event(
                NegotiationCompleteEvent(
                    event_type="negotiation_complete",
                    session_id=session_id,
                    deal_status="Failed",
                    final_summary={"reason": "timeout"},
                )
            )
        except Exception as e:
            logger.exception("Stream error for session %s", session_id)
            yield format_sse_event(
                StreamErrorEvent(
                    event_type="error",
                    message="An unexpected error occurred",
                )
            )
        finally:
            await tracker.release(email)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
