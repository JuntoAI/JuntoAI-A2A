"""Pydantic V2 models for authentication endpoints."""

from pydantic import BaseModel, field_validator


class SetPasswordRequest(BaseModel):
    """Request body for POST /api/v1/auth/set-password."""

    email: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        return v


class ChangePasswordRequest(BaseModel):
    """Request body for password change."""

    email: str
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        return v


class LoginRequest(BaseModel):
    """Request body for POST /api/v1/auth/login."""

    email: str
    password: str


class GoogleTokenRequest(BaseModel):
    """Request body for Google OAuth endpoints."""

    id_token: str
    email: str | None = None  # Required for link, optional for login


class CheckEmailResponse(BaseModel):
    """Response for GET /api/v1/auth/check-email/{email}."""

    has_password: bool


class LoginResponse(BaseModel):
    """Response for successful login."""

    email: str
    tier: int
    daily_limit: int
    token_balance: int
