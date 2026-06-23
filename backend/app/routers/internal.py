"""Internal API router — transcript export and scenario analysis.

Protected by bearer token (INTERNAL_API_KEY) in cloud mode.
No auth required in local mode.
"""

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.db import get_session_store
from app.db.base import SessionStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])

_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def verify_internal_access(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Verify internal API access.

    - Local mode: no auth required, always passes.
    - Cloud mode: requires a valid Bearer token matching INTERNAL_API_KEY.
      If INTERNAL_API_KEY is not configured, the endpoint is disabled (503).
    """
    if settings.RUN_MODE == "local":
        return

    # Cloud mode — enforce bearer token
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Internal API not configured (INTERNAL_API_KEY not set)",
        )

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
        )

    if not hmac.compare_digest(credentials.credentials, settings.INTERNAL_API_KEY):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )


# ---------------------------------------------------------------------------
# GET /internal/transcripts — bulk export with filters
# ---------------------------------------------------------------------------


@router.get("/transcripts", dependencies=[Depends(verify_internal_access)])
async def list_transcripts(
    scenario_id: str | None = Query(default=None, description="Filter by scenario ID"),
    deal_status: str | None = Query(default=None, description="Filter by deal_status (Agreed, Blocked, Failed)"),
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of sessions to return"),
    db: SessionStore = Depends(get_session_store),
):
    """Export full negotiation session documents with optional filters.

    Returns complete session data including history (inner thoughts + public
    messages), agent_calls, evaluation reports, toggle configurations, and
    outcome metadata. Designed for LLM-powered analysis.
    """
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=days)

    sessions = await db.list_sessions(since=cutoff)

    # Apply filters
    results: list[dict] = []
    for doc in sessions:
        if scenario_id and doc.get("scenario_id") != scenario_id:
            continue
        if deal_status and doc.get("deal_status") != deal_status:
            continue
        results.append(doc)
        if len(results) >= limit:
            break

    return {
        "count": len(results),
        "filters": {
            "scenario_id": scenario_id,
            "deal_status": deal_status,
            "days": days,
            "limit": limit,
        },
        "sessions": results,
    }


# ---------------------------------------------------------------------------
# GET /internal/transcripts/{session_id} — single full transcript
# ---------------------------------------------------------------------------


@router.get("/transcripts/{session_id}", dependencies=[Depends(verify_internal_access)])
async def get_transcript(
    session_id: str,
    db: SessionStore = Depends(get_session_store),
):
    """Export a single full negotiation session document by session_id.

    Returns the complete session state: history with inner thoughts,
    agent_calls, evaluation, participant_summaries, tipping_point,
    toggle config, model overrides — everything needed for analysis.
    """
    from app.exceptions import SessionNotFoundError

    try:
        doc = await db.get_session_doc(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return doc
