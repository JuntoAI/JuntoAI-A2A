"""Pydantic V2 models for user profile management.

Defines the Firestore document schema, API request/response models,
and field validators for the profile system.
"""

import re
from datetime import datetime

import pycountry
from pydantic import BaseModel, field_validator


class ProfileDocument(BaseModel):
    """Firestore profile document schema."""

    display_name: str = ""
    email_verified: bool = False
    github_url: str | None = None
    linkedin_url: str | None = None
    profile_completed_at: datetime | None = None
    created_at: datetime | None = None
    password_hash: str | None = None
    country: str | None = None
    google_oauth_id: str | None = None


class ProfileUpdateRequest(BaseModel):
    """Request body for PUT /api/v1/profile/{email}."""

    display_name: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    country: str | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2 or len(v) > 100:
            raise ValueError("Display name must be between 2 and 100 characters")
        return v

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.rstrip("/")
        pattern = r"^https://github\.com/[a-zA-Z0-9\-]{1,39}$"
        if not re.match(pattern, v):
            raise ValueError("GitHub URL must match https://github.com/{username}")
        return v

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.rstrip("/")
        pattern = r"^https://(www\.)?linkedin\.com/in/[a-zA-Z0-9\-]{3,100}$"
        if not re.match(pattern, v):
            raise ValueError(
                "LinkedIn URL must match https://linkedin.com/in/{slug}"
            )
        return v

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if pycountry.countries.get(alpha_2=v.upper()) is None:
            raise ValueError(
                f"Invalid country code: {v}. Must be a valid ISO 3166-1 alpha-2 code."
            )
        return v.upper()


class ProfileResponse(BaseModel):
    """Response body for profile endpoints."""

    display_name: str
    email_verified: bool
    github_url: str | None
    linkedin_url: str | None
    profile_completed_at: datetime | None
    created_at: datetime | None
    password_hash_set: bool  # True if password_hash is non-null (never expose hash)
    country: str | None
    google_oauth_id: str | None
    tier: int
    daily_limit: int
    token_balance: int
