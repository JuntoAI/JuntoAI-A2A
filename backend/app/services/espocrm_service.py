"""EspoCRM contact synchronisation service.

Provides two public entry points:
- ``build_contact_payload`` — pure function, no I/O, fully testable.
- ``sync_contact`` — async upsert; never raises to its caller.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.models.admin import CrmSyncResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Payload builder — pure function, no side effects
# ---------------------------------------------------------------------------


def build_contact_payload(
    email: str,
    waitlist_data: dict,
    profile_data: dict | None,
) -> dict:
    """Build the EspoCRM Contact JSON payload.

    Pure function — no I/O, no side effects, deterministic output.

    Args:
        email: Raw email string (will be normalised internally).
        waitlist_data: Firestore waitlist document dict.
        profile_data: Firestore profile document dict, or None.

    Returns:
        Dict with all nine required EspoCRM Contact fields.
    """
    normalised_email = email.lower().strip()

    # --- Name splitting ---
    display_name = (profile_data or {}).get("display_name", "") or ""
    display_name = display_name.strip()
    if display_name and " " in display_name:
        first_name, last_name = display_name.split(" ", 1)
    elif display_name:
        # Single-word display name — use it as firstName, lastName empty
        first_name = display_name
        last_name = ""
    else:
        # Fallback: derive firstName from email local part
        first_name = normalised_email.split("@")[0]
        last_name = ""

    # --- Timestamps ---
    signed_up_at = waitlist_data.get("signed_up_at")
    if signed_up_at:
        if isinstance(signed_up_at, datetime):
            registered_at = signed_up_at.astimezone(timezone.utc).isoformat()
        else:
            registered_at = str(signed_up_at)
    else:
        registered_at = datetime.now(timezone.utc).isoformat()

    return {
        "emailAddress": normalised_email,
        "firstName": first_name,
        "lastName": last_name,
        "juntoaiServices": ["a2a"],
        "juntoaiRegisteredAt": registered_at,
        "juntoaiMarketingEmail": True,
        "juntoaiConsentTimestamp": registered_at,
        "accountId": settings.ESPOCRM_JUNTOAI_MINI_ACCOUNT_ID,
        "teamsIds": [settings.ESPOCRM_JUNTOAI_TEAM_ID],
    }


# ---------------------------------------------------------------------------
# Sync function — async, never raises
# ---------------------------------------------------------------------------


async def sync_contact(
    email: str,
    waitlist_data: dict,
    profile_data: dict | None,
) -> CrmSyncResult:
    """Upsert a Contact in EspoCRM. Never raises.

    Guards:
    - Returns ``action="skipped"`` immediately in local mode.
    - Returns ``action="skipped"`` when ESPOCRM_URL or ESPOCRM_API_KEY is empty.

    All HTTP errors and exceptions are caught and returned as ``action="error"``.

    Args:
        email: User email address.
        waitlist_data: Firestore waitlist document dict.
        profile_data: Firestore profile document dict, or None.

    Returns:
        CrmSyncResult with action one of "created", "updated", "skipped", "error".
    """
    normalised_email = email.lower().strip()

    # Guard 1: local mode
    if settings.RUN_MODE == "local":
        return CrmSyncResult(email=normalised_email, action="skipped")

    # Guard 2: missing config
    if not settings.ESPOCRM_URL or not settings.ESPOCRM_API_KEY:
        logger.warning(
            "espocrm action=skipped reason=missing_config email=%s",
            normalised_email,
        )
        return CrmSyncResult(email=normalised_email, action="skipped")

    payload = build_contact_payload(email, waitlist_data, profile_data)

    headers = {"X-Api-Key": settings.ESPOCRM_API_KEY}
    base_url = settings.ESPOCRM_URL.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            # Search for existing contact by email
            search_url = (
                f"{base_url}/api/v1/Contact"
                f"?where[0][type]=equals"
                f"&where[0][attribute]=emailAddress"
                f"&where[0][value]={normalised_email}"
            )
            search_resp = await client.get(search_url)
            search_resp.raise_for_status()
            search_data = search_resp.json()
            total = search_data.get("total", 0)

            if total == 0:
                # Create new contact
                create_resp = await client.post(
                    f"{base_url}/api/v1/Contact",
                    json=payload,
                )
                create_resp.raise_for_status()
                logger.info(
                    "espocrm action=created email=%s",
                    normalised_email,
                )
                return CrmSyncResult(email=normalised_email, action="created")
            else:
                # Update first matching contact
                contact_id = search_data["list"][0]["id"]
                update_resp = await client.put(
                    f"{base_url}/api/v1/Contact/{contact_id}",
                    json=payload,
                )
                update_resp.raise_for_status()
                logger.info(
                    "espocrm action=updated email=%s contact_id=%s",
                    normalised_email,
                    contact_id,
                )
                return CrmSyncResult(email=normalised_email, action="updated")

    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500]
        detail = f"HTTP {exc.response.status_code}: {body}"
        logger.error(
            "espocrm action=error email=%s status=%d body=%s",
            normalised_email,
            exc.response.status_code,
            body,
        )
        return CrmSyncResult(email=normalised_email, action="error", detail=detail)

    except httpx.RequestError as exc:
        detail = f"{type(exc).__name__}: {exc}"
        logger.error(
            "espocrm action=error email=%s exception=%s",
            normalised_email,
            detail,
        )
        return CrmSyncResult(email=normalised_email, action="error", detail=detail)

    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {exc}"
        logger.error(
            "espocrm action=error email=%s exception=%s",
            normalised_email,
            detail,
        )
        return CrmSyncResult(email=normalised_email, action="error", detail=detail)
