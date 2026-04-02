"""SSE streaming endpoint and session start for real-time negotiations."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

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
from app.orchestrator.graph import run_negotiation
from app.orchestrator.state import create_initial_state
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry
from app.utils.sse import format_sse_event

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /negotiation/start — create session, deduct token, return session_id
# ---------------------------------------------------------------------------

class StartNegotiationRequest(BaseModel):
    email: str = Field(..., min_length=1)
    scenario_id: str = Field(..., min_length=1)
    active_toggles: list[str] = Field(default_factory=list)


class StartNegotiationResponse(BaseModel):
    session_id: str
    tokens_remaining: int
    max_turns: int


@router.post("/negotiation/start", response_model=StartNegotiationResponse)
async def start_negotiation(
    body: StartNegotiationRequest,
    db: FirestoreSessionClient = Depends(get_firestore_client),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
):
    """Create a new negotiation session.

    Validates the scenario, builds initial state with toggle injection,
    persists to Firestore, and returns the session_id.
    """
    # 1. Validate scenario exists
    try:
        scenario = registry.get_scenario(body.scenario_id)
    except Exception:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Scenario '{body.scenario_id}' not found"},
        )

    # 2. Build hidden context from active toggles
    hidden_context: dict = {}
    for toggle in scenario.toggles:
        if toggle.id in body.active_toggles:
            hidden_context[toggle.target_agent_role] = toggle.hidden_context_payload

    # 3. Create session state
    session_id = uuid.uuid4().hex
    state = NegotiationStateModel(
        session_id=session_id,
        scenario_id=body.scenario_id,
        max_turns=scenario.negotiation_params.max_turns,
        agreement_threshold=scenario.negotiation_params.agreement_threshold,
        turn_order=[r for r in scenario.negotiation_params.turn_order],
        current_speaker=scenario.negotiation_params.turn_order[0],
        active_toggles=body.active_toggles,
        hidden_context=hidden_context,
    )

    # 4. Persist to Firestore (also stores owner_email for auth)
    doc_data = state.model_dump()
    doc_data["owner_email"] = body.email
    doc_ref = db._collection.document(session_id)
    await doc_ref.set(doc_data)

    # 5. Deduct token from waitlist document
    from google.cloud.firestore import AsyncClient
    waitlist_ref = db._db.collection("waitlist").document(body.email.lower().strip())
    waitlist_doc = await waitlist_ref.get()
    if waitlist_doc.exists:
        current_balance = waitlist_doc.to_dict().get("token_balance", 0)
        new_balance = max(0, current_balance - 1)
        await waitlist_ref.update({"token_balance": new_balance})
        tokens_remaining = new_balance
    else:
        tokens_remaining = 99

    return StartNegotiationResponse(
        session_id=session_id,
        tokens_remaining=tokens_remaining,
        max_turns=state.max_turns,
    )


def _snapshot_to_events(snapshot: dict, session_id: str):
    """Convert a LangGraph state snapshot into SSE events.

    Each snapshot is keyed by node name. We extract the latest history
    entry and convert it to thought + message events.
    """
    events = []
    for _node_name, state in snapshot.items():
        if not isinstance(state, dict) or "history" not in state:
            continue
        history = state.get("history", [])
        if not history:
            continue
        entry = history[-1]
        role = entry.get("role", "Unknown")
        agent_type = entry.get("agent_type", "negotiator")
        turn_number = state.get("turn_count", 0)
        content = entry.get("content", {})

        # Thought event (inner_thought for negotiators, reasoning for regulators,
        # observation for observers)
        thought_text = (
            content.get("inner_thought")
            or content.get("reasoning")
            or content.get("observation")
            or ""
        )
        if thought_text:
            events.append(AgentThoughtEvent(
                event_type="agent_thought",
                agent_name=role,
                inner_thought=thought_text,
                turn_number=turn_number,
            ))

        # Message event
        public_message = content.get("public_message", "")
        if public_message:
            msg = AgentMessageEvent(
                event_type="agent_message",
                agent_name=role,
                public_message=public_message,
                turn_number=turn_number,
            )
            if agent_type == "negotiator" and "proposed_price" in content:
                msg.proposed_price = content["proposed_price"]
            if agent_type == "regulator" and "status" in content:
                msg.status = content["status"]
            events.append(msg)

        # Check for terminal state
        deal_status = state.get("deal_status", "Negotiating")
        if deal_status in ("Agreed", "Blocked", "Failed"):
            events.append(NegotiationCompleteEvent(
                event_type="negotiation_complete",
                session_id=session_id,
                deal_status=deal_status,
                final_summary={
                    "final_price": state.get("current_offer", 0),
                    "turns_taken": state.get("turn_count", 0),
                    "warning_count": state.get("warning_count", 0),
                },
            ))

    return events


@router.get("/negotiation/stream/{session_id}")
async def stream_negotiation(
    session_id: str,
    email: str = Query(...),
    db: FirestoreSessionClient = Depends(get_firestore_client),
    tracker: SSEConnectionTracker = Depends(get_sse_tracker),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
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

    # 4. Load scenario config for the orchestrator
    try:
        scenario = registry.get_scenario(state.scenario_id)
        scenario_config = scenario.model_dump()
    except Exception:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Scenario '{state.scenario_id}' not found"},
        )

    # 5. Acquire connection slot
    acquired = await tracker.acquire(email)
    if not acquired:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Concurrent SSE connection limit reached (max 3)"
            },
        )

    # 6. Build initial orchestrator state
    initial_state = create_initial_state(
        session_id=session_id,
        scenario_config=scenario_config,
        active_toggles=state.active_toggles,
        hidden_context=state.hidden_context,
    )

    # 7. Build the async event stream generator
    async def event_stream():
        timeout = state.max_turns * 30
        try:
            async with asyncio.timeout(timeout):
                async for snapshot in run_negotiation(initial_state, scenario_config):
                    events = _snapshot_to_events(snapshot, session_id)
                    for event in events:
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
