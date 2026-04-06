"""Builder API router — chat, save, list, delete custom scenarios.

# Feature: ai-scenario-builder
# Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 6.1, 6.2, 6.3, 6.4,
#               7.6, 10.1, 10.2, 14.1, 14.3, 14.4, 14.5
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from app.builder.events import BuilderErrorEvent
from app.builder.health_check import HealthCheckAnalyzer
from app.builder.llm_agent import BuilderLLMAgent
from app.builder.session_manager import BuilderSessionManager
from app.config import settings
from app.db import get_custom_scenario_store, get_profile_client
from app.scenarios.loader import load_scenario_from_dict
from app.scenarios.models import ArenaScenario
from app.scenarios.pretty_printer import pretty_print
from app.services.tier_calculator import calculate_tier, get_daily_limit
from app.utils.sse import format_sse_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/builder", tags=["builder"])

# ---------------------------------------------------------------------------
# Singletons / dependency factories
# ---------------------------------------------------------------------------

_session_manager = BuilderSessionManager()
_llm_agent = BuilderLLMAgent()
_health_check_analyzer = HealthCheckAnalyzer()


def get_builder_session_manager() -> BuilderSessionManager:
    return _session_manager


def get_builder_llm_agent() -> BuilderLLMAgent:
    return _llm_agent


def get_health_check_analyzer() -> HealthCheckAnalyzer:
    return _health_check_analyzer


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class BuilderChatRequest(BaseModel):
    email: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=5000)


class BuilderSaveRequest(BaseModel):
    email: str = Field(..., min_length=1)
    scenario_json: dict


class BuilderSaveResponse(BaseModel):
    scenario_id: str
    name: str
    readiness_score: float
    tier: str


# ---------------------------------------------------------------------------
# Token helpers (mirrors the pattern in profile.py / auth.py)
# ---------------------------------------------------------------------------


async def _get_token_balance(profile_client: Any, email: str) -> int:
    """Read the current token_balance from the waitlist document."""
    email_key = email.lower().strip()

    if settings.RUN_MODE == "local":
        import aiosqlite

        db_path = settings.SQLITE_DB_PATH
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute(
                "SELECT token_balance FROM waitlist WHERE email = ?",
                (email_key,),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 20
    else:
        waitlist_ref = profile_client._db.collection("waitlist").document(email_key)
        doc = await waitlist_ref.get()
        if doc.exists:
            return doc.to_dict().get("token_balance", 20)
        return 20


async def _deduct_token(profile_client: Any, email: str, current_balance: int) -> None:
    """Deduct 1 token from the waitlist document."""
    email_key = email.lower().strip()
    new_balance = max(0, current_balance - 1)

    if settings.RUN_MODE == "local":
        import aiosqlite

        db_path = settings.SQLITE_DB_PATH
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(
                "UPDATE waitlist SET token_balance = ? WHERE email = ?",
                (new_balance, email_key),
            )
            await conn.commit()
    else:
        waitlist_ref = profile_client._db.collection("waitlist").document(email_key)
        await waitlist_ref.update({"token_balance": new_balance})


# ---------------------------------------------------------------------------
# POST /builder/chat — SSE streaming chat
# ---------------------------------------------------------------------------


@router.post("/chat")
async def builder_chat(
    body: BuilderChatRequest,
    profile_client=Depends(get_profile_client),
    session_mgr: BuilderSessionManager = Depends(get_builder_session_manager),
    llm_agent: BuilderLLMAgent = Depends(get_builder_llm_agent),
):
    """Stream a builder chatbot response via SSE."""
    # 1. Validate email
    email = body.email.strip()
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Valid email required"})

    # 2. Verify profile exists
    profile = await profile_client.get_profile(email)
    if profile is None:
        return JSONResponse(
            status_code=403,
            content={"detail": "Profile required. Please create a profile first."},
        )

    # 3. Check token balance
    balance = await _get_token_balance(profile_client, email)
    if balance <= 0:
        return JSONResponse(
            status_code=429,
            content={"detail": "Daily token limit reached. Resets at midnight UTC."},
        )

    # 4. Deduct 1 token
    await _deduct_token(profile_client, email, balance)

    # 5. Get or create session
    session = session_mgr.get_session(body.session_id)
    if session is None:
        session = session_mgr.create_session(email)
        # Overwrite session_id to match the client's requested ID
        session_mgr._sessions.pop(session.session_id)
        session.session_id = body.session_id
        session_mgr._sessions[body.session_id] = session

    # 6. Add user message
    try:
        session_mgr.add_message(session.session_id, "user", body.message)
    except ValueError:
        return JSONResponse(
            status_code=429,
            content={"detail": "Session message limit reached (50). Please save or start a new session."},
        )

    # 7. Stream LLM response
    async def event_stream():
        event_id = 0
        accumulated_text = ""
        try:
            async for event in llm_agent.stream_response(
                conversation_history=session.conversation_history,
                partial_scenario=session.partial_scenario,
            ):
                event_id += 1
                yield format_sse_event(event, event_id=event_id)

                # Track assistant text for history
                if hasattr(event, "token"):
                    accumulated_text += event.token

                # Apply JSON deltas to session
                if hasattr(event, "section") and hasattr(event, "data"):
                    session_mgr.update_scenario(session.session_id, event.section, event.data)

            # Add assistant response to history
            if accumulated_text:
                session_mgr.add_message(session.session_id, "assistant", accumulated_text)

        except Exception as exc:
            logger.exception("Builder chat stream error")
            error_event = BuilderErrorEvent(
                event_type="builder_error",
                message=f"Stream error: {exc}",
            )
            yield format_sse_event(error_event, event_id=event_id + 1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# POST /builder/save — validate + health check + persist
# ---------------------------------------------------------------------------


@router.post("/save", response_model=BuilderSaveResponse)
async def builder_save(
    body: BuilderSaveRequest,
    profile_client=Depends(get_profile_client),
    store=Depends(get_custom_scenario_store),
    analyzer: HealthCheckAnalyzer = Depends(get_health_check_analyzer),
):
    """Validate scenario, run health check, persist, return summary."""
    # 1. Validate email
    email = body.email.strip()
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Valid email required"})

    # 2. Verify profile exists
    profile = await profile_client.get_profile(email)
    if profile is None:
        return JSONResponse(
            status_code=403,
            content={"detail": "Profile required. Please create a profile first."},
        )

    # 3. Validate scenario against ArenaScenario
    try:
        scenario = ArenaScenario.model_validate(body.scenario_json)
    except ValidationError as e:
        errors = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in e.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": "Validation failed", "errors": errors},
        )

    # 4. Round-trip validation: pretty_print → parse → re-validate
    try:
        serialized = pretty_print(scenario)
        reparsed_data = json.loads(serialized)
        reparsed_scenario = ArenaScenario.model_validate(reparsed_data)
        if reparsed_scenario.model_dump() != scenario.model_dump():
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "Round-trip validation failed: serialized scenario differs from original"
                },
            )
    except Exception as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": f"Round-trip validation error: {exc}"},
        )

    # 5. Run health check (stream SSE events)
    async def save_stream():
        event_id = 0
        readiness_score = 0
        tier_label = "Not Ready"

        try:
            # Load gold-standard scenarios for health check context
            gold_scenarios = _load_gold_standard_scenarios()

            async for event in analyzer.analyze(scenario, gold_scenarios):
                event_id += 1
                yield format_sse_event(event, event_id=event_id)

                # Extract readiness info from complete event
                if hasattr(event, "report") and isinstance(event.report, dict):
                    readiness_score = event.report.get("readiness_score", 0)
                    tier_label = event.report.get("tier", "Not Ready")

        except Exception as exc:
            logger.exception("Health check failed")
            error_event = BuilderErrorEvent(
                event_type="builder_error",
                message=f"Health check error: {exc}",
            )
            yield format_sse_event(error_event, event_id=event_id + 1)

        # 6. Persist scenario
        try:
            scenario_id = await store.save(email, scenario)
        except Exception as exc:
            logger.exception("Scenario save failed")
            error_event = BuilderErrorEvent(
                event_type="builder_error",
                message=f"Save error: {exc}",
            )
            yield format_sse_event(error_event, event_id=event_id + 1)
            return

        # 7. Emit save response as final SSE event
        save_response = {
            "event_type": "builder_save_complete",
            "scenario_id": scenario_id,
            "name": scenario.name,
            "readiness_score": readiness_score,
            "tier": tier_label,
        }
        event_id += 1
        yield f"id: {event_id}\ndata: {json.dumps(save_response)}\n\n"

    return StreamingResponse(
        save_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# GET /builder/scenarios — list user's custom scenarios
# ---------------------------------------------------------------------------


@router.get("/scenarios")
async def list_scenarios(
    email: str = Query(default=""),
    store=Depends(get_custom_scenario_store),
):
    """Return the user's custom scenarios."""
    if not email or not email.strip():
        return JSONResponse(status_code=401, content={"detail": "Valid email required"})

    scenarios = await store.list_by_email(email.strip())
    return scenarios


# ---------------------------------------------------------------------------
# DELETE /builder/scenarios/{scenario_id} — delete a custom scenario
# ---------------------------------------------------------------------------


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    email: str = Query(default=""),
    store=Depends(get_custom_scenario_store),
):
    """Delete a custom scenario by ID."""
    if not email or not email.strip():
        return JSONResponse(status_code=401, content={"detail": "Valid email required"})

    deleted = await store.delete(email.strip(), scenario_id)
    if not deleted:
        return JSONResponse(
            status_code=404,
            content={"detail": "Scenario not found or not owned by this email"},
        )

    return {"detail": "Scenario deleted", "scenario_id": scenario_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_gold_standard_scenarios() -> list[ArenaScenario]:
    """Load gold-standard scenario files for health check context."""
    from pathlib import Path

    scenarios_dir = Path("scenarios")
    gold_ids = {"talent-war", "b2b-sales", "ma-buyout", "freelance-gig", "urban-development"}
    results: list[ArenaScenario] = []

    if not scenarios_dir.exists():
        return results

    for path in scenarios_dir.glob("*.scenario.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("id") in gold_ids:
                results.append(ArenaScenario.model_validate(data))
        except Exception:
            logger.debug("Skipping gold-standard scenario %s", path)

    return results
