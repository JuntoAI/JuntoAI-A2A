"""Share service — core business logic for social sharing of negotiation results."""

from __future__ import annotations

import logging
import secrets
import string
import urllib.parse
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.db import get_session_store, get_share_store
from app.exceptions import ShareNotFoundError
from app.models.share import (
    CreateShareResponse,
    EvaluationScores,
    ParticipantSummary,
    PublicMessage,
    SharePayload,
    SocialPostText,
)
from app.scenarios.registry import ScenarioRegistry
from app.services.image_generator import generate_share_image

logger = logging.getLogger(__name__)

_SLUG_ALPHABET = string.ascii_letters + string.digits
_SLUG_LENGTH = 8
_MAX_SLUG_RETRIES = 20

_BRANDING = "Created with @JuntoAI A2A"
_HASHTAGS = "#JuntoAI #A2A #AIAgents #Negotiation"


async def create_or_get_share(
    session_id: str,
    email: str,
    registry: ScenarioRegistry,
) -> CreateShareResponse:
    """Idempotent share creation.

    If a share already exists for *session_id*, returns the existing data.
    Otherwise builds a new SharePayload from the session document, generates
    a slug, triggers image generation, composes social text, and persists.
    """
    share_store = get_share_store()
    session_store = get_session_store()

    # Check for existing share (idempotent)
    existing = await share_store.get_share_by_session(session_id)
    if existing is not None:
        share_url = _share_url(existing.share_slug)
        return CreateShareResponse(
            share_slug=existing.share_slug,
            share_url=share_url,
            social_post_text=_compose_social_text(existing, share_url),
            share_image_url=existing.share_image_url,
        )

    # Fetch session document
    raw_doc = await session_store.get_session_doc(session_id)

    # Validate email ownership
    owner_email = raw_doc.get("owner_email")
    if owner_email is not None and owner_email != email:
        raise HTTPException(status_code=403, detail="Email does not match session owner")

    # Load scenario metadata
    scenario_id = raw_doc.get("scenario_id", "")
    try:
        scenario = registry.get_scenario(scenario_id, email=email)
    except Exception:
        scenario = None

    # Generate unique slug
    slug = await _generate_slug()

    # Build payload (public data only)
    payload = _build_share_payload(raw_doc, scenario, slug)

    # Generate share image
    image_prompt = _build_image_prompt(payload)
    image_url = await generate_share_image(image_prompt, slug)

    # Update payload with actual image URL
    payload = payload.model_copy(update={"share_image_url": image_url})

    # Persist
    await share_store.create_share(payload)

    share_url = _share_url(slug)
    return CreateShareResponse(
        share_slug=slug,
        share_url=share_url,
        social_post_text=_compose_social_text(payload, share_url),
        share_image_url=image_url,
    )


async def get_share(share_slug: str) -> SharePayload:
    """Retrieve a share by slug. Raises ShareNotFoundError if missing."""
    share_store = get_share_store()
    payload = await share_store.get_share(share_slug)
    if payload is None:
        raise ShareNotFoundError(share_slug)
    return payload


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _share_url(slug: str) -> str:
    """Build the public share URL from a slug."""
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/share/{slug}"


async def _generate_slug() -> str:
    """Generate a unique 8-char alphanumeric slug.

    Retries up to ``_MAX_SLUG_RETRIES`` times on collision.
    """
    share_store = get_share_store()
    for _ in range(_MAX_SLUG_RETRIES):
        slug = "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(_SLUG_LENGTH))
        existing = await share_store.get_share(slug)
        if existing is None:
            return slug
    # Extremely unlikely — 62^8 ≈ 218 trillion combinations
    raise RuntimeError("Failed to generate unique slug after max retries")


def _build_share_payload(
    session_doc: dict,
    scenario: object | None,
    slug: str,
) -> SharePayload:
    """Extract ONLY public-facing data from the session document.

    Never includes: history, hidden_context, custom_prompts, model_overrides,
    agent_states, agent_memories, or any other sensitive session internals.
    """
    # Scenario metadata — prefer live registry, fall back to stored config
    if scenario is not None:
        scenario_name = getattr(scenario, "name", "")
        scenario_description = getattr(scenario, "description", "")
    else:
        sc = session_doc.get("scenario_config", {})
        scenario_name = sc.get("name", session_doc.get("scenario_id", "Unknown"))
        scenario_description = sc.get("description", "")

    # Deal status
    deal_status = session_doc.get("deal_status", "Failed")
    if deal_status not in ("Agreed", "Blocked", "Failed"):
        deal_status = "Failed"

    # Participant summaries — use AI-generated if available
    raw_summaries = session_doc.get("participant_summaries", [])
    participant_summaries: list[ParticipantSummary] = []
    if isinstance(raw_summaries, list):
        for ps in raw_summaries:
            if isinstance(ps, dict):
                participant_summaries.append(
                    ParticipantSummary(
                        role=ps.get("role", "Unknown"),
                        name=ps.get("name", "Unknown"),
                        agent_type=ps.get("agent_type", "negotiator"),
                        summary=ps.get("summary", ""),
                    )
                )

    # Outcome text
    outcome_text = _extract_outcome_text(session_doc)

    # Elapsed time — use persisted duration_seconds if available
    duration_seconds = session_doc.get("duration_seconds", 0) or 0
    elapsed_time_ms = int(duration_seconds * 1000)

    # Evaluation scores — extract from evaluation report if present
    evaluation_scores = _extract_evaluation_scores(session_doc)

    # Public conversation — extract public_message fields from history
    public_conversation = _extract_public_conversation(session_doc)

    return SharePayload(
        share_slug=slug,
        session_id=session_doc.get("session_id", ""),
        scenario_id=session_doc.get("scenario_id", ""),
        scenario_name=scenario_name,
        scenario_description=scenario_description,
        deal_status=deal_status,
        outcome_text=outcome_text,
        final_offer=max(0.0, float(session_doc.get("current_offer", 0) or 0)),
        turns_completed=max(0, int(session_doc.get("turn_count", 0) or 0)),
        warning_count=max(0, int(session_doc.get("warning_count", 0) or 0)),
        participant_summaries=participant_summaries,
        evaluation_scores=evaluation_scores,
        public_conversation=public_conversation,
        elapsed_time_ms=elapsed_time_ms,
        share_image_url="",  # placeholder — updated after image generation
        created_at=datetime.now(timezone.utc),
    )


def _extract_outcome_text(session_doc: dict) -> str:
    """Build a human-readable outcome summary from the session document."""
    deal_status = session_doc.get("deal_status", "Failed")
    current_offer = session_doc.get("current_offer", 0)

    if deal_status == "Agreed":
        return f"Deal agreed at ${current_offer:,.2f}"
    elif deal_status == "Blocked":
        return "Negotiation blocked by regulator"
    else:
        max_turns = session_doc.get("max_turns", 0)
        return f"Negotiation failed after {max_turns} turns without agreement"


def _extract_evaluation_scores(session_doc: dict) -> EvaluationScores | None:
    """Extract evaluation dimension scores from the session's evaluation report.

    Returns None if no evaluation data is present.
    """
    evaluation = session_doc.get("evaluation")
    if not isinstance(evaluation, dict):
        return None

    dimensions = evaluation.get("dimensions")
    if not isinstance(dimensions, dict):
        return None

    overall_score = evaluation.get("overall_score")
    if overall_score is None:
        return None

    try:
        return EvaluationScores(
            fairness=int(dimensions.get("fairness", 5)),
            mutual_respect=int(dimensions.get("mutual_respect", 5)),
            value_creation=int(dimensions.get("value_creation", 5)),
            satisfaction=int(dimensions.get("satisfaction", 5)),
            overall_score=int(overall_score),
        )
    except (ValueError, TypeError):
        return None


def _extract_public_conversation(session_doc: dict) -> list[PublicMessage]:
    """Extract public messages from session history.

    Only includes public_message fields — never inner_thought, reasoning,
    or other private agent data.
    """
    history = session_doc.get("history")
    if not isinstance(history, list):
        return []

    messages: list[PublicMessage] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        if not isinstance(content, dict):
            continue
        public_msg = content.get("public_message")
        if not public_msg or not isinstance(public_msg, str):
            continue
        messages.append(
            PublicMessage(
                agent_name=entry.get("name", entry.get("role", "Unknown")),
                role=entry.get("role", "Unknown"),
                agent_type=entry.get("agent_type", "negotiator"),
                message=public_msg,
                turn_number=entry.get("turn_number", 0),
            )
        )

    return messages


def _build_image_prompt(payload: SharePayload) -> str:
    """Build an image generation prompt from public summary data only.

    Uses only fields present in the SharePayload — never raw history,
    hidden context, or other sensitive session data.
    """
    participants = ", ".join(
        f"{p.name} ({p.role})" for p in payload.participant_summaries
    )
    return (
        f"A professional, modern illustration for a negotiation summary. "
        f"Scenario: {payload.scenario_name}. "
        f"Participants: {participants or 'AI Agents'}. "
        f"Outcome: {payload.deal_status}. "
        f"Style: clean corporate infographic, blue and green tones, "
        f"abstract handshake or deal imagery. No text overlay."
    )


def _compose_social_text(payload: SharePayload, share_url: str) -> SocialPostText:
    """Compose platform-specific social post text.

    All variants include: share URL, branding, and hashtags.
    Twitter variant is truncated to ≤280 chars preserving URL + branding + hashtags.
    """
    summary = _one_sentence_summary(payload)

    # Full post template (used for LinkedIn/Facebook)
    full_text = f"{summary}\n\n{_BRANDING}\n{share_url}\n{_HASHTAGS}"

    # LinkedIn / Facebook — generous limits
    linkedin = full_text[:3000]
    facebook = full_text[:3000]

    # Twitter — must fit in 280 chars
    twitter = _truncate_for_twitter(summary, share_url)

    return SocialPostText(
        twitter=twitter,
        linkedin=linkedin,
        facebook=facebook,
    )


def _one_sentence_summary(payload: SharePayload) -> str:
    """Build a one-sentence negotiation summary from public data."""
    status_verb = {
        "Agreed": "reached a deal",
        "Blocked": "was blocked by the regulator",
        "Failed": "ended without agreement",
    }
    verb = status_verb.get(payload.deal_status, "completed")

    offer_part = ""
    if payload.deal_status == "Agreed" and payload.final_offer > 0:
        offer_part = f" at ${payload.final_offer:,.2f}"

    return (
        f"I just simulated a {payload.scenario_name} negotiation "
        f"— the AI agents {verb}{offer_part}"
    )


def _truncate_for_twitter(summary: str, share_url: str) -> str:
    """Build a Twitter post ≤280 chars, truncating summary if needed.

    Preserves: URL + branding + hashtags. Truncates summary with '…'.
    """
    suffix = f"\n\n{_BRANDING}\n{share_url}\n{_HASHTAGS}"
    max_summary_len = 280 - len(suffix)

    if max_summary_len <= 0:
        # Edge case: suffix alone exceeds 280 — just return suffix truncated
        return suffix.strip()[:280]

    if len(summary) <= max_summary_len:
        return f"{summary}{suffix}"

    # Truncate summary with ellipsis
    truncated = summary[: max_summary_len - 1] + "…"
    return f"{truncated}{suffix}"


def generate_meta_tags(payload: SharePayload, site_url: str) -> dict:
    """Generate Open Graph and Twitter Card meta tag values for a SharePayload.

    Returns a dict with keys: og:title, og:description, og:image, og:url,
    twitter:card, twitter:title, twitter:description, twitter:image.
    """
    title = f"{payload.scenario_name} — {payload.deal_status}"
    description_source = payload.outcome_text or payload.scenario_description
    description = description_source[:199] + "…" if len(description_source) > 200 else description_source
    image = payload.share_image_url
    url = f"{site_url.rstrip('/')}/share/{payload.share_slug}"

    return {
        "og:title": title,
        "og:description": description,
        "og:image": image,
        "og:url": url,
        "twitter:card": "summary_large_image",
        "twitter:title": title,
        "twitter:description": description,
        "twitter:image": image,
    }


def _compose_mailto(payload: SharePayload, share_url: str) -> str:
    """Build a mailto link with pre-filled subject and body.

    Subject: scenario name + deal status
    Body: summary + URL + branding
    """
    subject = f"JuntoAI A2A: {payload.scenario_name} — Deal {payload.deal_status}"
    body = (
        f"{_one_sentence_summary(payload)}\n\n"
        f"View the full negotiation: {share_url}\n\n"
        f"{_BRANDING}"
    )
    params = urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
    return f"mailto:?{params}"
