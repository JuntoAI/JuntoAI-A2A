"""API key authentication dependency for the Integration API.

Provides FastAPI dependencies that validate X-API-Key headers, enforce
scope-based access control, and check rate limits before route handlers execute.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Header, HTTPException

from app.db import get_api_key_store
from app.services.api_key_service import ApiKeyService


async def validate_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> dict:
    """FastAPI dependency — validates X-API-Key header and returns key_record.

    Raises:
        HTTPException(401): Missing or invalid API key.
        HTTPException(403): Key is deactivated.
        HTTPException(429): Rate limit exceeded.
    """
    store = get_api_key_store()
    service = ApiKeyService(store)

    # Validate key by hash lookup
    key_record = await service.validate_key(x_api_key)

    if key_record is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_api_key",
                "message": "The provided API key is invalid or does not exist.",
                "details": {},
            },
        )

    # Check if key is active
    if not key_record.get("active", False):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "key_deactivated",
                "message": "This API key has been deactivated.",
                "details": {},
            },
        )

    # Check rate limits
    allowed, rate_info = await service.check_rate_limit(key_record)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Rate limit exceeded. Please retry after the specified time.",
                "details": {
                    "retry_after_seconds": rate_info.get("retry_after_seconds", 60),
                    "limit": rate_info.get("daily_limit", 0),
                    "used": rate_info.get("used_today", 0),
                },
            },
        )

    # Attach rate_info to key_record for downstream use (headers)
    key_record["_rate_info"] = rate_info

    return key_record


def require_scope(scope: str) -> Callable:
    """Return a FastAPI dependency that validates the API key has the given scope.

    Usage:
        @router.get("/endpoint")
        async def endpoint(key_record: dict = Depends(require_scope("simulate"))):
            ...
    """

    async def _scope_dependency(
        x_api_key: str = Header(..., alias="X-API-Key"),
    ) -> dict:
        """Validate API key and enforce the required scope."""
        # First, validate the key (auth + rate limits)
        key_record = await validate_api_key(x_api_key)

        # Check scope
        key_scopes = key_record.get("scopes", [])
        if scope not in key_scopes:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "insufficient_scope",
                    "message": f"This API key does not have the required scope: {scope}.",
                    "details": {"required_scope": scope, "key_scopes": key_scopes},
                },
            )

        return key_record

    return _scope_dependency
