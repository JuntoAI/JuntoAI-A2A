"""SSE streaming endpoint and session start for real-time negotiations."""

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from app.config import settings
from app.db import get_custom_scenario_store, get_profile_client, get_session_store
from app.db.base import SessionStore
from app.middleware import get_event_buffer, get_sse_tracker
from app.middleware.event_buffer import SSEEventBuffer
from app.middleware.sse_limiter import SSEConnectionTracker
from app.models.events import (
    AgentMessageEvent,
    AgentThoughtEvent,
    EvaluationCompleteEvent,
    EvaluationInterviewEvent,
    NegotiationCompleteEvent,
    NegotiationStallEvent,
    StreamErrorEvent,
)
from app.models.history import DayGroup, SessionHistoryItem, SessionHistoryResponse
from app.orchestrator.evaluator import run_evaluation
from app.orchestrator.post_analysis import run_post_analysis
from app.models.negotiation import NegotiationStateModel
from app.orchestrator import model_router
from app.orchestrator.available_models import VALID_MODEL_IDS
from app.orchestrator.graph import run_negotiation
from app.orchestrator.state import create_initial_state
from app.scenarios.loader import load_scenario_from_dict
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry
from app.services.tier_calculator import calculate_tier, get_daily_limit
from app.utils.sse import format_sse_event
from app.orchestrator.usage_summary import compute_usage_summary
from app.utils.token_cost import compute_token_cost

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pure grouping logic — importable for property testing
# ---------------------------------------------------------------------------

TERMINAL_STATUSES = {"Agreed", "Blocked", "Failed"}


def _group_sessions_by_day(
    sessions: list[SessionHistoryItem],
) -> list[DayGroup]:
    """Group sessions by UTC date, sorted descending.

    Each group's sessions are sorted descending by ``created_at``.
    Groups themselves are sorted descending by ``date``.
    ``total_token_cost`` per group is the sum of session ``token_cost`` values.
    """
    buckets: dict[str, list[SessionHistoryItem]] = defaultdict(list)
    for s in sessions:
        # Extract UTC date from ISO timestamp (e.g. "2025-06-23T14:30:00Z" → "2025-06-23")
        utc_date = s.created_at[:10]
        buckets[utc_date].append(s)

    groups: list[DayGroup] = []
    for date_str in sorted(buckets, reverse=True):
        day_sessions = sorted(buckets[date_str], key=lambda s: s.created_at, reverse=True)
        groups.append(
            DayGroup(
                date=date_str,
                total_token_cost=sum(s.token_cost for s in day_sessions),
                sessions=day_sessions,
            )
        )
    return groups


# ---------------------------------------------------------------------------
# GET /negotiation/history — return grouped session history
# ---------------------------------------------------------------------------


@router.get("/negotiation/history", response_model=SessionHistoryResponse)
async def get_negotiation_history(
    email: str = Query(default="", description="User email"),
    days: int = Query(default=7, ge=1, le=90, description="Number of days to look back"),
    db: SessionStore = Depends(get_session_store),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
    custom_store=Depends(get_custom_scenario_store),
):
    """Return the user's completed negotiation sessions grouped by UTC day."""
    # Validate email presence
    if not email or not email.strip():
        return JSONResponse(
            status_code=422,
            content={"detail": "email query parameter is required"},
        )

    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    raw_sessions = await db.list_sessions_by_owner(email.strip(), cutoff_iso)

    # Build SessionHistoryItem list from raw docs
    items: list[SessionHistoryItem] = []
    for doc in raw_sessions:
        deal_status = doc.get("deal_status", "")
        if deal_status not in TERMINAL_STATUSES:
            continue

        scenario_id = doc.get("scenario_id", "")
        # Resolve scenario name from registry, then custom store, fallback to scenario_id
        scenario_name = scenario_id
        try:
            scenario = registry.get_scenario(scenario_id, email=email)
            scenario_name = scenario.name
        except Exception:
            try:
                custom_doc = await custom_store.get(email.strip(), scenario_id)
                if custom_doc and custom_doc.get("scenario_json"):
                    scenario_name = custom_doc["scenario_json"].get("name", scenario_id)
            except Exception:
                pass

        total_tokens_used = doc.get("total_tokens_used", 0) or 0
        items.append(
            SessionHistoryItem(
                session_id=doc.get("session_id", ""),
                scenario_id=scenario_id,
                scenario_name=scenario_name,
                deal_status=deal_status,
                total_tokens_used=total_tokens_used,
                token_cost=compute_token_cost(total_tokens_used),
                created_at=doc.get("created_at", ""),
                completed_at=doc.get("completed_at"),
            )
        )

    day_groups = _group_sessions_by_day(items)
    total_cost = sum(g.total_token_cost for g in day_groups)

    return SessionHistoryResponse(
        days=day_groups,
        total_token_cost=total_cost,
        period_days=days,
    )


# ---------------------------------------------------------------------------
# POST /negotiation/start — create session, deduct token, return session_id
# ---------------------------------------------------------------------------

class StartNegotiationRequest(BaseModel):
    email: str = Field(..., min_length=1)
    scenario_id: str = Field(..., min_length=1)
    active_toggles: list[str] = Field(default_factory=list)
    custom_prompts: dict[str, str] = Field(default_factory=dict)
    model_overrides: dict[str, str] = Field(default_factory=dict)
    structured_memory_enabled: bool = Field(default=False)
    structured_memory_roles: list[str] = Field(default_factory=list)
    milestone_summaries_enabled: bool = Field(default=False)
    no_memory_roles: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_custom_prompt_lengths(self) -> "StartNegotiationRequest":
        for role, prompt in self.custom_prompts.items():
            if len(prompt) > 500:
                raise ValueError(
                    f"Custom prompt for '{role}' exceeds 500 character limit "
                    f"({len(prompt)} chars)"
                )
        return self


class StartNegotiationResponse(BaseModel):
    session_id: str
    tokens_remaining: int
    max_turns: int


@router.post("/negotiation/start", response_model=StartNegotiationResponse)
async def start_negotiation(
    body: StartNegotiationRequest,
    db: SessionStore = Depends(get_session_store),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
    profile_client=Depends(get_profile_client),
    custom_store=Depends(get_custom_scenario_store),
):
    """Create a new negotiation session.

    Validates the scenario, builds initial state with toggle injection,
    persists to Firestore, and returns the session_id.
    """
    # 0. User status check (cloud mode only)
    if settings.RUN_MODE == "cloud":
        wl_ref = profile_client._db.collection("waitlist").document(body.email.lower().strip())
        wl_doc = await wl_ref.get()
        if wl_doc.exists:
            user_status = wl_doc.to_dict().get("user_status", "active")
            if user_status == "suspended":
                return JSONResponse(status_code=403, content={"detail": "Account suspended"})
            if user_status == "banned":
                return JSONResponse(status_code=403, content={"detail": "Account banned"})

    # 1. Validate scenario exists — check built-in registry first, then custom store
    normalized_email = body.email.lower().strip()
    scenario = None
    try:
        scenario = registry.get_scenario(body.scenario_id, email=normalized_email)
    except Exception:
        pass

    if scenario is None:
        # Fallback: look up in user's custom scenarios
        try:
            custom_doc = await custom_store.get(normalized_email, body.scenario_id)
            if custom_doc and custom_doc.get("scenario_json"):
                scenario = load_scenario_from_dict(custom_doc["scenario_json"])
            else:
                logger.warning(
                    "Custom scenario lookup returned no data: email=%s scenario_id=%s doc=%s",
                    normalized_email, body.scenario_id, custom_doc,
                )
        except Exception as exc:
            logger.error(
                "Custom scenario lookup failed: email=%s scenario_id=%s error=%s",
                normalized_email, body.scenario_id, exc,
                exc_info=True,
            )

    if scenario is None:
        logger.warning(
            "Scenario not found in registry or custom store: scenario_id=%s email=%s",
            body.scenario_id, normalized_email,
        )
        return JSONResponse(
            status_code=404,
            content={"detail": f"Scenario '{body.scenario_id}' not found"},
        )

    # 2. Validate model_overrides against available models
    if body.model_overrides:
        for role, mid in body.model_overrides.items():
            if mid not in VALID_MODEL_IDS:
                return JSONResponse(
                    status_code=422,
                    content={"detail": f"Invalid model_id '{mid}' for role '{role}'. Available models: {sorted(VALID_MODEL_IDS)}"},
                )

    # 3. Filter custom_prompts and model_overrides to valid agent roles
    agent_roles = {a.role for a in scenario.agents}
    filtered_custom_prompts = {k: v for k, v in body.custom_prompts.items() if k in agent_roles}
    filtered_model_overrides = {k: v for k, v in body.model_overrides.items() if k in agent_roles}

    # 4. Build hidden context from active toggles
    hidden_context: dict = {}
    for toggle in scenario.toggles:
        if toggle.id in body.active_toggles:
            hidden_context[toggle.target_agent_role] = toggle.hidden_context_payload

    # 5. Create session state
    # Enforce dependency: milestone summaries require structured memory
    structured_memory_enabled = body.structured_memory_enabled
    if body.milestone_summaries_enabled:
        structured_memory_enabled = True

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
        custom_prompts=filtered_custom_prompts,
        model_overrides=filtered_model_overrides,
        structured_memory_enabled=structured_memory_enabled,
        structured_memory_roles=body.structured_memory_roles,
        milestone_summaries_enabled=body.milestone_summaries_enabled,
        no_memory_roles=body.no_memory_roles,
    )

    # 6. Persist session
    if settings.RUN_MODE == "cloud":
        # Cloud: store via Firestore internals (owner_email for auth)
        doc_data = state.model_dump()
        doc_data["owner_email"] = body.email
        doc_data["created_at"] = datetime.now(timezone.utc).isoformat()
        doc_ref = db._collection.document(session_id)  # type: ignore[attr-defined]
        await doc_ref.set(doc_data)
    else:
        # Local: use the SessionStore protocol
        await db.create_session(state)
        # Add created_at metadata (not part of NegotiationStateModel)
        await db.update_session(session_id, {"created_at": datetime.now(timezone.utc).isoformat()})

    # 7. Return session info (tokens deducted after negotiation completes)
    if settings.RUN_MODE == "cloud":
        waitlist_ref = profile_client._db.collection("waitlist").document(body.email.lower().strip())
        waitlist_doc = await waitlist_ref.get()
        if waitlist_doc.exists:
            tokens_remaining = waitlist_doc.to_dict().get("token_balance", 0)
        else:
            tokens_remaining = 0

        # Determine tier-aware daily limit from profile
        profile = await profile_client.get_profile(body.email.lower().strip())
        if profile is not None:
            tier = calculate_tier(
                profile.get("profile_completed_at"),
                profile.get("email_verified", False),
            )
            daily_limit = get_daily_limit(tier)
        else:
            daily_limit = get_daily_limit(1)  # Tier 1 default

        # If no waitlist doc existed, fall back to the tier daily limit
        if not waitlist_doc.exists:
            tokens_remaining = daily_limit
    else:
        tokens_remaining = 999  # unlimited in local mode

    return StartNegotiationResponse(
        session_id=session_id,
        tokens_remaining=tokens_remaining,
        max_turns=state.max_turns,
    )


def _build_role_name_map(agent_states: dict[str, dict]) -> dict[str, str]:
    """Build a role→display-name mapping from agent_states.

    Falls back to the role key itself if no ``name`` field is present.
    """
    return {
        role: info.get("name", role)
        for role, info in agent_states.items()
    }


def _resolve_name(role: str, role_name_map: dict[str, str]) -> str:
    """Resolve an internal role to its display name."""
    return role_name_map.get(role, role)


def _find_warned_negotiator(
    history: list[dict],
    regulator_index: int,
    agent_states: dict[str, dict] | None = None,
) -> str:
    """Walk backward from a regulator entry to find the most recent negotiator.

    Looks past other non-negotiator entries (observers, other regulators)
    that may sit between the negotiator and the regulator in history.

    Fallback chain when the backward walk finds no negotiator:
    1. Scan the regulator's reasoning text for mentions of known negotiator
       role names or display names.
    2. Return the first negotiator role from ``agent_states``.
    3. Return ``"Unknown"`` only as a last resort.
    """
    # Primary: walk backward through history
    for j in range(regulator_index - 1, -1, -1):
        if history[j].get("agent_type") == "negotiator":
            return history[j].get("role", "Unknown")

    # Fallback: use agent_states to resolve from reasoning text or pick first negotiator
    if agent_states:
        negotiator_roles = [
            role for role, info in agent_states.items()
            if info.get("agent_type") == "negotiator"
        ]
        if negotiator_roles:
            # Try to match a negotiator name/role in the regulator's reasoning
            entry = history[regulator_index] if regulator_index < len(history) else {}
            content = entry.get("content", {})
            reasoning = (
                content.get("reasoning", "") or content.get("public_message", "")
            ).lower()
            if reasoning:
                for role in negotiator_roles:
                    name = agent_states[role].get("name", role)
                    if role.lower() in reasoning or name.lower() in reasoning:
                        return role
            # No text match — return the first negotiator role
            return negotiator_roles[0]

    return "Unknown"


def _format_price_for_summary(price: float, value_format: str = "currency", value_label: str = "Price") -> str:
    """Format a price value for participant summaries."""
    if value_format == "time_from_22":
        total_minutes = 22 * 60 + round(price)
        hours24 = (total_minutes // 60) % 24
        mins = total_minutes % 60
        period = "PM" if hours24 >= 12 else "AM"
        hours12 = 12 if hours24 == 0 else (hours24 - 12 if hours24 > 12 else hours24)
        return f"{hours12}:{mins:02d} {period}"
    elif value_format == "percent":
        return f"{round(price)}%"
    elif value_format == "number":
        return f"{price:,.0f}"
    else:
        return f"${price:,.0f}"


def _build_participant_summaries(
    history: list[dict],
    agent_states: dict[str, dict],
    value_format: str = "currency",
    value_label: str = "Price",
) -> list[dict]:
    """Build a 1-2 sentence summary per participant from the negotiation history.

    For negotiators: captures their final position and core argument.
    For regulators: captures their enforcement stance.
    """
    role_name_map = _build_role_name_map(agent_states)
    # Collect last message per role (iterate forward, overwrite)
    last_entry: dict[str, dict] = {}
    first_entry: dict[str, dict] = {}
    for entry in history:
        role = entry.get("role", "")
        if not role:
            continue
        if role not in first_entry:
            first_entry[role] = entry
        last_entry[role] = entry

    summaries: list[dict] = []
    for role, info in agent_states.items():
        agent_type = info.get("agent_type", "negotiator")
        name = _resolve_name(role, role_name_map)
        last = last_entry.get(role)
        first = first_entry.get(role)
        if not last:
            continue

        content = last.get("content", {})

        if agent_type == "negotiator":
            # Extract final proposed price and core argument
            final_price = content.get("proposed_price", 0)
            last_msg = content.get("public_message", "")
            # Build a meaningful summary from the last message
            parts: list[str] = []
            if final_price and final_price > 0:
                parts.append(f"Ended at {_format_price_for_summary(final_price, value_format, value_label)}")
            if last_msg:
                # Use the last 2 meaningful sentences (skip short greetings)
                sentences = [s.strip() for s in last_msg.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) > 15]
                tail = sentences[-2:] if len(sentences) >= 2 else sentences
                if tail:
                    parts.append(". ".join(tail))

            summaries.append({
                "role": role,
                "name": name,
                "agent_type": agent_type,
                "summary": ". ".join(parts) if parts else f"Participated as {name}",
            })

        elif agent_type == "regulator":
            warning_count = info.get("warning_count", 0)
            status = content.get("status", "")
            reasoning = content.get("reasoning", "") or content.get("public_message", "")
            # Use last 2 meaningful sentences instead of just the first
            sentences = [s.strip() for s in reasoning.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) > 15] if reasoning else []
            stance = ". ".join(sentences[-2:]) if sentences else ""

            summary_text = ""
            if status == "BLOCKED":
                summary_text = f"Blocked the deal after issuing {warning_count} warning(s). {stance}"
            elif warning_count > 0:
                summary_text = f"Issued {warning_count} warning(s). {stance}"
            else:
                summary_text = stance or f"Monitored the negotiation as {name}"

            summaries.append({
                "role": role,
                "name": name,
                "agent_type": agent_type,
                "summary": summary_text.strip(),
            })

        elif agent_type == "observer":
            observation = content.get("observation", "") or content.get("public_message", "")
            sentences = [s.strip() for s in observation.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) > 15] if observation else []
            stance = ". ".join(sentences[-2:]) if sentences else ""
            summaries.append({
                "role": role,
                "name": name,
                "agent_type": agent_type,
                "summary": stance or f"Observed as {name}",
            })

    return summaries


def _build_block_advice(history: list[dict], blocker: str, agent_states: dict[str, dict] | None = None) -> list[dict]:
    """Build actionable advice from regulator warnings that led to a block.

    Returns a list of advice objects, each containing:
    - ``agent_role``: which agent to adjust
    - ``issue``: what the regulator flagged
    - ``suggested_prompt``: a ready-to-use custom_prompts snippet (≤500 chars)
      the user can paste into the "Advanced Options" panel when re-running
    """
    # Build role→name map for display-friendly labels
    role_name_map = _build_role_name_map(agent_states) if agent_states else {}

    # Collect (warned_agent_role, warning_reasoning) pairs.
    # Include both WARNING and BLOCKED entries — a BLOCKED entry is the
    # final escalation and contains the most complete reasoning about what
    # went wrong.
    flagged: list[tuple[str, str]] = []
    for i, entry in enumerate(history):
        if entry.get("agent_type") != "regulator":
            continue
        content = entry.get("content", {})
        status = content.get("status")
        if status not in ("WARNING", "BLOCKED"):
            continue
        reasoning = content.get("reasoning", "") or content.get("public_message", "")
        # Walk backward to find the negotiator this warning targets
        warned_role = _find_warned_negotiator(history, i, agent_states)
        flagged.append((warned_role, reasoning))

    if not flagged:
        # Last resort: no WARNING/BLOCKED entries found in history at all.
        # Find the last negotiator who spoke before the block as the most
        # likely agent to adjust.
        fallback_role = "Unknown"
        for entry in reversed(history):
            if entry.get("agent_type") == "negotiator":
                fallback_role = entry.get("role", "Unknown")
                break
        # If history walk failed, pick the first negotiator from agent_states
        if fallback_role == "Unknown" and agent_states:
            for role, info in agent_states.items():
                if info.get("agent_type") == "negotiator":
                    fallback_role = role
                    break
        display_name = _resolve_name(fallback_role, role_name_map)
        return [{
            "agent_role": display_name,
            "issue": f"{blocker} blocked the deal after repeated warnings.",
            "suggested_prompt": (
                "Focus on collaborative problem-solving. If the mediator "
                "warns you about a tactic, immediately drop it and pivot "
                "to a different, fact-based argument."
            ),
        }]

    # Group warnings by agent role
    by_role: dict[str, list[str]] = {}
    for role, reason in flagged:
        by_role.setdefault(role, []).append(reason)

    advice: list[dict] = []
    for role, reasons in by_role.items():
        display_name = _resolve_name(role, role_name_map)
        # Summarize the pattern from the first two warnings (keeps it concise)
        issue_summary = reasons[0][:200]
        if len(reasons) > 1:
            issue_summary += f" (repeated {len(reasons)}x)"

        prompt = (
            f"IMPORTANT: The mediator has flagged your approach {len(reasons)} "
            f"time(s). You MUST change tactics. Rules: "
            f"1) Never repeat an argument the mediator already warned about. "
            f"2) Lead with concrete proposals and logistics, not emotions. "
            f"3) Mention your track record only once, then move on. "
            f"4) If warned, acknowledge it and immediately offer a new "
            f"safety measure or creative compromise instead."
        )

        advice.append({
            "agent_role": display_name,
            "issue": issue_summary,
            "suggested_prompt": prompt,
        })

    return advice


def _format_outcome_value(offer: float, state: dict) -> str:
    """Format the final offer value using the scenario's value_format.

    Falls back to currency formatting if no format is specified.
    """
    neg_params = state.get("scenario_config", {}).get("negotiation_params", {})
    value_format = neg_params.get("value_format", "currency")
    value_label = neg_params.get("value_label", "Price")

    if value_format == "time_from_22":
        # Convert minutes-from-22:00 to human-readable time
        total_minutes = 22 * 60 + round(offer)
        hours24 = (total_minutes // 60) % 24
        mins = total_minutes % 60
        period = "PM" if hours24 >= 12 else "AM"
        hours12 = 12 if hours24 == 0 else (hours24 - 12 if hours24 > 12 else hours24)
        time_str = f"{hours12}:{mins:02d} {period}"
        return f"All parties reached agreement — {value_label}: {time_str}"
    elif value_format == "percent":
        return f"All parties reached agreement at {round(offer)}%"
    elif value_format == "number":
        return f"All parties reached agreement — {value_label}: {offer:,.0f}"
    else:
        return f"All parties reached agreement at ${offer:,.0f}"


def _reconstruct_events_from_session(session_id: str, raw_doc: dict, scenario_config: dict | None = None) -> list:
    """Reconstruct SSE events from a persisted terminal session document.

    Used when viewing a completed negotiation from history — replays the
    saved history as thought + message events followed by a terminal
    NegotiationCompleteEvent, without re-running the orchestrator.

    Parameters
    ----------
    scenario_config:
        Full scenario config dict. Used as a fallback when the session
        document does not contain scenario_config (pre-persistence sessions).
    """
    # Ensure scenario_config is available on the doc for formatting
    if "scenario_config" not in raw_doc and scenario_config:
        raw_doc = {**raw_doc, "scenario_config": scenario_config}
    events: list = []
    history = raw_doc.get("history", [])

    for entry in history:
        role = entry.get("role", "Unknown")
        agent_type = entry.get("agent_type", "negotiator")
        turn_number = entry.get("turn_number", 0)
        content = entry.get("content", {})

        # Confirmation entries — emit final_statement as public message
        if agent_type == "confirmation":
            final_statement = content.get("final_statement", "")
            if final_statement:
                events.append(AgentMessageEvent(
                    event_type="agent_message",
                    agent_name=role,
                    public_message=final_statement,
                    turn_number=turn_number,
                ))
            continue

        # Thought event
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

    # Terminal event
    deal_status = raw_doc.get("deal_status", "Failed")
    summary: dict = {
        "current_offer": raw_doc.get("current_offer", 0),
        "turns_completed": raw_doc.get("turn_count", 0),
        "total_warnings": raw_doc.get("warning_count", 0),
        "ai_tokens_used": raw_doc.get("total_tokens_used", 0),
    }

    agent_states = raw_doc.get("agent_states", {})

    # Use AI-generated participant summaries if persisted, else fall back to extraction
    persisted_summaries = raw_doc.get("participant_summaries")
    if persisted_summaries and isinstance(persisted_summaries, list):
        summary["participant_summaries"] = persisted_summaries
    elif agent_states:
        neg_params = raw_doc.get("scenario_config", {}).get("negotiation_params", {})
        summary["participant_summaries"] = _build_participant_summaries(
            history, agent_states,
            value_format=neg_params.get("value_format", "currency"),
            value_label=neg_params.get("value_label", "Price"),
        )

    # Include tipping point analysis if persisted
    tipping_point = raw_doc.get("tipping_point")
    if tipping_point and isinstance(tipping_point, str):
        summary["tipping_point"] = tipping_point

    if deal_status == "Agreed":
        offer = raw_doc.get("current_offer", 0)
        summary["outcome"] = _format_outcome_value(offer, raw_doc)
    elif deal_status == "Blocked":
        blocker = "Regulator"
        block_reason = ""
        for h in reversed(history):
            if h.get("agent_type") == "regulator":
                c = h.get("content", {})
                if c.get("status") in ("BLOCKED", "WARNING"):
                    blocker = h.get("role", "Regulator")
                    block_reason = c.get("public_message", c.get("reasoning", ""))
                    break
        summary["blocked_by"] = blocker
        summary["reason"] = block_reason or f"{blocker} issued 3 warnings — deal terminated"
        summary["advice"] = _build_block_advice(history, blocker, agent_states)
    elif deal_status == "Failed":
        max_turns = raw_doc.get("max_turns", 0)
        stall = raw_doc.get("stall_diagnosis")
        if stall and isinstance(stall, dict):
            summary["reason"] = f"Negotiation stalled: {stall.get('stall_type', 'unknown pattern')}"
            summary["stall_diagnosis"] = stall
        else:
            summary["reason"] = f"Reached maximum of {max_turns} turns without agreement"

    # Include persisted evaluation report if available
    evaluation = raw_doc.get("evaluation")
    if evaluation and isinstance(evaluation, dict):
        summary["evaluation"] = evaluation

    # Compute usage summary from persisted agent_calls telemetry (Spec 145).
    # This covers old sessions that were completed before the live-stream
    # fix, as well as replayed sessions viewed from history.
    summary["usage_summary"] = compute_usage_summary(
        raw_doc.get("agent_calls", [])
    )

    events.append(NegotiationCompleteEvent(
        event_type="negotiation_complete",
        session_id=session_id,
        deal_status=deal_status,
        final_summary=summary,
    ))

    return events


def _snapshot_to_events(
    snapshot: dict,
    session_id: str,
    accumulated_history: list[dict] | None = None,
    accumulated_agent_calls: list[dict] | None = None,
    scenario_config: dict | None = None,
):
    """Convert a LangGraph state snapshot into SSE events.

    Each snapshot is keyed by node name. We extract the latest history
    entry and convert it to thought + message events.

    Dispatcher snapshots may contain a terminal ``deal_status`` without
    any ``history`` entries (the dispatcher only sets status flags).
    We must still emit a ``NegotiationCompleteEvent`` in that case.

    Parameters
    ----------
    accumulated_history:
        Full negotiation history accumulated across all prior snapshots.
        Used by the dispatcher early-exit path to build participant
        summaries when the delta itself has no history.
    accumulated_agent_calls:
        Full agent_calls list accumulated across all prior snapshots.
        Used for usage summary computation since individual snapshot
        deltas (especially the dispatcher) may not contain agent_calls.
    scenario_config:
        Full scenario config dict. Used as a fallback when the snapshot
        delta does not include scenario_config (e.g. dispatcher node).
    """
    if accumulated_history is None:
        accumulated_history = []
    if accumulated_agent_calls is None:
        accumulated_agent_calls = []
    if scenario_config is None:
        scenario_config = {}
    events = []
    for _node_name, state in snapshot.items():
        if not isinstance(state, dict):
            continue

        # Ensure scenario_config is available on the snapshot delta.
        # Dispatcher nodes don't include it, so fall back to the
        # caller-provided scenario_config.
        if "scenario_config" not in state and scenario_config:
            state = {**state, "scenario_config": scenario_config}

        # Handle dispatcher snapshots that set a terminal deal_status
        # but contain no history entries (e.g. max_turns reached,
        # or agreement detected by the dispatcher).
        history = state.get("history", [])
        if not history:
            deal_status = state.get("deal_status", "")
            if deal_status in ("Agreed", "Blocked", "Failed"):
                summary: dict = {
                    "current_offer": state.get("current_offer", 0),
                    "turns_completed": state.get("turn_count", 0),
                    "total_warnings": state.get("warning_count", 0),
                    "ai_tokens_used": state.get("total_tokens_used", 0),
                }

                # Build per-agent summaries when agent_states is available
                # (the dispatcher now forwards agent_states for Agreed).
                # Note: history is empty in the delta, so summaries will
                # use agent_states metadata only.  For richer summaries
                # the accumulated_history from the streaming loop is used.
                agent_states_data = state.get("agent_states", {})
                if agent_states_data:
                    neg_params = state.get("scenario_config", {}).get("negotiation_params", {})
                    summary["participant_summaries"] = _build_participant_summaries(
                        accumulated_history, agent_states_data,
                        value_format=neg_params.get("value_format", "currency"),
                        value_label=neg_params.get("value_label", "Price"),
                    )

                if deal_status == "Agreed":
                    offer = state.get("current_offer", 0)
                    summary["outcome"] = _format_outcome_value(offer, state)

                elif deal_status == "Failed":
                    max_turns = state.get("max_turns", 0)
                    stall = state.get("stall_diagnosis")
                    if stall and isinstance(stall, dict):
                        summary["reason"] = f"Negotiation stalled: {stall.get('stall_type', 'unknown pattern')}"
                        summary["stall_diagnosis"] = stall
                        events.append(NegotiationStallEvent(
                            event_type="negotiation_stall",
                            session_id=session_id,
                            stall_type=stall.get("stall_type", ""),
                            confidence=stall.get("confidence", 0.0),
                            advice=stall.get("advice", []),
                            details=stall.get("details", {}),
                        ))
                    else:
                        summary["reason"] = f"Reached maximum of {max_turns} turns without agreement"
                summary["usage_summary"] = compute_usage_summary(
                    accumulated_agent_calls or state.get("agent_calls", [])
                )
                events.append(NegotiationCompleteEvent(
                    event_type="negotiation_complete",
                    session_id=session_id,
                    deal_status=deal_status,
                    final_summary=summary,
                ))
            continue
        entry = history[-1]
        role = entry.get("role", "Unknown")
        agent_type = entry.get("agent_type", "negotiator")
        # Use turn_count from state (increments on full cycle wrap).
        # Fall back to the entry's own turn_number, then 0.
        # This is important because some snapshot deltas (e.g. confirmation
        # node) don't include turn_count in their state delta.
        turn_number = state.get("turn_count", None)
        if turn_number is None:
            turn_number = entry.get("turn_number", 0)
        content = entry.get("content", {})

        # Handle confirmation entries — emit final_statement as public message
        if agent_type == "confirmation":
            # The confirmation node snapshot does NOT include turn_count
            # in its state delta, so state.get("turn_count", 0) falls
            # back to 0.  Use the turn_number stored inside the history
            # entry itself (set by confirmation_node from the full state).
            conf_turn = entry.get("turn_number", turn_number)
            final_statement = content.get("final_statement", "")
            if final_statement:
                events.append(AgentMessageEvent(
                    event_type="agent_message",
                    agent_name=role,
                    public_message=final_statement,
                    turn_number=conf_turn,
                ))
            continue

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

        # Check for terminal state (Confirming is NOT terminal)
        deal_status = state.get("deal_status", "Negotiating")
        if deal_status in ("Agreed", "Blocked", "Failed"):
            summary: dict = {
                "current_offer": state.get("current_offer", 0),
                "turns_completed": state.get("turn_count", 0),
                "total_warnings": state.get("warning_count", 0),
                "ai_tokens_used": state.get("total_tokens_used", 0),
            }

            # Build per-agent summaries for all outcomes
            agent_states = state.get("agent_states", {})
            if agent_states:
                neg_params = state.get("scenario_config", {}).get("negotiation_params", {})
                summary["participant_summaries"] = _build_participant_summaries(
                    history, agent_states,
                    value_format=neg_params.get("value_format", "currency"),
                    value_label=neg_params.get("value_label", "Price"),
                )

            if deal_status == "Agreed":
                summary["outcome"] = _format_outcome_value(state.get("current_offer", 0), state)

            elif deal_status == "Blocked":
                # Find which regulator blocked and why from history
                blocker = "Regulator"
                block_reason = ""
                for h in reversed(history):
                    if h.get("agent_type") == "regulator":
                        c = h.get("content", {})
                        if c.get("status") in ("BLOCKED", "WARNING"):
                            blocker = h.get("role", "Regulator")
                            block_reason = c.get("public_message", c.get("reasoning", ""))
                            break
                summary["blocked_by"] = blocker
                summary["reason"] = block_reason or f"{blocker} issued 3 warnings — deal terminated"

                # Build actionable advice from warning history
                summary["advice"] = _build_block_advice(history, blocker, agent_states)

            elif deal_status == "Failed":
                max_turns = state.get("max_turns", 0)
                summary["reason"] = f"Reached maximum of {max_turns} turns without agreement"

                # Check for stall diagnosis
                stall = state.get("stall_diagnosis")
                if stall and isinstance(stall, dict):
                    summary["reason"] = f"Negotiation stalled: {stall.get('stall_type', 'unknown pattern')}"
                    summary["stall_diagnosis"] = stall
                    events.append(NegotiationStallEvent(
                        event_type="negotiation_stall",
                        session_id=session_id,
                        stall_type=stall.get("stall_type", ""),
                        confidence=stall.get("confidence", 0.0),
                        advice=stall.get("advice", []),
                        details=stall.get("details", {}),
                    ))

            summary["usage_summary"] = compute_usage_summary(
                accumulated_agent_calls or state.get("agent_calls", [])
            )
            events.append(NegotiationCompleteEvent(
                event_type="negotiation_complete",
                session_id=session_id,
                deal_status=deal_status,
                final_summary=summary,
            ))

    return events


@router.get("/negotiation/stream/{session_id}")
async def stream_negotiation(
    session_id: str,
    email: str = Query(...),
    db: SessionStore = Depends(get_session_store),
    tracker: SSEConnectionTracker = Depends(get_sse_tracker),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
    event_buffer: SSEEventBuffer = Depends(get_event_buffer),
    profile_client=Depends(get_profile_client),
    last_event_id: int | None = Query(None, alias="last_event_id"),
):
    """Open an SSE stream for a negotiation session.

    Validates session existence, email ownership, and connection limits
    before returning a StreamingResponse of SSE-formatted events.

    Supports reconnection: if ``last_event_id`` query param is provided,
    replays buffered events after that ID before streaming new ones.
    """
    # 1. Session lookup — raises SessionNotFoundError → 404 via exception handler
    raw_doc = await db.get_session_doc(session_id)

    # 2. Email ownership check (cloud mode only)
    if settings.RUN_MODE == "cloud":
        owner_email = raw_doc.get("owner_email")
        if owner_email is not None and owner_email != email:
            return JSONResponse(
                status_code=403,
                content={"detail": "Email does not match session owner"},
            )

    # 3. Build state model (extra="ignore" drops owner_email, created_at, etc.)
    state = NegotiationStateModel(**raw_doc)

    # 4. Load scenario config for the orchestrator
    #    Check built-in registry first, then fall back to custom scenario store.
    scenario = None
    try:
        scenario = registry.get_scenario(state.scenario_id, email=email)
    except Exception:
        pass

    if scenario is None:
        normalized_email = email.strip().lower()
        custom_store = get_custom_scenario_store()
        try:
            custom_doc = await custom_store.get(normalized_email, state.scenario_id)
            if custom_doc and custom_doc.get("scenario_json"):
                scenario = load_scenario_from_dict(custom_doc["scenario_json"])
        except Exception as exc:
            logger.error(
                "Custom scenario lookup failed in stream: email=%s scenario_id=%s error=%s",
                normalized_email, state.scenario_id, exc,
                exc_info=True,
            )

    if scenario is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Scenario '{state.scenario_id}' not found"},
        )

    scenario_config = scenario.model_dump()

    # 5. Acquire connection slot
    # Reconnections (last_event_id present) get a free pass — they replace
    # a dead connection whose release may not have fired yet on the server.
    is_reconnect = last_event_id is not None
    if not is_reconnect:
        acquired = await tracker.acquire(email)
        if not acquired:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Concurrent SSE connection limit reached (max 3)"
                },
            )
    else:
        # Best-effort acquire for reconnects — proceed even if over limit
        await tracker.acquire(email)

    # 5a. Check if this is a reconnect to a terminal session — replay and close
    if last_event_id is not None and await event_buffer.is_session_terminal(session_id):
        replay = await event_buffer.replay_after(session_id, last_event_id)

        async def replay_stream():
            try:
                for eid, evt_data in replay:
                    yield f"id: {eid}\ndata: {evt_data}\n\n"
            finally:
                await tracker.release(email)

        return StreamingResponse(
            replay_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # 5b. Check if session is already terminal (viewing from history).
    #     Reconstruct events from persisted state instead of re-running.
    if state.deal_status in TERMINAL_STATUSES:
        # Load scenario config for value formatting (old sessions may not
        # have scenario_config persisted on the document).
        replay_scenario_config = raw_doc.get("scenario_config")
        if not replay_scenario_config:
            try:
                sc = registry.get_scenario(state.scenario_id, email=email)
                replay_scenario_config = sc.model_dump()
            except Exception:
                # Fallback: try custom scenario store
                try:
                    cs = get_custom_scenario_store()
                    custom_doc = await cs.get(email.strip().lower(), state.scenario_id)
                    if custom_doc and custom_doc.get("scenario_json"):
                        replay_scenario_config = load_scenario_from_dict(
                            custom_doc["scenario_json"]
                        ).model_dump()
                except Exception:
                    replay_scenario_config = None
        reconstructed = _reconstruct_events_from_session(session_id, raw_doc, replay_scenario_config)

        async def history_replay_stream():
            try:
                for idx, event in enumerate(reconstructed, start=1):
                    yield format_sse_event(event, event_id=idx)
            finally:
                await tracker.release(email)

        return StreamingResponse(
            history_replay_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # 6. Build initial orchestrator state
    initial_state = create_initial_state(
        session_id=session_id,
        scenario_config=scenario_config,
        active_toggles=state.active_toggles,
        hidden_context=state.hidden_context,
        custom_prompts=state.custom_prompts,
        model_overrides=state.model_overrides,
        structured_memory_enabled=state.structured_memory_enabled,
        structured_memory_roles=state.structured_memory_roles,
        milestone_summaries_enabled=state.milestone_summaries_enabled,
        no_memory_roles=state.no_memory_roles,
    )

    # 7. Build the async event stream generator
    async def event_stream():
        timeout = state.max_turns * 60  # 60s per turn to account for LLM latency
        ai_tokens_used = 0

        # Accumulate final state for write-back after negotiation completes.
        # These fields are tracked across all snapshots so the session
        # document reflects the final negotiation outcome.
        final_state: dict = {
            "deal_status": "Negotiating",
            "turn_count": 0,
            "current_offer": 0.0,
            "warning_count": 0,
            "total_tokens_used": 0,
            "agent_calls": [],
            "history": [],
            "agent_states": {},
            "scenario_config": scenario_config,
        }

        # If reconnecting, replay missed events first
        if last_event_id is not None:
            replay = await event_buffer.replay_after(session_id, last_event_id)
            for eid, evt_data in replay:
                yield f"id: {eid}\ndata: {evt_data}\n\n"

        try:
            async with asyncio.timeout(timeout):
                accumulated_history: list[dict] = []
                held_complete_event: NegotiationCompleteEvent | None = None
                last_terminal_state: dict | None = None

                async for snapshot in run_negotiation(initial_state, scenario_config):
                    # Accumulate history and state from each snapshot delta
                    for _node, s in snapshot.items():
                        if isinstance(s, dict):
                            accumulated_history.extend(s.get("history", []))
                            # Accumulate agent_calls (append-only, same as LangGraph add reducer)
                            final_state["agent_calls"].extend(s.get("agent_calls", []))
                            # Track latest values for scalar fields
                            if "deal_status" in s:
                                final_state["deal_status"] = s["deal_status"]
                            if "turn_count" in s:
                                final_state["turn_count"] = max(final_state["turn_count"], s["turn_count"])
                            if "current_offer" in s and s["current_offer"]:
                                final_state["current_offer"] = s["current_offer"]
                            if "warning_count" in s:
                                final_state["warning_count"] = max(final_state["warning_count"], s["warning_count"])
                            if "total_tokens_used" in s:
                                final_state["total_tokens_used"] = max(final_state["total_tokens_used"], s["total_tokens_used"])
                            if "agent_states" in s and s["agent_states"]:
                                final_state["agent_states"] = s["agent_states"]
                    final_state["history"] = accumulated_history
                    events = _snapshot_to_events(snapshot, session_id, accumulated_history, final_state["agent_calls"], scenario_config)
                    # Track tokens and terminal state from snapshot
                    for _node, s in snapshot.items():
                        if isinstance(s, dict):
                            ai_tokens_used = max(ai_tokens_used, s.get("total_tokens_used", 0))
                            if s.get("deal_status") in ("Agreed", "Blocked", "Failed"):
                                last_terminal_state = s
                    for event in events:
                        if isinstance(event, NegotiationCompleteEvent):
                            # Hold back — we'll emit after evaluation
                            held_complete_event = event
                            continue
                        json_data = event.model_dump_json()
                        eid = await event_buffer.append(session_id, json_data)
                        yield format_sse_event(event, event_id=eid)

                # Run evaluation if enabled (between negotiation end and complete event)
                if held_complete_event is not None:
                    evaluation_report = None

                    terminal_for_work = {
                        **(last_terminal_state or {}),
                        "history": accumulated_history,
                    }

                    # Kick off post-analysis immediately — it only needs the transcript,
                    # not the evaluation results, so it can run concurrently.
                    post_analysis_task = asyncio.create_task(
                        run_post_analysis(terminal_for_work, scenario_config)
                    )

                    try:
                        evaluator_config = scenario_config.get("evaluator_config")
                        evaluator_enabled = evaluator_config is None or evaluator_config.get("enabled", True)
                        if evaluator_enabled and last_terminal_state is not None:
                            # Interviews inside run_evaluation are parallelized via asyncio.gather
                            async for eval_event in run_evaluation(terminal_for_work, scenario_config):
                                json_data = eval_event.model_dump_json()
                                eid = await event_buffer.append(session_id, json_data)
                                yield format_sse_event(eval_event, event_id=eid)
                                if isinstance(eval_event, EvaluationCompleteEvent):
                                    evaluation_report = eval_event.model_dump()

                            if evaluation_report:
                                held_complete_event.final_summary["evaluation"] = evaluation_report
                                final_state["evaluation"] = evaluation_report
                    except Exception:
                        logger.exception("Evaluation failed for session %s", session_id)

                    # Await post-analysis (likely already done by now since it ran concurrently)
                    try:
                        analysis = await post_analysis_task
                        if analysis.get("participant_summaries"):
                            held_complete_event.final_summary["participant_summaries"] = analysis["participant_summaries"]
                            final_state["participant_summaries"] = analysis["participant_summaries"]
                        if analysis.get("tipping_point"):
                            held_complete_event.final_summary["tipping_point"] = analysis["tipping_point"]
                            final_state["tipping_point"] = analysis["tipping_point"]
                    except Exception:
                        logger.exception("Post-analysis failed for session %s", session_id)

                    # NOW emit the held-back NegotiationCompleteEvent
                    json_data = held_complete_event.model_dump_json()
                    eid = await event_buffer.append(session_id, json_data, is_terminal=True)
                    yield format_sse_event(held_complete_event, event_id=eid)
                    return
        except TimeoutError:
            final_state["deal_status"] = "Failed"
            timeout_event = NegotiationCompleteEvent(
                event_type="negotiation_complete",
                session_id=session_id,
                deal_status="Failed",
                final_summary={"reason": "timeout"},
            )
            json_data = timeout_event.model_dump_json()
            eid = await event_buffer.append(session_id, json_data, is_terminal=True)
            yield format_sse_event(timeout_event, event_id=eid)
        except Exception as e:
            logger.exception("Stream error for session %s", session_id)
            err_event = StreamErrorEvent(
                event_type="error",
                message="An unexpected error occurred",
            )
            json_data = err_event.model_dump_json()
            eid = await event_buffer.append(session_id, json_data)
            yield format_sse_event(err_event, event_id=eid)
        finally:
            # Persist final negotiation state back to the session document.
            # This ensures agent_calls, deal_status, history, and other
            # fields are available for downstream consumers (Specs 190,
            # 192, 195) that read the session after completion.
            try:
                await db.update_session(session_id, final_state)
            except Exception:
                logger.warning("Failed to persist final state for session %s", session_id)

            await tracker.release(email)
            # Deduct AI tokens from user's balance (cloud mode only)
            if settings.RUN_MODE == "cloud" and ai_tokens_used > 0:
                try:
                    user_tokens_cost = compute_token_cost(ai_tokens_used)
                    wl_ref = profile_client._db.collection("waitlist").document(email.lower().strip())
                    wl_doc = await wl_ref.get()
                    if wl_doc.exists:
                        balance = wl_doc.to_dict().get("token_balance", 0)
                        new_balance = max(0, balance - user_tokens_cost)
                        await wl_ref.update({"token_balance": new_balance})
                except Exception:
                    logger.warning("Failed to deduct tokens for %s", email)

            # Write session completion metadata (cloud mode only)
            if settings.RUN_MODE == "cloud":
                try:
                    completed_at = datetime.now(timezone.utc).isoformat()
                    created_at_str = raw_doc.get("created_at")
                    duration_seconds = None
                    if created_at_str:
                        created_dt = datetime.fromisoformat(created_at_str)
                        duration_seconds = int((datetime.now(timezone.utc) - created_dt).total_seconds())
                    updates: dict = {"completed_at": completed_at}
                    if duration_seconds is not None:
                        updates["duration_seconds"] = duration_seconds
                    await db.update_session(session_id, updates)
                except Exception:
                    logger.warning("Failed to write session metadata for %s", session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
