"""Integration API authentication dependency.

Validates requests using two headers:
- X-Integration-Token: org token (hashed, looked up in store)
- X-User-Email: email of the CRM user triggering the request

The email's domain must match the org's registered domain.
Rate limits are enforced per-org (daily + per-minute).
No scopes — all authenticated orgs get full API access.
"""

from __future__ import annotations

import re

from fastapi import Header, HTTPException

from app.db import get_api_key_store
from app.services.api_key_service import ApiKeyService

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _extract_domain(email: str) -> str:
    """Extract the domain part from an email address."""
    return email.rsplit("@", 1)[-1].lower().strip()


async def validate_integration_auth(
    x_integration_token: str = Header(..., alias="X-Integration-Token"),
    x_user_email: str = Header(..., alias="X-User-Email"),
) -> dict:
    """FastAPI dependency — validates org token + user email domain.

    Returns a dict with the org record and the validated user email:
    {**org_record, "_user_email": email, "_rate_info": rate_info}

    Raises:
        HTTPException(401): Invalid or missing token.
        HTTPException(401): Invalid email format.
        HTTPException(403): Token deactivated.
        HTTPException(403): Email domain does not match org domain.
        HTTPException(429): Rate limit exceeded.
    """
    # Validate email format
    if not x_user_email or not _EMAIL_RE.match(x_user_email):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_email",
                "message": "X-User-Email header must contain a valid email address.",
                "details": {},
            },
        )

    store = get_api_key_store()
    service = ApiKeyService(store)

    # Validate token by hash lookup
    org_record = await service.validate_key(x_integration_token)

    if org_record is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_token",
                "message": "The provided integration token is invalid or does not exist.",
                "details": {},
            },
        )

    # Check if org is active
    if not org_record.get("active", False):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "org_deactivated",
                "message": "This organization's integration access has been deactivated.",
                "details": {},
            },
        )

    # Check email domain matches org domain
    user_domain = _extract_domain(x_user_email)
    org_domain = org_record.get("domain", "").lower().strip()

    if user_domain != org_domain:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "domain_mismatch",
                "message": f"Email domain '{user_domain}' does not match the organization's registered domain.",
                "details": {"expected_domain": org_domain, "provided_domain": user_domain},
            },
        )

    # Check rate limits (per-org)
    allowed, rate_info = await service.check_rate_limit(org_record)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Organization rate limit exceeded. Please retry after the specified time.",
                "details": {
                    "retry_after_seconds": rate_info.get("retry_after_seconds", 60),
                    "limit": rate_info.get("daily_limit", 0),
                    "used": rate_info.get("used_today", 0),
                },
            },
        )

    # Attach metadata for downstream use
    org_record["_user_email"] = x_user_email.strip()
    org_record["_rate_info"] = rate_info

    return org_record
