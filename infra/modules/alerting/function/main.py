"""Telegram notifier Cloud Function for GCP alerting pipeline.

Receives Pub/Sub messages from GCP Monitoring alerting policies and Cloud Build
events, formats them as HTML, and sends to a Telegram group chat.
"""

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime

import functions_framework
import requests
from google.cloud import secretmanager

logger = logging.getLogger(__name__)

# Module-level cache for secrets (cold start optimization)
_cached_bot_token: str | None = None
_cached_chat_id: str | None = None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AlertIncident:
    policy_name: str
    state: str  # "open" or "closed"
    condition_name: str
    resource_labels: dict[str, str]
    summary: str
    started_at: int | None
    ended_at: int | None
    url: str


@dataclass
class CloudBuildEvent:
    build_id: str
    status: str  # "FAILURE", "TIMEOUT", "INTERNAL_ERROR"
    trigger_name: str
    branch: str
    commit_sha: str
    log_url: str
    start_time: str
    finish_time: str
    duration_seconds: float


# ---------------------------------------------------------------------------
# 8.2 — Secret Manager helpers
# ---------------------------------------------------------------------------

def _get_secrets() -> tuple[str, str]:
    """Fetch and cache telegram-bot-token and telegram-chat-id from Secret Manager.

    Uses module-level globals so secrets are only fetched once per cold start.
    """
    global _cached_bot_token, _cached_chat_id

    if _cached_bot_token is not None and _cached_chat_id is not None:
        return _cached_bot_token, _cached_chat_id

    client = secretmanager.SecretManagerServiceClient()
    project_id = os.environ.get("GCP_PROJECT")

    token_name = f"projects/{project_id}/secrets/telegram-bot-token/versions/latest"
    chat_id_name = f"projects/{project_id}/secrets/telegram-chat-id/versions/latest"

    token_response = client.access_secret_version(request={"name": token_name})
    _cached_bot_token = token_response.payload.data.decode("utf-8")

    chat_id_response = client.access_secret_version(request={"name": chat_id_name})
    _cached_chat_id = chat_id_response.payload.data.decode("utf-8")

    return _cached_bot_token, _cached_chat_id


# ---------------------------------------------------------------------------
# 8.3 — Message type detection
# ---------------------------------------------------------------------------

def detect_message_type(payload: dict) -> str:
    """Detect whether a Pub/Sub payload is an alerting policy or Cloud Build event.

    Returns "alerting_policy", "cloud_build", or "unknown".
    """
    if "incident" in payload:
        return "alerting_policy"
    if "status" in payload and ("id" in payload or "substitutions" in payload):
        return "cloud_build"
    return "unknown"


# ---------------------------------------------------------------------------
# 8.4 — Alerting incident parser
# ---------------------------------------------------------------------------

def parse_alerting_incident(payload: dict) -> AlertIncident:
    """Extract fields from a GCP Monitoring notification into an AlertIncident."""
    incident = payload.get("incident", {})
    resource = incident.get("resource", {})
    return AlertIncident(
        policy_name=incident.get("policy_name", "Unknown Policy"),
        state=incident.get("state", "unknown"),
        condition_name=incident.get("condition_name", ""),
        resource_labels=resource.get("labels", {}),
        summary=incident.get("summary", ""),
        started_at=incident.get("started_at"),
        ended_at=incident.get("ended_at"),
        url=incident.get("url", ""),
    )


# ---------------------------------------------------------------------------
# 8.5 — Cloud Build event parser
# ---------------------------------------------------------------------------

def _calculate_duration(start_time: str, finish_time: str) -> float:
    """Calculate duration in seconds between two ISO 8601 timestamps."""
    try:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finish_time.replace("Z", "+00:00"))
        return (finish - start).total_seconds()
    except (ValueError, TypeError):
        return 0.0


def parse_cloud_build_event(payload: dict) -> CloudBuildEvent:
    """Extract fields from a Cloud Build event into a CloudBuildEvent."""
    substitutions = payload.get("substitutions", {})
    source = payload.get("source", {})
    repo_source = source.get("repoSource", {})

    start_time = payload.get("startTime", "")
    finish_time = payload.get("finishTime", "")

    return CloudBuildEvent(
        build_id=payload.get("id", "unknown"),
        status=payload.get("status", "UNKNOWN"),
        trigger_name=substitutions.get("TRIGGER_NAME", "unknown"),
        branch=substitutions.get("BRANCH_NAME", repo_source.get("branchName", "unknown")),
        commit_sha=substitutions.get("SHORT_SHA", repo_source.get("commitSha", "unknown")[:7] if repo_source.get("commitSha") else "unknown"),
        log_url=payload.get("logUrl", ""),
        start_time=start_time,
        finish_time=finish_time,
        duration_seconds=_calculate_duration(start_time, finish_time),
    )


# ---------------------------------------------------------------------------
# 8.6 — Alerting message formatter
# ---------------------------------------------------------------------------

def format_alerting_message(incident: AlertIncident) -> str:
    """Format an AlertIncident as an HTML Telegram message.

    Uses 🚨 prefix for firing (open) incidents and ✅ for resolved (closed).
    """
    is_open = incident.state == "open"
    service_name = incident.resource_labels.get("service_name", "unknown")

    if is_open:
        prefix = "🚨"
        title = f"ALARM: {incident.policy_name}"
        state_label = "FIRING"
        time_label = "Started"
        timestamp = incident.started_at
    else:
        prefix = "✅"
        title = f"RESOLVED: {incident.policy_name}"
        state_label = "RESOLVED"
        time_label = "Resolved"
        timestamp = incident.ended_at

    time_str = ""
    if timestamp is not None:
        time_str = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        f'{prefix} <b>{title}</b>',
        "",
        f"<b>State:</b> {state_label}",
        f"<b>Resource:</b> {service_name}",
        f"<b>Condition:</b> {incident.condition_name}",
        f"<b>{time_label}:</b> {time_str}",
    ]

    if is_open:
        lines.append(f"<b>Summary:</b> {incident.summary}")
        lines.append(f'<b>Link:</b> <a href="{incident.url}">View Incident</a>')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 8.7 — Cloud Build message formatter
# ---------------------------------------------------------------------------

def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string like '5m 12s'."""
    if seconds <= 0:
        return "0s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_cloud_build_message(build: CloudBuildEvent) -> str:
    """Format a CloudBuildEvent as an HTML Telegram message with 🔴 prefix."""
    duration_str = _format_duration(build.duration_seconds)

    lines = [
        f'🔴 <b>Build FAILED: {build.trigger_name}</b>',
        "",
        f"<b>Status:</b> {build.status}",
        f"<b>Branch:</b> {build.branch}",
        f"<b>Commit:</b> {build.commit_sha}",
        f"<b>Duration:</b> {duration_str}",
        f'<b>Logs:</b> <a href="{build.log_url}">View Build Logs</a>',
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 8.8 — Telegram sender
# ---------------------------------------------------------------------------

def send_telegram_message(text: str) -> None:
    """POST a message to the Telegram Bot API. Raises on non-2xx response."""
    bot_token, chat_id = _get_secrets()

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    response = requests.post(url, json=payload, timeout=10)

    if not response.ok:
        logger.error(
            "Telegram API error: status=%d body=%s",
            response.status_code,
            response.text,
        )
        response.raise_for_status()


# ---------------------------------------------------------------------------
# 8.9 — Entry point
# ---------------------------------------------------------------------------

@functions_framework.cloud_event
def handle_pubsub(cloud_event) -> None:
    """Cloud Function entry point. Orchestrates detect → parse → format → send.

    Decodes base64 Pub/Sub data, detects message type, routes to the
    appropriate parser and formatter, and sends the result to Telegram.
    SUCCESS Cloud Build events and unknown schemas are silently discarded.
    """
    # Decode the Pub/Sub message data
    raw_data = cloud_event.data["message"]["data"]
    decoded = base64.b64decode(raw_data).decode("utf-8")

    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError:
        logger.warning("Failed to parse Pub/Sub message as JSON: %s", decoded[:200])
        return

    message_type = detect_message_type(payload)

    if message_type == "alerting_policy":
        incident = parse_alerting_incident(payload)
        message = format_alerting_message(incident)
        send_telegram_message(message)
        logger.info("Sent alerting notification for policy: %s", incident.policy_name)

    elif message_type == "cloud_build":
        status = payload.get("status", "")
        if status == "SUCCESS":
            logger.info("Discarding SUCCESS Cloud Build event")
            return
        build = parse_cloud_build_event(payload)
        message = format_cloud_build_message(build)
        send_telegram_message(message)
        logger.info("Sent Cloud Build failure notification: %s", build.trigger_name)

    else:
        logger.warning("Unknown message schema, discarding: %s", str(payload)[:200])
