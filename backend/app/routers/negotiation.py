"""SSE streaming endpoint and session start for real-time negotiations."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from app.config import settings
from app.db import get_profile_client, get_session_store
from app.db.base import SessionStore
from app.middleware import get_event_buffer, get_sse_tracker
from app.middleware.event_buffer import SSEEventBuffer
from app.middleware.sse_limiter import SSEConnectionTracker
from app.models.events import (
    AgentMessageEvent,
    AgentThoughtEvent,
    NegotiationCompleteEvent,
    NegotiationStallEvent,
    StreamErrorEvent,
)
from app.models.negotiation import NegotiationStateModel
from app.orchestrator import model_router
from app.orchestrator.graph import run_negotiation
from app.orchestrator.state import create_initial_state
from app.scenarios.registry import ScenarioRegistry
from app.scenarios.router import get_scenario_registry
from app.services.tier_calculator import calculate_tier, get_daily_limit
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
):
    """Create a new negotiation session.

    Validates the scenario, builds initial state with toggle injection,
    persists to Firestore, and returns the session_id.
    """
    # 1. Validate scenario exists
    try:
        scenario = registry.get_scenario(body.scenario_id, email=body.email)
    except Exception:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Scenario '{body.scenario_id}' not found"},
        )

    # 2. Validate model_overrides against available models
    if body.model_overrides:
        available_model_ids: set[str] = set()
        for sc in registry._scenarios.values():
            for agent in sc.agents:
                available_model_ids.add(agent.model_id)
                if agent.fallback_model_id:
                    available_model_ids.add(agent.fallback_model_id)
        # Filter to supported families only
        available_model_ids = {
            mid for mid in available_model_ids
            if (mid.split("-", 1)[0] if "-" in mid else mid) in model_router.MODEL_FAMILIES
        }
        for role, mid in body.model_overrides.items():
            if mid not in available_model_ids:
                return JSONResponse(
                    status_code=422,
                    content={"detail": f"Invalid model_id '{mid}' for role '{role}'. Available models: {sorted(available_model_ids)}"},
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
        doc_ref = db._collection.document(session_id)  # type: ignore[attr-defined]
        await doc_ref.set(doc_data)
    else:
        # Local: use the SessionStore protocol
        await db.create_session(state)

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


def _find_warned_negotiator(history: list[dict], regulator_index: int) -> str:
    """Walk backward from a regulator entry to find the most recent negotiator.

    Looks past other non-negotiator entries (observers, other regulators)
    that may sit between the negotiator and the regulator in history.
    """
    for j in range(regulator_index - 1, -1, -1):
        if history[j].get("agent_type") == "negotiator":
            return history[j].get("role", "Unknown")
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
            # Use the first message for their opening stance
            first_msg = (first or {}).get("content", {}).get("public_message", "")
            last_msg = content.get("public_message", "")
            # Build a concise summary
            parts = [f"{name}"]
            if final_price and final_price > 0:
                parts.append(f"ended at {_format_price_for_summary(final_price, value_format, value_label)}")
            if last_msg:
                # Take first sentence of last public message as their final stance
                first_sentence = last_msg.split(".")[0].strip()
                if len(first_sentence) > 150:
                    first_sentence = first_sentence[:147] + "..."
                parts.append(first_sentence)
            elif first_msg:
                first_sentence = first_msg.split(".")[0].strip()
                if len(first_sentence) > 150:
                    first_sentence = first_sentence[:147] + "..."
                parts.append(first_sentence)

            summaries.append({
                "role": role,
                "name": name,
                "agent_type": agent_type,
                "summary": ". ".join(parts[1:]) if len(parts) > 1 else f"Participated as {name}",
            })

        elif agent_type == "regulator":
            warning_count = info.get("warning_count", 0)
            status = content.get("status", "")
            reasoning = content.get("reasoning", "") or content.get("public_message", "")
            first_sentence = reasoning.split(".")[0].strip() if reasoning else ""
            if len(first_sentence) > 150:
                first_sentence = first_sentence[:147] + "..."

            summary_text = ""
            if status == "BLOCKED":
                summary_text = f"Blocked the deal after issuing {warning_count} warning(s). {first_sentence}"
            elif warning_count > 0:
                summary_text = f"Issued {warning_count} warning(s). {first_sentence}"
            else:
                summary_text = first_sentence or f"Monitored the negotiation as {name}"

            summaries.append({
                "role": role,
                "name": name,
                "agent_type": agent_type,
                "summary": summary_text.strip(),
            })

        elif agent_type == "observer":
            observation = content.get("observation", "") or content.get("public_message", "")
            first_sentence = observation.split(".")[0].strip() if observation else ""
            if len(first_sentence) > 150:
                first_sentence = first_sentence[:147] + "..."
            summaries.append({
                "role": role,
                "name": name,
                "agent_type": agent_type,
                "summary": first_sentence or f"Observed as {name}",
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
        warned_role = _find_warned_negotiator(history, i)
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


def _snapshot_to_events(snapshot: dict, session_id: str, accumulated_history: list[dict] | None = None):
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
    """
    if accumulated_history is None:
        accumulated_history = []
    events = []
    for _node_name, state in snapshot.items():
        if not isinstance(state, dict):
            continue

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
        # Fall back to 0 if not present (dispatcher snapshots).
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
    try:
        scenario = registry.get_scenario(state.scenario_id, email=email)
        scenario_config = scenario.model_dump()
    except Exception:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Scenario '{state.scenario_id}' not found"},
        )

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
        }

        # If reconnecting, replay missed events first
        if last_event_id is not None:
            replay = await event_buffer.replay_after(session_id, last_event_id)
            for eid, evt_data in replay:
                yield f"id: {eid}\ndata: {evt_data}\n\n"

        try:
            async with asyncio.timeout(timeout):
                accumulated_history: list[dict] = []
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
                    events = _snapshot_to_events(snapshot, session_id, accumulated_history)
                    # Track tokens from snapshot state
                    for _node, s in snapshot.items():
                        if isinstance(s, dict):
                            ai_tokens_used = max(ai_tokens_used, s.get("total_tokens_used", 0))
                    for event in events:
                        is_terminal = isinstance(event, (NegotiationCompleteEvent,))
                        json_data = event.model_dump_json()
                        eid = await event_buffer.append(session_id, json_data, is_terminal=is_terminal)
                        yield format_sse_event(event, event_id=eid)
                        if is_terminal:
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
                    # Scale: 1 user token per 1000 AI tokens (rounded up)
                    user_tokens_cost = max(1, (ai_tokens_used + 999) // 1000)
                    wl_ref = profile_client._db.collection("waitlist").document(email.lower().strip())
                    wl_doc = await wl_ref.get()
                    if wl_doc.exists:
                        balance = wl_doc.to_dict().get("token_balance", 0)
                        new_balance = max(0, balance - user_tokens_cost)
                        await wl_ref.update({"token_balance": new_balance})
                except Exception:
                    logger.warning("Failed to deduct tokens for %s", email)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
