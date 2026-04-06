"""Admin dashboard router — cloud-only.

Provides authentication, rate limiting, tier computation,
and admin endpoints (login, logout, overview, plus future CRUD).
"""

import csv
import hmac
import io
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.responses import StreamingResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings
from app.models.admin import (
    AdminLoginRequest,
    ModelPerformance,
    OverviewResponse,
    RecentSimulation,
    ScenarioAnalytics,
    SimulationListItem,
    SimulationListResponse,
    StatusChangeRequest,
    TokenAdjustRequest,
    UserListItem,
    UserListResponse,
    UserStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def require_cloud_mode() -> None:
    """Raise 503 when running in local mode."""
    if settings.RUN_MODE == "local":
        raise HTTPException(
            status_code=503,
            detail="Admin dashboard is not available in local mode",
        )


def verify_admin_session(request: Request) -> str:
    """Validate the admin_session cookie.

    Calls the cloud-mode guard first, then deserialises the signed cookie
    using ``itsdangerous.URLSafeTimedSerializer`` with an 8-hour max age.
    """
    require_cloud_mode()

    cookie = request.cookies.get("admin_session")
    if not cookie:
        raise HTTPException(status_code=401, detail="Unauthorized")

    serializer = URLSafeTimedSerializer(settings.ADMIN_PASSWORD)
    try:
        data = serializer.loads(cookie, max_age=28800)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return data


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class LoginRateLimiter:
    """In-memory per-IP rate limiter with TTL cleanup."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}

    def is_rate_limited(self, ip: str) -> bool:
        """Return ``True`` if *ip* has exceeded the attempt threshold."""
        now = time.time()
        cutoff = now - self.window_seconds
        attempts = [t for t in self._attempts.get(ip, []) if t > cutoff]
        self._attempts[ip] = attempts
        return len(attempts) >= self.max_attempts

    def record_attempt(self, ip: str) -> None:
        """Record a login attempt from *ip*, pruning stale entries."""
        now = time.time()
        cutoff = now - self.window_seconds
        attempts = [t for t in self._attempts.get(ip, []) if t > cutoff]
        attempts.append(now)
        self._attempts[ip] = attempts


rate_limiter = LoginRateLimiter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_tier(profile: dict | None) -> int:
    """Determine token tier from a profile document.

    Reuses Spec 140 Req 7 logic:
    - Tier 3 (100 tokens/day) if ``profile_completed_at`` is set
    - Tier 2 (50 tokens/day)  if ``email_verified`` is truthy
    - Tier 1 (20 tokens/day)  otherwise
    """
    if profile and profile.get("profile_completed_at"):
        return 3
    if profile and profile.get("email_verified"):
        return 2
    return 1


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", dependencies=[Depends(require_cloud_mode)])
async def admin_login(body: AdminLoginRequest, request: Request) -> JSONResponse:
    """Authenticate with the admin password and set a signed session cookie."""
    ip = request.client.host if request.client else "unknown"

    if rate_limiter.is_rate_limited(ip):
        logger.info(
            "admin action=login_rate_limited ip=%s ts=%s",
            ip,
            datetime.now(timezone.utc).isoformat(),
        )
        raise HTTPException(status_code=429, detail="Too many login attempts")

    rate_limiter.record_attempt(ip)

    if not hmac.compare_digest(body.password, settings.ADMIN_PASSWORD):
        logger.info(
            "admin action=login_failed ip=%s ts=%s",
            ip,
            datetime.now(timezone.utc).isoformat(),
        )
        raise HTTPException(status_code=401, detail="Invalid password")

    serializer = URLSafeTimedSerializer(settings.ADMIN_PASSWORD)
    signed_token = serializer.dumps("admin")

    response = JSONResponse(content={"detail": "Logged in"})
    response.set_cookie(
        key="admin_session",
        value=signed_token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="strict",
        path="/",
        max_age=28800,
    )

    logger.info(
        "admin action=login_success ip=%s ts=%s",
        ip,
        datetime.now(timezone.utc).isoformat(),
    )
    return response


@router.post("/logout", dependencies=[Depends(verify_admin_session)])
async def admin_logout(request: Request) -> JSONResponse:
    """Clear the admin session cookie."""
    ip = request.client.host if request.client else "unknown"

    response = JSONResponse(content={"detail": "Logged out"})
    response.delete_cookie(key="admin_session", path="/")

    logger.info(
        "admin action=logout ip=%s ts=%s",
        ip,
        datetime.now(timezone.utc).isoformat(),
    )
    return response


# ---------------------------------------------------------------------------
# Overview endpoint
# ---------------------------------------------------------------------------


def _compute_scenario_analytics(sessions: list[dict]) -> list[ScenarioAnalytics]:
    """Aggregate run_count and avg_tokens_used per scenario_id."""
    buckets: dict[str, list[int]] = defaultdict(list)
    for s in sessions:
        sid = s.get("scenario_id", "unknown")
        tokens = s.get("total_tokens_used", 0) or 0
        buckets[sid].append(tokens)
    return [
        ScenarioAnalytics(
            scenario_id=sid,
            run_count=len(token_list),
            avg_tokens_used=sum(token_list) / len(token_list),
        )
        for sid, token_list in sorted(buckets.items())
    ]


def _compute_model_performance(sessions: list[dict]) -> list[ModelPerformance]:
    """Aggregate per-model metrics from agent_calls across all sessions.

    Sessions without ``agent_calls`` are silently skipped.
    """
    model_data: dict[str, dict] = defaultdict(
        lambda: {
            "latencies": [],
            "input_tokens": [],
            "output_tokens": [],
            "error_count": 0,
        }
    )
    for s in sessions:
        calls = s.get("agent_calls")
        if not calls:
            continue
        for call in calls:
            mid = call.get("model_id", "unknown")
            bucket = model_data[mid]
            bucket["latencies"].append(call.get("latency_ms", 0) or 0)
            bucket["input_tokens"].append(call.get("input_tokens", 0) or 0)
            bucket["output_tokens"].append(call.get("output_tokens", 0) or 0)
            if call.get("error"):
                bucket["error_count"] += 1

    results: list[ModelPerformance] = []
    for mid, data in sorted(model_data.items()):
        n = len(data["latencies"])
        if n == 0:
            continue
        results.append(
            ModelPerformance(
                model_id=mid,
                avg_latency_ms=sum(data["latencies"]) / n,
                avg_input_tokens=sum(data["input_tokens"]) / n,
                avg_output_tokens=sum(data["output_tokens"]) / n,
                error_count=data["error_count"],
                total_calls=n,
            )
        )
    return results


@router.get(
    "/overview",
    response_model=OverviewResponse,
    dependencies=[Depends(verify_admin_session)],
)
async def admin_overview() -> OverviewResponse:
    """Return all dashboard overview metrics in a single response.

    Queries Firestore for user count, today's simulations, scenario
    analytics, model performance, and the recent simulations feed.
    Reads the SSE tracker for active connection count.
    """
    from app.db import get_firestore_db
    from app.middleware import get_sse_tracker

    db = get_firestore_db()
    tracker = get_sse_tracker()

    # 1. Total registered users (waitlist collection)
    waitlist_docs = db.collection("waitlist").stream()
    total_users = 0
    async for _ in waitlist_docs:
        total_users += 1

    # 2. All sessions (needed for scenario analytics + model performance)
    all_sessions: list[dict] = []
    sessions_stream = db.collection("negotiation_sessions").stream()
    async for doc in sessions_stream:
        all_sessions.append(doc.to_dict())

    # 3. Today's simulations and AI tokens today
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    simulations_today = 0
    ai_tokens_today = 0
    for s in all_sessions:
        created_at = s.get("created_at", "")
        if isinstance(created_at, str) and created_at.startswith(today_str):
            simulations_today += 1
            ai_tokens_today += s.get("total_tokens_used", 0) or 0

    # 4. Active SSE connections
    active_sse_connections = tracker.total_active_connections

    # 5. Scenario analytics (all sessions)
    scenario_analytics = _compute_scenario_analytics(all_sessions)

    # 6. Model performance (all sessions with agent_calls)
    model_performance = _compute_model_performance(all_sessions)

    # 7. Recent simulations feed (last 50 by created_at desc)
    #    Firestore order_by requires an index; fall back to in-memory sort
    #    since we already have all sessions loaded.
    sorted_sessions = sorted(
        all_sessions,
        key=lambda s: s.get("created_at", "") or "",
        reverse=True,
    )[:50]

    recent_simulations = [
        RecentSimulation(
            session_id=s.get("session_id", ""),
            scenario_id=s.get("scenario_id", ""),
            deal_status=s.get("deal_status", ""),
            turn_count=s.get("turn_count", 0) or 0,
            total_tokens_used=s.get("total_tokens_used", 0) or 0,
            owner_email=s.get("owner_email"),
            created_at=s.get("created_at"),
        )
        for s in sorted_sessions
    ]

    return OverviewResponse(
        total_users=total_users,
        simulations_today=simulations_today,
        active_sse_connections=active_sse_connections,
        ai_tokens_today=ai_tokens_today,
        scenario_analytics=scenario_analytics,
        model_performance=model_performance,
        recent_simulations=recent_simulations,
    )


# ---------------------------------------------------------------------------
# User list endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/users",
    response_model=UserListResponse,
    dependencies=[Depends(verify_admin_session)],
)
async def admin_list_users(
    cursor: str | None = None,
    page_size: int = 50,
    tier: int | None = None,
    status: UserStatus | None = None,
) -> UserListResponse:
    """Return a paginated, filterable list of users.

    Joins ``waitlist`` with ``profiles`` to compute each user's tier.
    Tier filtering is done in application code because tier is derived
    from the profiles collection, not stored on waitlist documents.

    Cursor-based pagination uses ``signed_up_at`` (descending).
    """
    from app.db import get_firestore_db

    # Clamp page_size to [1, 200]
    page_size = max(1, min(page_size, 200))

    db = get_firestore_db()

    # Step 1: Build email → tier map from profiles collection
    email_tier_map: dict[str, int] = {}
    profiles_stream = db.collection("profiles").stream()
    async for doc in profiles_stream:
        profile = doc.to_dict()
        email_tier_map[doc.id] = compute_tier(profile)

    # Step 2: Query waitlist with cursor-based pagination.
    # Because tier filtering happens in application code, we may need
    # to fetch more docs than page_size to fill a page. We use an
    # over-fetch strategy: keep pulling batches until we have enough
    # results or exhaust the collection.
    collected: list[UserListItem] = []
    batch_size = page_size * 3  # over-fetch to account for tier filtering
    last_signed_up_at: str | None = None
    exhausted = False
    current_cursor = cursor

    while len(collected) < page_size and not exhausted:
        query = db.collection("waitlist").order_by(
            "signed_up_at", direction="DESCENDING"
        )

        if current_cursor:
            query = query.start_after({"signed_up_at": current_cursor})

        query = query.limit(batch_size)

        batch_docs: list[dict] = []
        batch_ids: list[str] = []
        async for doc in query.stream():
            batch_docs.append(doc.to_dict())
            batch_ids.append(doc.id)

        if not batch_docs:
            exhausted = True
            break

        for i, wl_data in enumerate(batch_docs):
            email = wl_data.get("email", batch_ids[i])
            user_tier = email_tier_map.get(email, compute_tier(None))
            user_status = wl_data.get("user_status", "active")
            signed_up_at = wl_data.get("signed_up_at")

            # Apply tier filter
            if tier is not None and user_tier != tier:
                continue

            # Apply status filter
            if status is not None and user_status != status.value:
                continue

            collected.append(
                UserListItem(
                    email=email,
                    signed_up_at=signed_up_at,
                    token_balance=wl_data.get("token_balance", 0) or 0,
                    last_reset_date=wl_data.get("last_reset_date"),
                    tier=user_tier,
                    user_status=user_status,
                )
            )

            if len(collected) >= page_size:
                break

        # Update cursor for next batch
        last_doc = batch_docs[-1]
        last_signed_up_at = last_doc.get("signed_up_at")
        current_cursor = last_signed_up_at

        if len(batch_docs) < batch_size:
            exhausted = True

    # Trim to page_size (safety)
    result_users = collected[:page_size]

    # Compute next_cursor from the last item returned
    next_cursor: str | None = None
    if result_users and not exhausted:
        next_cursor = result_users[-1].signed_up_at

    return UserListResponse(users=result_users, next_cursor=next_cursor)


# ---------------------------------------------------------------------------
# Token adjustment endpoint
# ---------------------------------------------------------------------------


@router.patch(
    "/users/{email}/tokens",
    dependencies=[Depends(verify_admin_session)],
)
async def admin_adjust_tokens(
    email: str,
    body: TokenAdjustRequest,
    request: Request,
) -> JSONResponse:
    """Adjust a user's token balance in the waitlist collection."""
    from app.db import get_firestore_db

    ip = request.client.host if request.client else "unknown"
    normalised_email = email.lower().strip()

    db = get_firestore_db()
    doc_ref = db.collection("waitlist").document(normalised_email)
    doc = await doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    await doc_ref.update({"token_balance": body.token_balance})

    logger.info(
        "admin action=token_adjust ip=%s target=%s new_balance=%d ts=%s",
        ip,
        normalised_email,
        body.token_balance,
        datetime.now(timezone.utc).isoformat(),
    )

    return JSONResponse(content={"detail": "Token balance updated"})


# ---------------------------------------------------------------------------
# Status change endpoint
# ---------------------------------------------------------------------------


@router.patch(
    "/users/{email}/status",
    dependencies=[Depends(verify_admin_session)],
)
async def admin_change_status(
    email: str,
    body: StatusChangeRequest,
    request: Request,
) -> JSONResponse:
    """Change a user's status in the waitlist collection."""
    from app.db import get_firestore_db

    ip = request.client.host if request.client else "unknown"
    normalised_email = email.lower().strip()

    db = get_firestore_db()
    doc_ref = db.collection("waitlist").document(normalised_email)
    doc = await doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    await doc_ref.update({"user_status": body.user_status.value})

    logger.info(
        "admin action=status_change ip=%s target=%s new_status=%s ts=%s",
        ip,
        normalised_email,
        body.user_status.value,
        datetime.now(timezone.utc).isoformat(),
    )

    return JSONResponse(content={"detail": "User status updated"})


# ---------------------------------------------------------------------------
# Simulation list endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/simulations",
    response_model=SimulationListResponse,
    dependencies=[Depends(verify_admin_session)],
)
async def admin_list_simulations(
    cursor: str | None = None,
    page_size: int = 50,
    scenario_id: str | None = None,
    deal_status: str | None = None,
    owner_email: str | None = None,
    order: str = "desc",
) -> SimulationListResponse:
    """Return a paginated, filterable list of simulations.

    Cursor-based pagination uses ``created_at``. Filtering by
    ``scenario_id``, ``deal_status``, and ``owner_email`` is applied
    in application code to avoid requiring Firestore compound indexes.
    """
    from app.db import get_firestore_db

    # Clamp page_size to [1, 200]
    page_size = max(1, min(page_size, 200))

    # Normalise order
    direction = "ASCENDING" if order == "asc" else "DESCENDING"

    db = get_firestore_db()

    collected: list[SimulationListItem] = []
    batch_size = page_size * 3  # over-fetch to account for filtering
    exhausted = False
    current_cursor = cursor

    while len(collected) < page_size and not exhausted:
        query = db.collection("negotiation_sessions").order_by(
            "created_at", direction=direction
        )

        if current_cursor:
            query = query.start_after({"created_at": current_cursor})

        query = query.limit(batch_size)

        batch_docs: list[dict] = []
        async for doc in query.stream():
            batch_docs.append(doc.to_dict())

        if not batch_docs:
            exhausted = True
            break

        for s in batch_docs:
            # Apply filters in application code
            if scenario_id is not None and s.get("scenario_id") != scenario_id:
                continue
            if deal_status is not None and s.get("deal_status") != deal_status:
                continue
            if owner_email is not None and s.get("owner_email") != owner_email:
                continue

            collected.append(
                SimulationListItem(
                    session_id=s.get("session_id", ""),
                    scenario_id=s.get("scenario_id", ""),
                    owner_email=s.get("owner_email"),
                    deal_status=s.get("deal_status", ""),
                    turn_count=s.get("turn_count", 0) or 0,
                    max_turns=s.get("max_turns", 15) or 15,
                    total_tokens_used=s.get("total_tokens_used", 0) or 0,
                    active_toggles=s.get("active_toggles") or [],
                    model_overrides=s.get("model_overrides") or {},
                    created_at=s.get("created_at"),
                )
            )

            if len(collected) >= page_size:
                break

        # Update cursor for next batch
        last_doc = batch_docs[-1]
        current_cursor = last_doc.get("created_at")

        if len(batch_docs) < batch_size:
            exhausted = True

    # Trim to page_size (safety)
    result_simulations = collected[:page_size]

    # Compute next_cursor from the last item returned
    next_cursor: str | None = None
    if result_simulations and not exhausted:
        next_cursor = result_simulations[-1].created_at

    return SimulationListResponse(
        simulations=result_simulations, next_cursor=next_cursor
    )


# ---------------------------------------------------------------------------
# Transcript helper
# ---------------------------------------------------------------------------


def format_transcript(session: dict) -> str:
    """Convert a session document into a deterministic plain-text transcript.

    The output format is parseable:
    - Turn headers: ``--- Turn (\\d+) ---``
    - Role headers: ``\\[(.+)\\]``
    - Field lines:  ``(Thought|Message|Status|Price): (.+)``

    Extracted as a standalone function for testability (Property 7).
    """
    lines: list[str] = [
        "=== Negotiation Transcript ===",
        f"Session: {session.get('session_id', '')}",
        f"Scenario: {session.get('scenario_id', '')}",
        f"Date: {session.get('created_at', '')}",
        f"Status: {session.get('deal_status', '')}",
        "=====================================",
        "",
    ]

    history = session.get("history") or []
    current_turn: int | None = None

    for entry in history:
        turn_number = entry.get("turn_number", 0)
        role = entry.get("role", "Unknown")
        agent_type = entry.get("agent_type", "")
        content = entry.get("content") or {}

        # Emit turn header when the turn number changes
        if turn_number != current_turn:
            if current_turn is not None:
                lines.append("")  # blank line between turns
            lines.append(f"--- Turn {turn_number} ---")
            current_turn = turn_number

        # Role header
        lines.append(f"[{role}]")

        # Thought field — key depends on agent_type
        if agent_type == "negotiator":
            thought = content.get("inner_thought", "")
        elif agent_type == "regulator":
            thought = content.get("reasoning", "")
        elif agent_type == "observer":
            thought = content.get("observation", "")
        else:
            thought = (
                content.get("inner_thought")
                or content.get("reasoning")
                or content.get("observation")
                or ""
            )
        if thought:
            lines.append(f"Thought: {thought}")

        # Public message
        public_message = content.get("public_message", "")
        if public_message:
            lines.append(f"Message: {public_message}")

        # Status (regulators)
        status = content.get("status", "")
        if status:
            lines.append(f"Status: {status}")

        # Proposed price (negotiators)
        proposed_price = content.get("proposed_price")
        if proposed_price is not None and proposed_price != 0:
            lines.append(f"Price: {proposed_price}")

        lines.append("")  # blank line after each agent block

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Transcript download endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/simulations/{session_id}/transcript",
    dependencies=[Depends(verify_admin_session)],
)
async def admin_download_transcript(session_id: str) -> PlainTextResponse:
    """Download a human-readable transcript for a negotiation session."""
    from app.db import get_firestore_db

    db = get_firestore_db()
    doc_ref = db.collection("negotiation_sessions").document(session_id)
    doc = await doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = doc.to_dict()
    session_data.setdefault("session_id", session_id)

    transcript_text = format_transcript(session_data)

    return PlainTextResponse(
        content=transcript_text,
        headers={
            "Content-Disposition": f'attachment; filename="transcript_{session_id}.txt"',
        },
    )


# ---------------------------------------------------------------------------
# JSON download endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/simulations/{session_id}/json",
    dependencies=[Depends(verify_admin_session)],
)
async def admin_download_json(session_id: str) -> JSONResponse:
    """Download the raw session document as a JSON file."""
    from app.db import get_firestore_db

    db = get_firestore_db()
    doc_ref = db.collection("negotiation_sessions").document(session_id)
    doc = await doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = doc.to_dict()
    session_data.setdefault("session_id", session_id)

    return JSONResponse(
        content=session_data,
        headers={
            "Content-Disposition": f'attachment; filename="session_{session_id}.json"',
        },
    )


# ---------------------------------------------------------------------------
# CSV export endpoints
# ---------------------------------------------------------------------------

USER_CSV_COLUMNS = [
    "email",
    "signed_up_at",
    "token_balance",
    "last_reset_date",
    "tier",
    "email_verified",
    "display_name",
    "status",
]

SIMULATION_CSV_COLUMNS = [
    "session_id",
    "scenario_id",
    "owner_email",
    "deal_status",
    "turn_count",
    "max_turns",
    "total_tokens_used",
    "active_toggles",
    "model_overrides",
    "created_at",
]


@router.get(
    "/export/users",
    dependencies=[Depends(verify_admin_session)],
)
async def admin_export_users(
    tier: int | None = None,
    status: UserStatus | None = None,
) -> StreamingResponse:
    """Export all users as a CSV file download.

    Joins ``waitlist`` with ``profiles`` to compute tier, email_verified,
    and display_name. Supports the same filter params as the user list.
    """
    from app.db import get_firestore_db

    db = get_firestore_db()

    # Build email → profile map
    email_profiles: dict[str, dict] = {}
    profiles_stream = db.collection("profiles").stream()
    async for doc in profiles_stream:
        email_profiles[doc.id] = doc.to_dict()

    # Stream all waitlist docs
    waitlist_stream = db.collection("waitlist").stream()
    rows: list[dict] = []
    async for doc in waitlist_stream:
        wl = doc.to_dict()
        email = wl.get("email", doc.id)
        profile = email_profiles.get(email)
        user_tier = compute_tier(profile)
        user_status = wl.get("user_status", "active")

        # Apply filters
        if tier is not None and user_tier != tier:
            continue
        if status is not None and user_status != status.value:
            continue

        rows.append({
            "email": email,
            "signed_up_at": wl.get("signed_up_at", ""),
            "token_balance": wl.get("token_balance", 0) or 0,
            "last_reset_date": wl.get("last_reset_date", ""),
            "tier": user_tier,
            "email_verified": profile.get("email_verified", False) if profile else False,
            "display_name": profile.get("display_name", "") if profile else "",
            "status": user_status,
        })

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=USER_CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="users_export_{today}.csv"',
        },
    )


@router.get(
    "/export/simulations",
    dependencies=[Depends(verify_admin_session)],
)
async def admin_export_simulations(
    scenario_id: str | None = None,
    deal_status: str | None = None,
    owner_email: str | None = None,
) -> StreamingResponse:
    """Export all simulations as a CSV file download.

    Supports the same filter params as the simulation list endpoint.
    ``active_toggles`` (list) and ``model_overrides`` (dict) are
    serialized to JSON strings for CSV compatibility.
    """
    from app.db import get_firestore_db

    db = get_firestore_db()

    sessions_stream = db.collection("negotiation_sessions").stream()
    rows: list[dict] = []
    async for doc in sessions_stream:
        s = doc.to_dict()

        # Apply filters
        if scenario_id is not None and s.get("scenario_id") != scenario_id:
            continue
        if deal_status is not None and s.get("deal_status") != deal_status:
            continue
        if owner_email is not None and s.get("owner_email") != owner_email:
            continue

        rows.append({
            "session_id": s.get("session_id", ""),
            "scenario_id": s.get("scenario_id", ""),
            "owner_email": s.get("owner_email", ""),
            "deal_status": s.get("deal_status", ""),
            "turn_count": s.get("turn_count", 0) or 0,
            "max_turns": s.get("max_turns", 15) or 15,
            "total_tokens_used": s.get("total_tokens_used", 0) or 0,
            "active_toggles": json.dumps(s.get("active_toggles") or []),
            "model_overrides": json.dumps(s.get("model_overrides") or {}),
            "created_at": s.get("created_at", ""),
        })

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SIMULATION_CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="simulations_export_{today}.csv"',
        },
    )
