"""Builder SSE event Pydantic models with Literal discriminators."""

from typing import Literal

from pydantic import BaseModel


class BuilderTokenEvent(BaseModel):
    """SSE event for an individual chatbot response token."""

    event_type: Literal["builder_token"]
    token: str


class BuilderJsonDeltaEvent(BaseModel):
    """SSE event for an updated scenario JSON section."""

    event_type: Literal["builder_json_delta"]
    section: str
    data: dict


class BuilderCompleteEvent(BaseModel):
    """SSE event signaling the chatbot finished responding."""

    event_type: Literal["builder_complete"]


class BuilderErrorEvent(BaseModel):
    """SSE event for errors during builder streaming."""

    event_type: Literal["builder_error"]
    message: str


class HealthCheckStartEvent(BaseModel):
    """SSE event signaling the health check analysis has begun."""

    event_type: Literal["builder_health_check_start"]


class HealthCheckFindingEvent(BaseModel):
    """SSE event for an individual health check finding."""

    event_type: Literal["builder_health_check_finding"]
    check_name: str
    severity: Literal["critical", "warning", "info"]
    agent_role: str | None = None
    message: str


class HealthCheckCompleteEvent(BaseModel):
    """SSE event for the completed health check report."""

    event_type: Literal["builder_health_check_complete"]
    report: dict
