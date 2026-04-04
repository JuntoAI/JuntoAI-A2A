"""Pydantic models for the JuntoAI A2A API."""

from app.models.auth import (
    ChangePasswordRequest,
    CheckEmailResponse,
    GoogleTokenRequest,
    LoginRequest,
    LoginResponse,
    SetPasswordRequest,
)
from app.models.events import (
    AgentMessageEvent,
    AgentThoughtEvent,
    NegotiationCompleteEvent,
    StreamErrorEvent,
)
from app.models.health import HealthResponse
from app.models.negotiation import NegotiationStateModel
from app.models.profile import ProfileDocument, ProfileResponse, ProfileUpdateRequest

__all__ = [
    "HealthResponse",
    "NegotiationStateModel",
    "AgentThoughtEvent",
    "AgentMessageEvent",
    "NegotiationCompleteEvent",
    "StreamErrorEvent",
    "ProfileDocument",
    "ProfileUpdateRequest",
    "ProfileResponse",
    "SetPasswordRequest",
    "ChangePasswordRequest",
    "LoginRequest",
    "GoogleTokenRequest",
    "CheckEmailResponse",
    "LoginResponse",
]
